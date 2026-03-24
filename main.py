from fastapi import FastAPI, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import text

from database import SessionLocal

app = FastAPI()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/books")
def create_book(book: dict, db: Session = Depends(get_db)):

    # 1. Dodaj książkę
    result = db.execute(text("""
        INSERT INTO book (title, publication_year, pages, isbn, rental_rate, publisher_id)
        VALUES (:title, :publication_year, :pages, :isbn, :rental_rate, :publisher_id)
    """), book)

    db.commit()
    book_id = result.lastrowid

    # 2. Dodaj autorów
    for author_id in book.get("author_ids", []):
        db.execute(text("""
            INSERT INTO book_author (book_id, author_id)
            VALUES (:book_id, :author_id)
        """), {
            "book_id": book_id,
            "author_id": author_id
        })

    # 3. Dodaj kategorie
    for category_id in book.get("category_ids", []):
        db.execute(text("""
            INSERT INTO book_category (book_id, category_id)
            VALUES (:book_id, :category_id)
        """), {
            "book_id": book_id,
            "category_id": category_id
        })

    db.commit()

    return {
        "message": "Book created",
        "book_id": book_id
    }

@app.get("/books")
def get_books(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM book"))
    books = result.fetchall()

    return [dict(row._mapping) for row in books]

@app.get("/books")
def get_books(db: Session = Depends(get_db)):
    # Pobierz książki wraz z publisherem
    books_result = db.execute(text("""
        SELECT b.book_id, b.title, b.publication_year, b.pages, b.isbn, b.rental_rate,
               p.publisher_id, p.name AS publisher_name
        FROM book b
        JOIN publisher p ON b.publisher_id = p.publisher_id
    """))
    books = []
    for row in books_result:
        book_id = row.book_id

        # Pobierz autorów dla książki
        authors_result = db.execute(text("""
            SELECT a.author_id, a.first_name, a.last_name
            FROM author a
            JOIN book_author ba ON a.author_id = ba.author_id
            WHERE ba.book_id = :book_id
        """), {"book_id": book_id})
        authors = [dict(a._mapping) for a in authors_result]

        # Pobierz kategorie dla książki
        categories_result = db.execute(text("""
            SELECT c.category_id, c.name
            FROM category c
            JOIN book_category bc ON c.category_id = bc.category_id
            WHERE bc.book_id = :book_id
        """), {"book_id": book_id})
        categories = [dict(c._mapping) for c in categories_result]

        books.append({
            "book_id": book_id,
            "title": row.title,
            "publication_year": row.publication_year,
            "pages": row.pages,
            "isbn": row.isbn,
            "rental_rate": float(row.rental_rate),
            "publisher": {
                "publisher_id": row.publisher_id,
                "name": row.publisher_name
            },
            "authors": authors,
            "categories": categories
        })

    return books

@app.post("/authors")
def create_author(author: dict, db: Session = Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO author (first_name, last_name)
        VALUES (:first_name, :last_name)
    """), author)

    db.commit()

    return {
        "message": "Author created",
        "author_id": result.lastrowid
    }

@app.get("/authors")
def get_authors(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM author"))
    return [dict(r._mapping) for r in result]

@app.post("/publishers")
def create_publisher(publisher: dict, db: Session = Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO publisher (name)
        VALUES (:name)
    """), publisher)

    db.commit()

    return {
        "message": "Publisher created",
        "publisher_id": result.lastrowid
    }

@app.get("/publishers")
def get_publishers(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM publisher"))
    return [dict(r._mapping) for r in result]

@app.post("/categories")
def create_category(category: dict, db: Session = Depends(get_db)):
    result = db.execute(text("""
        INSERT INTO category (name)
        VALUES (:name)
    """), category)

    db.commit()

    return {
        "message": "Category created",
        "category_id": result.lastrowid
    }

@app.get("/categories")
def get_categories(db: Session = Depends(get_db)):
    result = db.execute(text("SELECT * FROM category"))
    return [dict(r._mapping) for r in result]