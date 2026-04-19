import enum
import os
from datetime import date
from decimal import Decimal

from dotenv import load_dotenv
from pydantic import BaseModel, ConfigDict
from sqlalchemy import Column, Enum as SAEnum, Numeric, Text, create_engine
from sqlalchemy.engine import URL
from sqlalchemy.orm import sessionmaker
from sqlmodel import Field, Relationship, SQLModel

load_dotenv()





DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = (os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")

SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="mysql+pymysql",
    username=DB_USER or None,
    password=DB_PASSWORD or None,
    host=DB_HOST or None,
    port=DB_PORT,
    database=DB_NAME or None,
)

engine = create_engine(SQLALCHEMY_DATABASE_URL, echo=True)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class CopyStatus(str, enum.Enum):
    AVAILABLE = "available"
    BORROWED = "borrowed"
    LOST = "lost"
    DAMAGED = "damaged"


class LibraryCardStatus(str, enum.Enum):
    ACTIVE = "active"
    SUSPENDED = "suspended"
    BLOCKED = "blocked"


class RentalStatus(str, enum.Enum):
    ACTIVE = "active"
    OVERDUE = "overdue"
    RETURNED = "returned"
    CANCELLED = "cancelled"
    LOST = "lost"
    DAMAGED = "damaged"


class InternalRentalStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    REJECTED = "rejected"
    SHIPPED = "shipped"
    RECEIVED = "received"
    ACTIVE = "active"
    RETURNED_TO_LIBRARY = "returned_to_library"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BookAuthor(SQLModel, table=True):
    __tablename__ = "book_author"

    book_id: int = Field(foreign_key="book.book_id", primary_key=True)
    author_id: int = Field(foreign_key="author.author_id", primary_key=True)


class BookCategory(SQLModel, table=True):
    __tablename__ = "book_category"

    category_id: int = Field(foreign_key="category.category_id", primary_key=True)
    book_id: int = Field(foreign_key="book.book_id", primary_key=True)


class Address(SQLModel, table=True):
    __tablename__ = "address"

    address_id: int = Field(primary_key=True)
    district: str = Field(max_length=45)
    location: str = Field(max_length=45)
    postal_code: str = Field(max_length=45)
    street: str = Field(max_length=45)
    house_number: int

    library: list["Library"] = Relationship(back_populates="address")
    reader: list["Reader"] = Relationship(back_populates="address")


class Author(SQLModel, table=True):
    __tablename__ = "author"

    author_id: int | None = Field(default=None, primary_key=True)
    first_name: str = Field(max_length=45)
    last_name: str = Field(max_length=45)

    book: list["Book"] = Relationship(back_populates="author", link_model=BookAuthor)


class Publisher(SQLModel, table=True):
    __tablename__ = "publisher"

    publisher_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=45)

    book: list["Book"] = Relationship(back_populates="publisher")


class Book(SQLModel, table=True):
    __tablename__ = "book"

    book_id: int | None = Field(default=None, primary_key=True)
    title: str = Field(max_length=45)
    publication_year: int
    pages: int | None = Field(default=None)
    isbn: str = Field(max_length=20, unique=True)
    rental_rate: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    publisher_id: int = Field(foreign_key="publisher.publisher_id")

    publisher: Publisher | None = Relationship(back_populates="book")
    author: list[Author] = Relationship(back_populates="book", link_model=BookAuthor)
    category: list["Category"] = Relationship(back_populates="book", link_model=BookCategory)
    copy: list["Copy"] = Relationship(back_populates="book")


class BookCreate(BaseModel):
    title: str
    publication_year: int
    pages: int | None = None
    isbn: str
    rental_rate: float
    publisher_id: int
    author_ids: list[int] | None = None
    category_ids: list[int] | None = None


class AuthorCreate(BaseModel):
    first_name: str
    last_name: str


class PublisherCreate(BaseModel):
    name: str


class CategoryCreate(BaseModel):
    name: str


class PublisherOut(SQLModel):
    publisher_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class CategoryOut(SQLModel):
    category_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AuthorOut(SQLModel):
    author_id: int
    first_name: str
    last_name: str
    
    model_config = ConfigDict(from_attributes=True)


class BookListOut(SQLModel):
    book_id: int
    title: str

    model_config = ConfigDict(from_attributes=True)


class AuthorDetailOut(BaseModel):
    author_id: int
    first_name: str
    last_name: str
    book_title: list[str]

    model_config = ConfigDict(from_attributes=True)


class PublisherDetailOut(BaseModel):
    publisher_id: int
    name: str
    book_title: list[str]

    model_config = ConfigDict(from_attributes=True)


class CategoryDetailOut(BaseModel):
    category_id: int
    name: str
    book_title: list[str]

    model_config = ConfigDict(from_attributes=True)


class BookDetailOut(BaseModel):
    book_id: int
    title: str
    publication_year: int | None
    pages: int | None
    isbn: str | None
    rental_rate: float | None
    publisher: PublisherOut | None
    author: list[AuthorOut]
    category: list[CategoryOut]

    model_config = ConfigDict(from_attributes=True)

class Category(SQLModel, table=True):
    __tablename__ = "category"

    category_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=45, unique=True)

    book: list["Book"] = Relationship(back_populates="category", link_model=BookCategory)


class Library(SQLModel, table=True):
    __tablename__ = "library"

    library_id: int = Field(primary_key=True)
    name: str = Field(max_length=45)
    address_id: int = Field(foreign_key="address.address_id")

    address: Address | None = Relationship(back_populates="library")
    copy: list["Copy"] = Relationship(back_populates="library")
    source_internal_rental: list["InternalRental"] = Relationship(
        back_populates="source_library_rel",
        sa_relationship_kwargs={"foreign_keys": "[InternalRental.source_library]"},
    )
    target_internal_rental: list["InternalRental"] = Relationship(
        back_populates="target_library_rel",
        sa_relationship_kwargs={"foreign_keys": "[InternalRental.target_library]"},
    )


class Copy(SQLModel, table=True):
    __tablename__ = "copy"

    copy_id: int | None = Field(default=None, primary_key=True)
    status: CopyStatus = Field(
        default=CopyStatus.AVAILABLE,
        sa_column=Column(
            SAEnum(CopyStatus, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
            nullable=False,
            default=CopyStatus.AVAILABLE.value,
        ),
    )
    book_id: int = Field(foreign_key="book.book_id")
    library_id: int = Field(foreign_key="library.library_id")

    book: Book | None = Relationship(back_populates="copy")
    library: Library | None = Relationship(back_populates="copy")
    rental: list["Rental"] = Relationship(back_populates="copy")


class ReaderType(SQLModel, table=True):
    __tablename__ = "reader_type"

    type_id: int | None = Field(default=None, primary_key=True)
    name: str = Field(max_length=45)
    max_book: int
    borrow_day: int
    fine_per_day: Decimal = Field(sa_column=Column(Numeric(5, 2), nullable=False))

    reader: list["Reader"] = Relationship(back_populates="reader_type")


class Reader(SQLModel, table=True):
    __tablename__ = "reader"

    reader_id: int | None = Field(default=None, primary_key=True)
    first_name: str = Field(max_length=45)
    last_name: str = Field(max_length=45)
    email: str = Field(max_length=45)
    phone: int
    type_id: int = Field(foreign_key="reader_type.type_id")
    address_id: int = Field(foreign_key="address.address_id")

    reader_type: ReaderType | None = Relationship(back_populates="reader")
    address: Address | None = Relationship(back_populates="reader")
    library_card: list["LibraryCard"] = Relationship(back_populates="reader")


class LibraryCard(SQLModel, table=True):
    __tablename__ = "library_card"

    card_id: int | None = Field(default=None, primary_key=True)
    status: LibraryCardStatus = Field(
        default=LibraryCardStatus.ACTIVE,
        sa_column=Column(
            SAEnum(LibraryCardStatus, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
            nullable=False,
            default=LibraryCardStatus.ACTIVE.value,
        ),
    )
    created_at: date
    reader_id: int = Field(foreign_key="reader.reader_id")

    reader: Reader | None = Relationship(back_populates="library_card")
    rental: list["Rental"] = Relationship(back_populates="card")


class Rental(SQLModel, table=True):
    __tablename__ = "rental"

    rental_id: int | None = Field(default=None, primary_key=True)
    status: RentalStatus | None = Field(
        default=None,
        sa_column=Column(
            SAEnum(RentalStatus, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
            nullable=True,
        ),
    )
    rental_rate: int = Field(description="Rental rate copied from the book at rent time.")
    rental_date: date
    due_date: date
    return_date: date | None = Field(default=None)
    copy_id: int = Field(foreign_key="copy.copy_id")
    card_id: int = Field(foreign_key="library_card.card_id")

    copy: Copy | None = Relationship(back_populates="rental")
    card: LibraryCard | None = Relationship(back_populates="rental")
    fine: list["Fine"] = Relationship(back_populates="rental")
    internal_rental: list["InternalRental"] = Relationship(back_populates="rental")
    payment: list["Payment"] = Relationship(back_populates="rental")


class Fine(SQLModel, table=True):
    __tablename__ = "fine"

    fine_id: int | None = Field(default=None, primary_key=True)
    amount: Decimal = Field(sa_column=Column(Numeric(10, 2), nullable=False))
    note: str | None = Field(default=None, sa_column=Column(Text, nullable=True))
    paid: bool = Field(default=False)
    rental_id: int = Field(foreign_key="rental.rental_id")

    rental: Rental | None = Relationship(back_populates="fine")


class InternalRental(SQLModel, table=True):
    __tablename__ = "internal_rental"

    internal_rental_id: str = Field(primary_key=True, max_length=45)
    status: InternalRentalStatus = Field(
        sa_column=Column(
            SAEnum(InternalRentalStatus, values_callable=lambda enum_cls: [item.value for item in enum_cls]),
            nullable=False,
        ),
    )
    rental_id: int = Field(foreign_key="rental.rental_id")
    source_library: int = Field(foreign_key="library.library_id")
    target_library: int = Field(foreign_key="library.library_id")

    rental: Rental | None = Relationship(back_populates="internal_rental")
    source_library_rel: Library | None = Relationship(
        back_populates="source_internal_rental",
        sa_relationship_kwargs={"foreign_keys": "[InternalRental.source_library]"},
    )
    target_library_rel: Library | None = Relationship(
        back_populates="target_internal_rental",
        sa_relationship_kwargs={"foreign_keys": "[InternalRental.target_library]"},
    )


class Log(SQLModel, table=True):
    __tablename__ = "logs"

    log_id: int | None = Field(default=None, primary_key=True)
    operation: str | None = Field(default=None, max_length=200)
    log_date: date | None = Field(default=None)
    detail: str | None = Field(default=None, sa_column=Column(Text, nullable=True))


class Payment(SQLModel, table=True):
    __tablename__ = "payment"

    payment_id: int | None = Field(default=None, primary_key=True)
    amount: float
    payment_date: date | None = Field(default=None)
    rental_id: int = Field(foreign_key="rental.rental_id")

    rental: Rental | None = Relationship(back_populates="payment")


def create_db_and_tables() -> None:
    SQLModel.metadata.create_all(engine)


