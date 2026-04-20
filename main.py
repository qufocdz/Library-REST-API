from fastapi import FastAPI, Depends
from sqlalchemy.orm import Session
from sqlalchemy.orm import selectinload
from sqlalchemy import or_

from datetime import date, timedelta
from fastapi import HTTPException
from database import (
    create_db_and_tables,
    SessionLocal,
    Book,
    BookCreate,
    BookDetailOut,
    Author,
    AuthorCreate,
    AuthorDetailOut,
    Publisher,
    PublisherCreate,
    PublisherDetailOut,
    Category,
    CategoryCreate,
    CategoryDetailOut,
    Copy,
    CopyStatus,
    Rental,
    RentalStatus,
    LibraryCard,
    LibraryCardStatus,
    Reader,
    ReaderType,
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
              category_name: str = None,
              limit: int = 100
              ):
    
    query = (
        db.query(Book)
        .options(
            selectinload(Book.publisher),
            selectinload(Book.author),
            selectinload(Book.category),
        )
    )

    if title:
        query = query.filter(Book.title.ilike(f"%{title}%"))
    if author_first_name:
        query = query.filter(Author.first_name.ilike(f"%{author_first_name}%"))
    if author_last_name:
        query = query.filter(Author.last_name.ilike(f"%{author_last_name}%"))
    if publisher_name:
        query = query.filter(Publisher.name.ilike(f"%{publisher_name}%"))
    if category_name:
        query = query.filter(Category.name.ilike(f"%{category_name}%"))

    query = query.limit(limit)
    return query.all()



@app.get("/books/search", response_model=list[BookDetailOut])
def search_books(
    db: Session = Depends(get_db),
    title: str | None = None,
    category_id: int | None = None,
    category_name: str | None = None,
    author_first_name: str | None = None,
    author_last_name: str | None = None,
    publisher_name: str | None = None,
    q: str | None = None,
    library_id: int | None = None,          
    available_only: bool = False             
):
    query = (
        db.query(Book)
        .options(
            selectinload(Book.publisher),
            selectinload(Book.author),
            selectinload(Book.category),
            selectinload(Book.copy)
        )
    )

    

    # --- FILTRY ---
    if title:
        query = query.filter(Book.title.ilike(f"%{title}%"))

    if category_id:
        query = query.filter(Category.category_id == category_id)

    if category_name:
        query = query.filter(Category.name.ilike(f"%{category_name}%"))

    if author_first_name:
        query = query.filter(Author.first_name.ilike(f"%{author_first_name}%"))

    if author_last_name:
        query = query.filter(Author.last_name.ilike(f"%{author_last_name}%"))

    if publisher_name:
        query = query.filter(Publisher.name.ilike(f"%{publisher_name}%"))

    # --- GLOBAL SEARCH ---
    if q:
        query = query.outerjoin(Book.publisher)\
                    .outerjoin(Book.author)\
                    .outerjoin(Book.category)

        query = query.filter(
            or_(
                Book.title.ilike(f"%{q}%"),
                Book.isbn.ilike(f"%{q}%"),
                Publisher.name.ilike(f"%{q}%"),
                Author.first_name.ilike(f"%{q}%"),
                Author.last_name.ilike(f"%{q}%"),
                Category.name.ilike(f"%{q}%"),
            )
        )

    # --- DOSTĘPNOŚĆ W BIBLIOTECE ---
    if library_id:
        query = query.filter(Copy.library_id == library_id)

    if library_id or available_only:
        subquery = db.query(Copy.book_id)

        if library_id:
            subquery = subquery.filter(Copy.library_id == library_id)

        if available_only:
            subquery = subquery.filter(Copy.status == CopyStatus.AVAILABLE)

        query = query.filter(Book.book_id.in_(subquery))

    return query.all()



@app.get("/libraries/{library_id}/books/{isbn}/copies")
def get_book_copies_in_library(
    library_id: int,
    isbn: str,
    db: Session = Depends(get_db),
):
    book = db.query(Book).filter(Book.isbn == isbn).first()

    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    copy_ids = (
        db.query(Copy.copy_id)
        .filter(
            Copy.book_id == book.book_id,
            Copy.library_id == library_id
        )
        .all()
    )

    # SQLAlchemy zwraca listę tuple [(1,), (2,), ...]
    copy_ids = [c[0] for c in copy_ids]

    return {
        "book_id": book.book_id,
        "isbn": isbn,
        "library_id": library_id,
        "has_any_copy_in_library": len(copy_ids) > 0,
        "copy_ids": copy_ids
    }


@app.get("/rentals")
def get_rentals(db: Session = Depends(get_db)):
    return db.query(Rental).all()



@app.post("/rentals")
def rent_book(
    isbn: str,
    library_id: int,
    card_id: int,
    db: Session = Depends(get_db)
):
    # 1. książka
    book = db.query(Book).filter(Book.isbn == isbn).first()
    if not book:
        raise HTTPException(status_code=404, detail="Book not found")

    # 2. karta
    card = db.query(LibraryCard).filter(LibraryCard.card_id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Library card not found")

    if card.status != LibraryCardStatus.ACTIVE:
        raise HTTPException(status_code=400, detail="Library card is not active")

    # 3. reader + typ czytelnika
    reader = db.query(Reader).filter(Reader.reader_id == card.reader_id).first()
    reader_type = db.query(ReaderType).filter(ReaderType.type_id == reader.type_id).first()

    # 4. aktualnie aktywne wypożyczenia
    active_rentals_count = (
        db.query(Rental)
        .join(LibraryCard)
        .filter(
            LibraryCard.reader_id == reader.reader_id,
            Rental.status == RentalStatus.ACTIVE
        )
        .count()
    )

    # 5. limit książek
    if active_rentals_count >= reader_type.max_books:
        raise HTTPException(
            status_code=400,
            detail=f"Limit reached: max {reader_type.max_books} books allowed"
        )

    # 6. dostępna kopia
    copy = (
        db.query(Copy)
        .filter(
            Copy.book_id == book.book_id,
            Copy.library_id == library_id,
            Copy.status == CopyStatus.AVAILABLE
        )
        .first()
    )

    if not copy:
        raise HTTPException(status_code=400, detail="No available copies")

    # 7. terminy z typu czytelnika
    today = date.today()
    due_date = today + timedelta(days=reader_type.borrow_days)

    # 8. wypożyczenie
    rental = Rental(
        copy_id=copy.copy_id,
        card_id=card.card_id,
        rental_date=today,
        due_date=due_date,
        status=RentalStatus.ACTIVE,
        rental_rate=copy.book.rental_rate
    )

    # 9. zmiana statusu kopii
    copy.status = CopyStatus.BORROWED

    db.add(rental)
    db.commit()
    db.refresh(rental)

    return {
        "message": "Book rented successfully",
        "rental_id": rental.rental_id,
        "due_date": rental.due_date,
        "max_books_allowed": reader_type.max_books,
        "currently_rented": active_rentals_count + 1
    }

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

    query = db.query(Author).options(selectinload(Author.book))

    if first_name:
        query = query.filter(Author.first_name.ilike(f"%{first_name}%"))

    if last_name:
        query = query.filter(Author.last_name.ilike(f"%{last_name}%"))

    authors = query.all()

    return [
        {
            "author_id": a.author_id,
            "first_name": a.first_name,
            "last_name": a.last_name,
            "book_title": [b.title for b in a.book],
        }
        for a in authors
    ]
        
    

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