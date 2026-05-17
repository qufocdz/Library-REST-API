-- =========================
-- FULLTEXT INDEXES
-- =========================

ALTER TABLE book
ADD FULLTEXT idx_book_fulltext (title, isbn);

ALTER TABLE author
ADD FULLTEXT idx_author_fulltext (first_name, last_name);

ALTER TABLE category
ADD FULLTEXT idx_category_fulltext (name);

ALTER TABLE publisher
ADD FULLTEXT idx_publisher_fulltext (name);


-- =========================
-- NORMAL INDEXES
-- =========================

CREATE INDEX idx_copy_library_status_book
ON copy(library_id, status, book_id);

CREATE INDEX idx_book_publisher
ON book(publisher_id);

CREATE INDEX idx_book_author_book
ON book_author(book_id);

CREATE INDEX idx_book_author_author
ON book_author(author_id);

CREATE INDEX idx_book_category_book
ON book_category(book_id);

CREATE INDEX idx_book_category_category
ON book_category(category_id);

CREATE INDEX idx_copy_book
ON copy(book_id);