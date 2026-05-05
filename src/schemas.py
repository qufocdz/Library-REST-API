
from pydantic import BaseModel, ConfigDict, ConfigDict

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


class PublisherOut(BaseModel):
    publisher_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)

class CategoryOut(BaseModel):
    category_id: int
    name: str

    model_config = ConfigDict(from_attributes=True)


class AuthorOut(BaseModel):
    author_id: int
    first_name: str
    last_name: str
    
    model_config = ConfigDict(from_attributes=True)


class BookListOut(BaseModel):
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