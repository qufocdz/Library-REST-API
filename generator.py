import csv
import os
import re
from dotenv import load_dotenv
import random
import ast
import mysql.connector
from datetime import datetime
from tqdm import tqdm

load_dotenv()

DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = os.getenv("DB_PORT")
DB_NAME = os.getenv("DB_NAME")

# =========================
# CONFIG
# =========================
DB_CONFIG = {
    'host': DB_HOST,
    'user': DB_USER,
    'password': DB_PASSWORD,
    'database': DB_NAME
}

CSV_FILE = 'books.csv'

# =========================
# DB
# =========================
conn = mysql.connector.connect(**DB_CONFIG)
cursor = conn.cursor()

# =========================
# ISBN GENERATOR
# =========================
used_isbns = set()


def generate_isbn():
    while True:
        isbn = "96" + "".join([str(random.randint(0, 9)) for _ in range(11)])
        if isbn not in used_isbns:
            used_isbns.add(isbn)
            return isbn


def fix_isbn(isbn):
    if not isbn or isbn.strip() == "" or isbn == "9999999999999" or not isbn.isdigit():
        return generate_isbn()

    if isbn in used_isbns:
        return generate_isbn()

    used_isbns.add(isbn)
    return isbn


# =========================
# HELPERS
# =========================
def parse_list_field(value):
    if not value:
        return []
    try:
        return ast.literal_eval(value.strip())
    except:
        return [value]


def get_or_create_publisher(name):
    name = name[:45]
    cursor.execute("SELECT publisher_id FROM publisher WHERE name=%s", (name,))
    res = cursor.fetchone()
    if res:
        return res[0]

    cursor.execute("INSERT INTO publisher (name) VALUES (%s)", (name,))
    conn.commit()
    return cursor.lastrowid


def clean_author_name(name):
    # usuwa nawiasy typu (Preface), (Editor), itp.
    name = re.sub(r"\(.*?\)", "", name)

    # usuwa podwójne spacje
    name = " ".join(name.split())

    return name.strip()


def parse_authors(value):
    if not value:
        return []

    # jeśli lista Pythonowa
    try:
        parsed = ast.literal_eval(value)
        if isinstance(parsed, list):
            value = ",".join(parsed)
        else:
            value = str(parsed)
    except:
        pass

    # split po przecinku (BO TAK MASZ DANE)
    parts = value.split(",")

    authors = []
    for p in parts:
        p = clean_author_name(p)

        # filtr śmieci
        if len(p) < 2:
            continue
        if p.lower() in ["none", "unknown"]:
            continue

        authors.append(p)

    # deduplikacja
    return list(dict.fromkeys(authors))


def get_or_create_author(full_name):
    parts = full_name.strip().split(" ")
    first = parts[0][:45]
    last = " ".join(parts[1:])[:45] if len(parts) > 1 else "Unknown"

    cursor.execute(
        "SELECT author_id FROM author WHERE first_name=%s AND last_name=%s",
        (first, last)
    )
    res = cursor.fetchone()
    if res:
        return res[0]

    cursor.execute(
        "INSERT INTO author (first_name, last_name) VALUES (%s, %s)",
        (first, last)
    )
    conn.commit()
    return cursor.lastrowid


def get_or_create_category(name):
    name = name[:45]
    cursor.execute("SELECT category_id FROM category WHERE name=%s", (name,))
    res = cursor.fetchone()
    if res:
        return res[0]

    cursor.execute("INSERT IGNORE INTO category (name) VALUES (%s)", (name,))
    conn.commit()

    cursor.execute("SELECT category_id FROM category WHERE name=%s", (name,))
    return cursor.fetchone()[0]


def extract_year(date_str):
    try:
        return datetime.strptime(date_str, "%m/%d/%y").year
    except:
        return random.randint(1990, 2020)


# =========================
# LIBRARIES
# =========================
libraries_data = [
    ("Biblioteka Nad Odrą", "Dolnośląskie", "Wrocław", "50-001", "ul. Mostowa", 12),
    ("Centrum Książki Aurora", "Mazowieckie", "Warszawa", "00-950", "ul. Świętokrzyska", 45),
    ("Biblioteka Morska", "Pomorskie", "Gdańsk", "80-001", "ul. Długa", 22),
    ("Krakowska Czytelnia Publiczna", "Małopolskie", "Kraków", "30-001", "ul. Grodzka", 8),
    ("Biblioteka Zachodnia", "Wielkopolskie", "Poznań", "60-001", "ul. Półwiejska", 19),
]

library_ids = []

for name, district, city, postal, street, house in libraries_data:
    cursor.execute("""
        INSERT INTO address (district, location, postal_code, street, house_number)
        VALUES (%s, %s, %s, %s, %s)
    """, (district, city, postal, street, house))
    address_id = cursor.lastrowid

    cursor.execute("""
        INSERT INTO library (name, address_id)
        VALUES (%s, %s)
    """, (name, address_id))

    library_ids.append(cursor.lastrowid)

conn.commit()

# =========================
# COUNT ROWS (for tqdm)
# =========================
with open(CSV_FILE, encoding='utf-8') as f:
    total_rows = sum(1 for _ in f) - 1

# =========================
# PROCESS CSV
# =========================
with open(CSV_FILE, newline='', encoding='utf-8') as f:
    reader = csv.DictReader(f, delimiter=',', quotechar='"')

    for row in tqdm(reader, total=total_rows, desc="Importing books"):
        try:
            title = (row['title'] or "Unknown")[:45]
            isbn = fix_isbn((row['isbn'] or "").strip())
            pages = int(row['pages']) if row['pages'] and row['pages'].isdigit() else None
            publisher_name = (row['publisher'] or "Unknown")[:45]
            year = extract_year(row['publishDate'])
            rental_rate = round(random.uniform(5, 20), 2)

            publisher_id = get_or_create_publisher(publisher_name)

            # BOOK
            cursor.execute("""
                INSERT IGNORE INTO book (title, publication_year, pages, isbn, rental_rate, publisher_id)
                VALUES (%s, %s, %s, %s, %s, %s)
            """, (title, year, pages, isbn, rental_rate, publisher_id))

            conn.commit()

            cursor.execute("SELECT book_id FROM book WHERE isbn=%s", (isbn,))
            res = cursor.fetchone()
            if not res:
                continue
            book_id = res[0]

            # AUTHORS
            for a in parse_authors(row['author']):
                author_id = get_or_create_author(a)
                cursor.execute("""
                    INSERT IGNORE INTO book_author (book_id, author_id)
                    VALUES (%s, %s)
                """, (book_id, author_id))

            # CATEGORIES
            for g in parse_list_field(row['genres']):
                category_id = get_or_create_category(g)
                cursor.execute("""
                    INSERT IGNORE INTO book_category (book_id, category_id)
                    VALUES (%s, %s)
                """, (book_id, category_id))

            # COPIES
            for _ in range(random.randint(10, 100)):
                lib_id = random.choice(library_ids)
                cursor.execute("""
                    INSERT INTO copy (status, book_id, library_id)
                    VALUES ('available', %s, %s)
                """, (book_id, lib_id))

            conn.commit()

        except Exception as e:
            print("Error:", e)
            continue

cursor.close()
conn.close()

print("DONE ✅")