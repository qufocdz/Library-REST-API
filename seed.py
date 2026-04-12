# seed.py
from __future__ import annotations

import argparse
import contextlib
import dataclasses
import datetime as dt
import hashlib
import json
import logging
import os
import random
import re
import sys
import time
from decimal import Decimal
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests
from sqlalchemy import create_engine, text
from sqlalchemy.orm import Session, sessionmaker

try:
    # Prefer projektowy SessionLocal, zgodnie z Twoim patternem
    from database import SessionLocal as ProjectSessionLocal  # type: ignore
except Exception:
    ProjectSessionLocal = None

# Optional FastAPI trigger
try:
    from fastapi import Depends, FastAPI, HTTPException
except Exception:
    FastAPI = None  # type: ignore
    Depends = None  # type: ignore
    HTTPException = None  # type: ignore


ISBN_CLEAN_RE = re.compile(r"[^0-9xX]")
DEFAULT_FIELDS = [
    "title",
    "author_name",
    "publisher",
    "isbn",
    "first_publish_year",
    "publish_year",
    "number_of_pages_median",
    "subject",
]
OPENLIB_SEARCH_URL = "https://openlibrary.org/search.json"

DEFAULT_RENTAL_RATE = Decimal("9.99")
DEFAULT_PUBLICATION_YEAR = 2000

LOCKFILE_DEFAULT = ".seed_openlibrary.lock"

logger = logging.getLogger("seed")


@dataclasses.dataclass
class SeedConfig:
    # DB
    db_url: Optional[str] = None

    # Open Library
    user_agent: str = "librarydb-seeder/1.0 (contact: you@example.com)"
    fields: List[str] = dataclasses.field(default_factory=lambda: list(DEFAULT_FIELDS))
    queries: List[str] = dataclasses.field(default_factory=lambda: ["polska historia", "fantasy"])
    max_books: int = 50
    per_query_limit: int = 20
    delay: float = 0.4
    lang: str = "pl"

    # Local generation
    copies_per_book: int = 0
    seed_readers: bool = False

    # Control
    dry_run: bool = False
    lock_file: str = LOCKFILE_DEFAULT

    # network
    timeout_s: float = 20.0
    max_retries: int = 4
    backoff_base_s: float = 0.8


@dataclasses.dataclass
class SeedResult:
    api_requests: int = 0
    docs_seen: int = 0
    books_attempted: int = 0
    books_upserted: int = 0
    books_skipped_no_isbn: int = 0
    authors_linked: int = 0
    categories_linked: int = 0
    copies_created: int = 0
    readers_created: int = 0
    libraries_used: int = 0
    warnings: List[str] = dataclasses.field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return dataclasses.asdict(self)


def setup_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s %(levelname)s %(name)s - %(message)s",
    )


@contextlib.contextmanager
def acquire_lock(lock_path: str):
    """
    Prosty lock plikowy (dev/test). Chroni przed równoległym uruchomieniem seeda,
    co mogłoby tworzyć duplikaty w author/publisher (brak UNIQUE w schemacie).
    """
    lock_path = os.path.abspath(lock_path)
    try:
        fd = os.open(lock_path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        raise RuntimeError(f"Lock file exists: {lock_path}. Another seed may be running.")
    try:
        os.write(fd, str(os.getpid()).encode("utf-8"))
        os.close(fd)
        yield
    finally:
        with contextlib.suppress(Exception):
            os.remove(lock_path)


def build_session_factory(cfg: SeedConfig):
    """
    Jeśli cfg.db_url jest podane -> tworzymy engine + sessionmaker.
    Jeśli nie -> próbujemy użyć ProjectSessionLocal z projektu.
    """
    if cfg.db_url:
        engine = create_engine(cfg.db_url, pool_pre_ping=True)
        return sessionmaker(bind=engine, autoflush=False, autocommit=False)
    if ProjectSessionLocal is None:
        raise RuntimeError(
            "Nie mogę zaimportować SessionLocal z database.py. Podaj --db-url albo dodaj database.py."
        )
    return ProjectSessionLocal


def fit_varchar(value: Any, max_len: int, fallback: str = "Unknown") -> str:
    s = ("" if value is None else str(value)).strip()
    if not s:
        s = fallback
    return s[:max_len]


def normalize_isbn(raw: Any) -> str:
    s = ("" if raw is None else str(raw)).strip()
    return ISBN_CLEAN_RE.sub("", s)


def pick_best_isbn(isbns: Any) -> Optional[str]:
    if not isbns:
        return None
    cleaned = [normalize_isbn(x) for x in isbns if x]
    cleaned = [x for x in cleaned if 9 <= len(x) <= 20]
    if not cleaned:
        return None
    for x in cleaned:
        if len(x) == 13:
            return x[:20]
    for x in cleaned:
        if len(x) == 10:
            return x[:20]
    return cleaned[0][:20]


def split_author_name(full: str) -> Tuple[str, str]:
    s = (full or "").strip()
    if not s:
        return ("Unknown", "Unknown")

    # "Nazwisko, Imię"
    if "," in s:
        last, first = [p.strip() for p in s.split(",", 1)]
        return (fit_varchar(first, 45, "Unknown"), fit_varchar(last, 45, "Unknown"))

    # "Imię Nazwisko"
    parts = [p for p in s.split() if p]
    if len(parts) == 1:
        return (fit_varchar(parts[0], 45, "Unknown"), "Unknown")
    first = " ".join(parts[:-1])
    last = parts[-1]
    return (fit_varchar(first, 45, "Unknown"), fit_varchar(last, 45, "Unknown"))


def fit_category_name(name: str, max_len: int = 45) -> str:
    raw = (name or "").strip()
    if not raw:
        return "General"
    if len(raw) <= max_len:
        return raw
    suffix = "-" + hashlib.sha1(raw.encode("utf-8")).hexdigest()[:6]
    base_len = max_len - len(suffix)
    if base_len <= 0:
        return suffix[-max_len:]
    return (raw[:base_len].rstrip() + suffix)


def http_get_with_retry(url: str, *, params: Dict[str, Any], headers: Dict[str, str], cfg: SeedConfig, result: SeedResult) -> Dict[str, Any]:
    last_exc: Optional[Exception] = None
    for attempt in range(cfg.max_retries + 1):
        try:
            result.api_requests += 1
            r = requests.get(url, params=params, headers=headers, timeout=cfg.timeout_s)
            if r.status_code in (429, 503):
                # rate limit / przeciążenie
                wait_s = cfg.backoff_base_s * (2 ** attempt) + random.random() * 0.2
                logger.warning("HTTP %s from Open Library, retry in %.2fs (attempt %d/%d)", r.status_code, wait_s, attempt + 1, cfg.max_retries)
                time.sleep(wait_s)
                continue
            r.raise_for_status()
            return r.json()
        except Exception as e:
            last_exc = e
            wait_s = cfg.backoff_base_s * (2 ** attempt) + random.random() * 0.2
            if attempt >= cfg.max_retries:
                break
            logger.warning("Request failed: %s; retry in %.2fs (attempt %d/%d)", repr(e), wait_s, attempt + 1, cfg.max_retries)
            time.sleep(wait_s)
    raise RuntimeError(f"Open Library request failed after retries: {last_exc!r}")


def openlibrary_search(q: str, *, page: int, cfg: SeedConfig, result: SeedResult) -> Dict[str, Any]:
    params = {
        "q": q,
        "fields": ",".join(cfg.fields),
        "limit": cfg.per_query_limit,
        "page": page,     # wg docs page starts at 1
        "lang": cfg.lang,
    }
    headers = {
        "User-Agent": cfg.user_agent,
        "Accept": "application/json",
    }
    return http_get_with_retry(OPENLIB_SEARCH_URL, params=params, headers=headers, cfg=cfg, result=result)


def db_scalar(db: Session, sql: str, params: Optional[Dict[str, Any]] = None) -> Any:
    res = db.execute(text(sql), params or {})
    row = res.fetchone()
    return None if not row else row[0]


def ensure_unknown_publisher(db: Session) -> int:
    # W schemacie publisher.name nie jest UNIQUE, więc robimy SELECT-then-INSERT.
    name = "Unknown Publisher"
    existing = db_scalar(db, "SELECT publisher_id FROM publisher WHERE name=:name LIMIT 1", {"name": name})
    if existing:
        return int(existing)
    db.execute(text("INSERT INTO publisher(name) VALUES (:name)"), {"name": name})
    # LAST_INSERT_ID per-connection; przy braku błędu możemy pobrać
    return int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)


def get_or_create_publisher(db: Session, name: str) -> int:
    name = fit_varchar(name, 45, "Unknown Publisher")
    existing = db_scalar(db, "SELECT publisher_id FROM publisher WHERE name=:name LIMIT 1", {"name": name})
    if existing:
        return int(existing)
    db.execute(text("INSERT INTO publisher(name) VALUES (:name)"), {"name": name})
    return int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)


def get_or_create_author(db: Session, first: str, last: str) -> int:
    first = fit_varchar(first, 45, "Unknown")
    last = fit_varchar(last, 45, "Unknown")
    existing = db_scalar(
        db,
        "SELECT author_id FROM author WHERE first_name=:f AND last_name=:l LIMIT 1",
        {"f": first, "l": last},
    )
    if existing:
        return int(existing)
    db.execute(
        text("INSERT INTO author(first_name, last_name) VALUES (:f, :l)"),
        {"f": first, "l": last},
    )
    return int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)


def upsert_category(db: Session, name: str) -> int:
    name = fit_category_name(name, 45)
    db.execute(
        text("""
            INSERT INTO category(name)
            VALUES (:name)
            ON DUPLICATE KEY UPDATE
                category_id = LAST_INSERT_ID(category_id)
        """),
        {"name": name},
    )
    return int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)


def upsert_book(db: Session, row: Dict[str, Any]) -> int:
    """
    Idempotentny insert po isbn (UNIQUE). Dodatkowo:
    - aktualizujemy wybrane pola na nowsze wartości
    - ustawiamy LAST_INSERT_ID(book_id) przy duplikacie, żeby odzyskać book_id
    """
    db.execute(
        text("""
            INSERT INTO book (title, publication_year, page, isbn, rental_rate, publisher_id)
            VALUES (:title, :publication_year, :page, :isbn, :rental_rate, :publisher_id)
            ON DUPLICATE KEY UPDATE
                title = VALUES(title),
                publication_year = VALUES(publication_year),
                page = VALUES(page),
                rental_rate = VALUES(rental_rate),
                publisher_id = VALUES(publisher_id),
                book_id = LAST_INSERT_ID(book_id)
        """),
        row,
    )
    return int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)


def insert_ignore_book_author(db: Session, book_id: int, author_id: int) -> None:
    db.execute(
        text("INSERT IGNORE INTO book_author(book_id, author_id) VALUES (:b, :a)"),
        {"b": book_id, "a": author_id},
    )


def insert_ignore_book_category(db: Session, book_id: int, category_id: int) -> None:
    # Kolumny to (category_id, book_id), ale jawnie podajemy nazwy.
    db.execute(
        text("INSERT IGNORE INTO book_category(category_id, book_id) VALUES (:c, :b)"),
        {"c": category_id, "b": book_id},
    )


def next_manual_id(db: Session, table: str, col: str) -> int:
    val = db_scalar(db, f"SELECT COALESCE(MAX({col}), 0) + 1 FROM {table}")
    return int(val or 1)


def ensure_libraries(db: Session, *, desired: int = 2) -> List[int]:
    """
    library.library_id i address.address_id NIE są AUTO_INCREMENT w Twoim schemacie,
    więc tworzymy je z MAX()+1 (bezpieczne tylko w single-run).
    """
    rows = db.execute(text("SELECT library_id FROM library")).fetchall()
    if rows:
        return [int(r[0]) for r in rows]

    library_ids: List[int] = []
    for i in range(desired):
        address_id = next_manual_id(db, "address", "address_id")
        db.execute(
            text("""
                INSERT INTO address(address_id, district, location, postal_code, street, house_number)
                VALUES (:id, :district, :location, :postal, :street, :house)
            """),
            {
                "id": address_id,
                "district": f"District {i+1}",
                "location": "City",
                "postal": f"00-0{i+1}0",
                "street": f"Main Street",
                "house": 10 + i,
            },
        )

        library_id = next_manual_id(db, "library", "library_id")
        db.execute(
            text("INSERT INTO library(library_id, name, address_id) VALUES (:id, :name, :addr)"),
            {"id": library_id, "name": f"Library {i+1}", "addr": address_id},
        )
        library_ids.append(library_id)

    return library_ids


def seed_readers_block(db: Session, result: SeedResult) -> None:
    """
    Minimalny seed czytelników: reader_type, address, reader, library_card.
    """
    # reader_type baseline
    existing = db.execute(text("SELECT type_id FROM reader_type")).fetchall()
    if not existing:
        for name, max_book, borrow_day, fine_per_day in [
            ("Student", 5, 21, Decimal("0.50")),
            ("Adult", 10, 30, Decimal("0.50")),
            ("Senior", 8, 30, Decimal("0.25")),
        ]:
            db.execute(
                text("""
                    INSERT INTO reader_type(name, max_book, borrow_day, fine_per_day)
                    VALUES (:name, :max_book, :borrow_day, :fine)
                """),
                {"name": name, "max_book": max_book, "borrow_day": borrow_day, "fine": str(fine_per_day)},
            )

    type_ids = [int(r[0]) for r in db.execute(text("SELECT type_id FROM reader_type")).fetchall()]
    if not type_ids:
        return

    # create few readers
    for i in range(10):
        address_id = next_manual_id(db, "address", "address_id")
        db.execute(
            text("""
                INSERT INTO address(address_id, district, location, postal_code, street, house_number)
                VALUES (:id, :district, :location, :postal, :street, :house)
            """),
            {
                "id": address_id,
                "district": f"ReaderDistrict {i+1}",
                "location": "City",
                "postal": f"01-{i:03d}",
                "street": "Reader Street",
                "house": 100 + i,
            },
        )

        type_id = random.choice(type_ids)
        db.execute(
            text("""
                INSERT INTO reader(first_name, last_name, email, phone, type_id, address_id)
                VALUES (:fn, :ln, :email, :phone, :type_id, :addr)
            """),
            {
                "fn": f"Reader{i+1}",
                "ln": "Test",
                "email": fit_varchar(f"reader{i+1}@example.com", 45),
                "phone": 500000000 + i,
                "type_id": type_id,
                "addr": address_id,
            },
        )
        reader_id = int(db_scalar(db, "SELECT LAST_INSERT_ID()") or 0)

        db.execute(
            text("""
                INSERT INTO library_card(status, created_at, reader_id)
                VALUES ('active', :created_at, :rid)
            """),
            {"created_at": dt.date.today().isoformat(), "rid": reader_id},
        )
        result.readers_created += 1


def write_log_row(db: Session, operation: str, detail: Dict[str, Any]) -> None:
    db.execute(
        text("INSERT INTO logs(operation, log_date, detail) VALUES (:op, :d, :detail)"),
        {
            "op": fit_varchar(operation, 200, "seed"),
            "d": dt.date.today().isoformat(),
            "detail": json.dumps(detail, ensure_ascii=False),
        },
    )


def seed_openlibrary(db: Session, cfg: SeedConfig) -> SeedResult:
    result = SeedResult()

    # bootstrap: Unknown Publisher
    unknown_pub_id = ensure_unknown_publisher(db)

    library_ids: List[int] = []
    if cfg.copies_per_book > 0:
        library_ids = ensure_libraries(db, desired=2)
        result.libraries_used = len(library_ids)

    if cfg.seed_readers:
        seed_readers_block(db, result)

    inserted_total = 0
    for q in cfg.queries:
        page = 1
        while inserted_total < cfg.max_books:
            logger.info("Query=%r page=%d", q, page)

            data = openlibrary_search(q, page=page, cfg=cfg, result=result)
            docs = data.get("docs") or []
            if not docs:
                break

            for doc in docs:
                if inserted_total >= cfg.max_books:
                    break

                result.docs_seen += 1
                result.books_attempted += 1

                isbn = pick_best_isbn(doc.get("isbn"))
                if not isbn:
                    result.books_skipped_no_isbn += 1
                    continue

                title = fit_varchar(doc.get("title"), 45, "Untitled")
                year = doc.get("first_publish_year")
                if year is None:
                    years = doc.get("publish_year") or []
                    year = min(years) if years else None
                publication_year = int(year) if year else DEFAULT_PUBLICATION_YEAR

                page_val = doc.get("number_of_pages_median")
                page = int(page_val) if isinstance(page_val, (int, float)) else None

                publishers = doc.get("publisher") or []
                publisher_name = publishers[0] if publishers else "Unknown Publisher"
                publisher_id = get_or_create_publisher(db, publisher_name)

                book_id = upsert_book(db, {
                    "title": title,
                    "publication_year": publication_year,
                    "page": page,
                    "isbn": isbn,
                    "rental_rate": str(DEFAULT_RENTAL_RATE),
                    "publisher_id": publisher_id or unknown_pub_id,
                })
                result.books_upserted += 1

                # authors
                for a in (doc.get("author_name") or [])[:5]:
                    first, last = split_author_name(str(a))
                    author_id = get_or_create_author(db, first, last)
                    insert_ignore_book_author(db, book_id, author_id)
                    result.authors_linked += 1

                # categories
                for s in (doc.get("subject") or [])[:3]:
                    category_id = upsert_category(db, str(s))
                    insert_ignore_book_category(db, book_id, category_id)
                    result.categories_linked += 1

                # copies
                if cfg.copies_per_book > 0 and library_ids:
                    for _ in range(cfg.copies_per_book):
                        lib_id = random.choice(library_ids)
                        db.execute(
                            text("""
                                INSERT INTO copy(status, book_id, library_id)
                                VALUES ('available', :book_id, :lib_id)
                            """),
                            {"book_id": book_id, "lib_id": lib_id},
                        )
                        result.copies_created += 1

                inserted_total += 1

            # commit / rollback batch
            if cfg.dry_run:
                db.rollback()
                logger.info("Dry-run: rollback batch.")
            else:
                db.commit()

            page += 1

            # delay (rate limiting)
            if cfg.delay > 0:
                time.sleep(cfg.delay)

            if inserted_total >= cfg.max_books:
                break

    return result


def parse_args(argv: Optional[List[str]] = None) -> Tuple[SeedConfig, bool]:
    p = argparse.ArgumentParser(description="Seed librarydb from Open Library /search.json")
    p.add_argument("--db-url", default=os.getenv("DATABASE_URL"), help="SQLAlchemy DB URL (optional if database.SessionLocal exists)")
    p.add_argument("--user-agent", default=os.getenv("OPENLIB_USER_AGENT", SeedConfig.user_agent), help="Open Library User-Agent (include contact)")
    p.add_argument("--fields", default=os.getenv("OPENLIB_FIELDS", ",".join(DEFAULT_FIELDS)), help="Comma-separated fields list")
    p.add_argument("--lang", default=os.getenv("OPENLIB_LANG", "pl"), help="Language hint (ISO 639-1)")
    p.add_argument("--query", action="append", help="Search query; can be repeated")
    p.add_argument("--max-books", type=int, default=int(os.getenv("SEED_MAX_BOOKS", "50")))
    p.add_argument("--per-query-limit", type=int, default=int(os.getenv("SEED_PER_QUERY_LIMIT", "20")))
    p.add_argument("--delay", type=float, default=float(os.getenv("SEED_DELAY", "0.4")))
    p.add_argument("--copies-per-book", type=int, default=int(os.getenv("SEED_COPIES_PER_BOOK", "0")))
    p.add_argument("--seed-readers", action="store_true", help="Also create reader_type, readers, cards")
    p.add_argument("--dry-run", action="store_true", help="Execute but rollback (no persistent changes)")
    p.add_argument("--lock-file", default=os.getenv("SEED_LOCK_FILE", LOCKFILE_DEFAULT))
    p.add_argument("--serve", action="store_true", help="Run FastAPI app (requires fastapi+uvicorn)")
    p.add_argument("--verbose", action="store_true")

    args = p.parse_args(argv)

    cfg = SeedConfig(
        db_url=args.db_url,
        user_agent=args.user_agent,
        fields=[f.strip() for f in args.fields.split(",") if f.strip()],
        queries=args.query if args.query else SeedConfig().queries,
        max_books=args.max_books,
        per_query_limit=args.per_query_limit,
        delay=args.delay,
        lang=args.lang,
        copies_per_book=args.copies_per_book,
        seed_readers=args.seed_readers,
        dry_run=args.dry_run,
        lock_file=args.lock_file,
    )
    return cfg, bool(args.verbose), bool(args.serve)


# FastAPI optional trigger (import-safe)
if FastAPI is not None:
    app = FastAPI(title="librarydb seeder")

    SessionFactoryForAPI = None

    def get_db() -> Iterable[Session]:
        # Lazy init: prefer DATABASE_URL if provided at runtime
        nonlocal_factory = globals().get("SessionFactoryForAPI")
        if nonlocal_factory is None:
            cfg = SeedConfig(db_url=os.getenv("DATABASE_URL"))
            globals()["SessionFactoryForAPI"] = build_session_factory(cfg)
            nonlocal_factory = globals()["SessionFactoryForAPI"]

        db = nonlocal_factory()
        try:
            yield db
        finally:
            db.close()

    @app.post("/seed/openlibrary")
    def seed_endpoint(payload: Dict[str, Any], db: Session = Depends(get_db)):  # type: ignore
        try:
            cfg = SeedConfig(
                db_url=os.getenv("DATABASE_URL"),
                user_agent=payload.get("user_agent") or os.getenv("OPENLIB_USER_AGENT", SeedConfig.user_agent),
                fields=payload.get("fields") or list(DEFAULT_FIELDS),
                queries=payload.get("queries") or ["polska historia", "fantasy"],
                max_books=int(payload.get("max_books") or 50),
                per_query_limit=int(payload.get("per_query_limit") or 20),
                delay=float(payload.get("delay") or 0.4),
                lang=payload.get("lang") or "pl",
                copies_per_book=int(payload.get("copies_per_book") or 0),
                seed_readers=bool(payload.get("seed_readers") or False),
                dry_run=bool(payload.get("dry_run") or False),
            )
            with acquire_lock(payload.get("lock_file") or LOCKFILE_DEFAULT):
                if not cfg.dry_run:
                    write_log_row(db, "seed_openlibrary_start", {"cfg": dataclasses.asdict(cfg)})
                    db.commit()
                result = seed_openlibrary(db, cfg)
                if not cfg.dry_run:
                    write_log_row(db, "seed_openlibrary_done", {"result": result.to_dict()})
                    db.commit()
            return {"message": "ok", "result": result.to_dict()}
        except Exception as e:
            with contextlib.suppress(Exception):
                db.rollback()
            raise HTTPException(status_code=500, detail=str(e))  # type: ignore


def main(argv: Optional[List[str]] = None) -> int:
    cfg, verbose, serve = parse_args(argv)
    setup_logging(verbose)

    if serve:
        if FastAPI is None:
            raise RuntimeError("fastapi is not installed")
        # Nie uruchamiamy uvicorn programowo, bo w projektach zwykle używa się CLI.
        print("Run: uvicorn seed:app --reload")
        return 0

    session_factory = build_session_factory(cfg)

    with acquire_lock(cfg.lock_file):
        with session_factory() as db:
            try:
                if not cfg.dry_run:
                    write_log_row(db, "seed_openlibrary_start", {"cfg": dataclasses.asdict(cfg)})
                    db.commit()

                res = seed_openlibrary(db, cfg)

                if not cfg.dry_run:
                    write_log_row(db, "seed_openlibrary_done", {"result": res.to_dict()})
                    db.commit()

                print(json.dumps(res.to_dict(), ensure_ascii=False, indent=2))
                return 0
            except Exception as e:
                db.rollback()
                logger.exception("Seed failed")
                print(f"ERROR: {e}", file=sys.stderr)
                return 1


if __name__ == "__main__":
    raise SystemExit(main())
