from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload

from database import SessionLocal, create_db_and_tables
from database import (
    AuthorCreate,
    Author,
    AuthorDetailOut,
    Book,
    BookCreate,
    BookDetailOut,
    Category,
    CategoryCreate,
    CategoryDetailOut,
    PublisherCreate,
    Publisher,
    PublisherDetailOut,
)

app = FastAPI()


@app.on_event("startup")
def on_startup() -> None:
    create_db_and_tables()




def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.post("/books")
def create_book(book: BookCreate, db: Session = Depends(get_db)):

    book_data = book.model_dump(exclude={"author_ids", "category_ids"})
    new_book = Book(**book_data)

    if book.author_ids:
        authors = db.query(Author).filter(Author.author_id.in_(book.author_ids)).all()
        new_book.author = authors

    if book.category_ids:
        categories = db.query(Category).filter(Category.category_id.in_(book.category_ids)).all()
        new_book.category = categories

    db.add(new_book)
    db.commit()
    db.refresh(new_book)

    return {
        "message": "Book created",
        "book_id": new_book.book_id
    }

@app.get("/books", response_model=list[BookDetailOut])
def get_books(db: Session = Depends(get_db), 
              title: str = None, 
              author_first_name: str = None, 
              author_last_name: str = None, 
              publisher_name: str = None, 
              category_name: str = None):
    books_result = (
        db.query(Book)
        .options(
            selectinload(Book.publisher),
            selectinload(Book.author),
            selectinload(Book.category),
        )
        .all()
    )
    if title:
        books_result = books_result.filter(Book.title.ilike(f"%{title}%"))
    if author_first_name:
        books_result = books_result.filter(Author.first_name.ilike(f"%{author_first_name}%"))
    if author_last_name:
        books_result = books_result.filter(Author.last_name.ilike(f"%{author_last_name}%"))
    if publisher_name:
        books_result = books_result.filter(Publisher.name.ilike(f"%{publisher_name}%"))
    if category_name:
        books_result = books_result.filter(Category.name.ilike(f"%{category_name}%"))
    return books_result


@app.post("/authors")
def create_author(author: AuthorCreate, db: Session = Depends(get_db)):
    new_author = Author(**author.model_dump())
    db.add(new_author)
    db.commit()
    db.refresh(new_author)

    return {
        "message": "Author created",
        "author_id": new_author.author_id
    }

@app.get("/authors", response_model=list[AuthorDetailOut])
def get_authors(db: Session = Depends(get_db), 
                first_name: str = None, 
                last_name: str = None):
    authors_result = db.query(Author).options(selectinload(Author.book)).all()
    if first_name:
        authors_result = authors_result.filter(Author.first_name.ilike(f"%{first_name}%"))
    if last_name:
        authors_result = authors_result.filter(Author.last_name.ilike(f"%{last_name}%"))

    return authors_result
        
    

@app.post("/publishers")
def create_publisher(publisher: PublisherCreate, db: Session = Depends(get_db)):
    new_publisher = Publisher(**publisher.model_dump())
    db.add(new_publisher)
    db.commit()
    db.refresh(new_publisher)

    return {
        "message": "Publisher created",
        "publisher_id": new_publisher.publisher_id
    }

@app.get("/publishers", response_model=list[PublisherDetailOut])
def get_publishers(db: Session = Depends(get_db)):
    publishers = db.query(Publisher).options(selectinload(Publisher.book)).all()
    return [
        {
            "publisher_id": publisher.publisher_id,
            "name": publisher.name,
            "book_title": [book.title for book in publisher.book],
        }
        for publisher in publishers
    ]

@app.post("/categories")
def create_category(category: CategoryCreate, db: Session = Depends(get_db)):
    new_category = Category(**category.model_dump())
    db.add(new_category)
    db.commit()
    db.refresh(new_category)

    return {
        "message": "Category created",
        "category_id": new_category.category_id
    }

@app.get("/categories", response_model=list[CategoryDetailOut])
def get_categories(db: Session = Depends(get_db)):
    categories = db.query(Category).options(selectinload(Category.book)).all()
    return [
        {
            "category_id": category.category_id,
            "name": category.name,
            "book_title": [book.title for book in category.book],
        }
        for category in categories
    ]