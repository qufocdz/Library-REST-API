from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy import text
from database import SessionLocal
from datetime import date, timedelta

app = FastAPI()


def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


# CREATE BOOK
@app.post("/books")
def create_book(book: dict, db=Depends(get_db)):

    result = db.execute(text("""
        INSERT INTO book (title, publication_year, pages, isbn, rental_rate, publisher_id)
        VALUES (:title, :year, :pages, :isbn, :rate, :publisher_id)
    """), {
        "title": book["title"],
        "year": book["publication_year"],
        "pages": book.get("pages"),
        "isbn": book["isbn"],
        "rate": book["rental_rate"],
        "publisher_id": book["publisher_id"]
    })

    book_id = result.lastrowid

    # autorzy
    for author_id in book.get("author_ids", []):
        db.execute(text("""
            INSERT INTO book_author (book_id, author_id)
            VALUES (:book_id, :author_id)
        """), {"book_id": book_id, "author_id": author_id})

    # kategorie
    for category_id in book.get("category_ids", []):
        db.execute(text("""
            INSERT INTO book_category (book_id, category_id)
            VALUES (:book_id, :category_id)
        """), {"book_id": book_id, "category_id": category_id})

    db.commit()

    return {"message": "Book created", "book_id": book_id}

# GET BOOKS
@app.get("/books")
def get_books(db=Depends(get_db), limit: int = 100):

    query = """
    SELECT 
        b.book_id,
        b.title,
        b.isbn,
        p.name AS publisher,

        GROUP_CONCAT(DISTINCT CONCAT(a.first_name, ' ', a.last_name)) AS authors,
        GROUP_CONCAT(DISTINCT c.name) AS categories

    FROM book b
    LEFT JOIN publisher p ON b.publisher_id = p.publisher_id

    LEFT JOIN book_author ba ON b.book_id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.author_id

    LEFT JOIN book_category bc ON b.book_id = bc.book_id
    LEFT JOIN category c ON bc.category_id = c.category_id

    GROUP BY b.book_id
    LIMIT :limit
    """

    rows = db.execute(text(query), {"limit": limit}).fetchall()

    result = []

    for row in rows:
        result.append({
            "book_id": row.book_id,
            "title": row.title,
            "isbn": row.isbn,
            "publisher": row.publisher,
            "authors": row.authors.split(",") if row.authors else [],
            "categories": row.categories.split(",") if row.categories else []
        })

    return result


# SEARCH
@app.get("/books/search")
def search_books(
    db=Depends(get_db),
    q: str = None,
    title: str = None,
    category_id: int = None,
    category_name: str = None,
    author_first_name: str = None,
    author_last_name: str = None,
    publisher_name: str = None,
    library_id: int = None,
    available_only: bool = False
):

    query = """
    SELECT 
        b.book_id,
        b.title,
        b.isbn,
        p.name AS publisher,

        GROUP_CONCAT(DISTINCT CONCAT(a.first_name, ' ', a.last_name)) AS authors,
        GROUP_CONCAT(DISTINCT c.name) AS categories

    FROM book b

    LEFT JOIN publisher p ON b.publisher_id = p.publisher_id

    LEFT JOIN book_author ba ON b.book_id = ba.book_id
    LEFT JOIN author a ON ba.author_id = a.author_id

    LEFT JOIN book_category bc ON b.book_id = bc.book_id
    LEFT JOIN category c ON bc.category_id = c.category_id

    LEFT JOIN copy cp ON cp.book_id = b.book_id

    WHERE 1=1
    """

    params = {}

    # filtry
    if title:
        query += " AND b.title LIKE :title"
        params["title"] = f"%{title}%"

    if category_id:
        query += " AND c.category_id = :cid"
        params["cid"] = category_id

    if category_name:
        query += " AND c.name LIKE :cname"
        params["cname"] = f"%{category_name}%"

    if author_first_name:
        query += " AND a.first_name LIKE :afn"
        params["afn"] = f"%{author_first_name}%"

    if author_last_name:
        query += " AND a.last_name LIKE :aln"
        params["aln"] = f"%{author_last_name}%"

    if publisher_name:
        query += " AND p.name LIKE :pname"
        params["pname"] = f"%{publisher_name}%"

    # wyszukanie wszędzie
    if q:
        query += """
        AND (
            b.title LIKE :q OR
            b.isbn LIKE :q OR
            p.name LIKE :q OR
            a.first_name LIKE :q OR
            a.last_name LIKE :q OR
            c.name LIKE :q
        )
        """
        params["q"] = f"%{q}%"

    # dostępność w bibliotece
    if library_id:
        query += " AND cp.library_id = :lib"
        params["lib"] = library_id

    if available_only:
        query += " AND cp.status = 'available'"

    query += " GROUP BY b.book_id"

    rows = db.execute(text(query), params).fetchall()

    result = []

    for row in rows:
        result.append({
            "book_id": row.book_id,
            "title": row.title,
            "isbn": row.isbn,
            "publisher": row.publisher,
            "authors": row.authors.split(",") if row.authors else [],
            "categories": row.categories.split(",") if row.categories else []
        })

    return result


# COPIES IN LIBRARY
@app.get("/libraries/{library_id}/books/{isbn}/copies")
def get_copies(library_id: int, isbn: str, db=Depends(get_db)):

    book = db.execute(text("""
        SELECT book_id FROM book WHERE isbn = :isbn
    """), {"isbn": isbn}).fetchone()

    if not book:
        raise HTTPException(404, "Book not found")

    copies = db.execute(text("""
        SELECT copy_id
        FROM copy
        WHERE book_id = :book_id AND library_id = :library_id
    """), {
        "book_id": book.book_id,
        "library_id": library_id
    }).fetchall()

    copy_ids = [c.copy_id for c in copies]

    return {
        "book_id": book.book_id,
        "copy_ids": copy_ids
    }


# RENT BOOK
@app.post("/rentals")
def rent_book(isbn: str, library_id: int, card_id: int, db=Depends(get_db)):

    # czy jest książka
    book = db.execute(text("SELECT * FROM book WHERE isbn=:isbn"),
                      {"isbn": isbn}).fetchone()
    if not book:
        raise HTTPException(404, "Book not found")

    # czy jest aktywna karta
    card = db.execute(text("SELECT * FROM library_card WHERE card_id=:id"),
                      {"id": card_id}).fetchone()
    if not card:
        raise HTTPException(404, "Card not found")

    if card.status != "active":
        raise HTTPException(400, "Card inactive")

    # sprawdzenie typu czytelnika
    reader = db.execute(text("SELECT * FROM reader WHERE reader_id=:id"),
                        {"id": card.reader_id}).fetchone()

    rtype = db.execute(text("""
        SELECT * FROM reader_type WHERE type_id=:id
    """), {"id": reader.type_id}).fetchone()

    # zebranie jego wypożyczeń
    count = db.execute(text("""
        SELECT COUNT(*) as cnt
        FROM rental r
        JOIN library_card c ON r.card_id = c.card_id
        WHERE c.reader_id = :rid AND r.status='active'
    """), {"rid": reader.reader_id}).fetchone().cnt

    if count >= rtype.max_books:
        raise HTTPException(400, "Limit reached")

    # wybór dostępnej kopii
    copy = db.execute(text("""
        SELECT * FROM copy
        WHERE book_id=:book_id
        AND library_id=:lib
        AND status='available'
        LIMIT 1
    """), {
        "book_id": book.book_id,
        "lib": library_id
    }).fetchone()

    if not copy:
        raise HTTPException(400, "No copies")

    # data oddania zgodna z typem użytkownika
    today = date.today()
    due = today + timedelta(days=rtype.borrow_days)

    # dodanie wypożyczenia
    result = db.execute(text("""
        INSERT INTO rental (status, rental_date, due_date, copy_id, card_id)
        VALUES ('active', :today, :due, :copy_id, :card_id)
    """), {
        "today": today,
        "due": due,
        "copy_id": copy.copy_id,
        "card_id": card_id
    })

    # wypożyczenie kopii
    db.execute(text("""
        UPDATE copy SET status='borrowed'
        WHERE copy_id=:id
    """), {"id": copy.copy_id})

    db.commit()

    return {
        "message": "Book rented",
        "rental_id": result.lastrowid,
        "due_date": due
    }

# GET RENTALS
@app.get("/rentals")
def get_rentals(db=Depends(get_db)):

    result = db.execute(text("""
        SELECT r.rental_id, r.status, r.rental_date, r.due_date,
               r.return_date, r.copy_id, r.card_id
        FROM rental r
    """)).fetchall()

    return [dict(row._mapping) for row in result]


# CREATE AUTHOR
@app.post("/authors")
def create_author(author: dict, db=Depends(get_db)):

    result = db.execute(text("""
        INSERT INTO author (first_name, last_name)
        VALUES (:first_name, :last_name)
    """), author)

    db.commit()

    return {
        "message": "Author created",
        "author_id": result.lastrowid
    }


# GET AUTHORS + BOOKS
@app.get("/authors")
def get_authors(
    db=Depends(get_db),
    first_name: str = None,
    last_name: str = None
):

    query = """
        SELECT a.author_id, a.first_name, a.last_name,
               b.title
        FROM author a
        LEFT JOIN book_author ba ON a.author_id = ba.author_id
        LEFT JOIN book b ON ba.book_id = b.book_id
        WHERE 1=1
    """

    params = {}

    if first_name:
        query += " AND a.first_name LIKE :fn"
        params["fn"] = f"%{first_name}%"

    if last_name:
        query += " AND a.last_name LIKE :ln"
        params["ln"] = f"%{last_name}%"

    rows = db.execute(text(query), params).fetchall()

    # grupowanie (bo JOIN duplikuje rekordy)
    authors = {}

    for row in rows:
        a_id = row.author_id

        if a_id not in authors:
            authors[a_id] = {
                "author_id": a_id,
                "first_name": row.first_name,
                "last_name": row.last_name,
                "book_title": []
            }

        if row.title:
            authors[a_id]["book_title"].append(row.title)

    return list(authors.values())


# CREATE PUBLISHER
@app.post("/publishers")
def create_publisher(publisher: dict, db=Depends(get_db)):

    result = db.execute(text("""
        INSERT INTO publisher (name)
        VALUES (:name)
    """), publisher)

    db.commit()

    return {
        "message": "Publisher created",
        "publisher_id": result.lastrowid
    }


# GET PUBLISHERS + BOOKS
@app.get("/publishers")
def get_publishers(db=Depends(get_db)):

    rows = db.execute(text("""
        SELECT p.publisher_id, p.name, b.title
        FROM publisher p
        LEFT JOIN book b ON p.publisher_id = b.publisher_id
    """)).fetchall()

    publishers = {}

    for row in rows:
        p_id = row.publisher_id

        if p_id not in publishers:
            publishers[p_id] = {
                "publisher_id": p_id,
                "name": row.name,
                "book_title": []
            }

        if row.title:
            publishers[p_id]["book_title"].append(row.title)

    return list(publishers.values())


# CREATE CATEGORY
@app.post("/categories")
def create_category(category: dict, db=Depends(get_db)):

    try:
        result = db.execute(text("""
            INSERT INTO category (name)
            VALUES (:name)
        """), category)

        db.commit()

        return {
            "message": "Category created",
            "category_id": result.lastrowid
        }

    except Exception:
        raise HTTPException(400, "Category already exists")


# GET CATEGORIES + BOOKS
@app.get("/categories")
def get_categories(db=Depends(get_db)):

    rows = db.execute(text("""
        SELECT c.category_id, c.name, b.title
        FROM category c
        LEFT JOIN book_category bc ON c.category_id = bc.category_id
        LEFT JOIN book b ON bc.book_id = b.book_id
    """)).fetchall()

    categories = {}

    for row in rows:
        c_id = row.category_id

        if c_id not in categories:
            categories[c_id] = {
                "category_id": c_id,
                "name": row.name,
                "book_title": []
            }

        if row.title:
            categories[c_id]["book_title"].append(row.title)

    return list(categories.values())