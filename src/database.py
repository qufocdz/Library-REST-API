
import os

from sqlmodel import SQLModel

from dotenv import load_dotenv

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.ext.asyncio import async_sessionmaker
from sqlalchemy.engine import URL




load_dotenv()





DB_USER = os.getenv("DB_USER")
DB_PASSWORD = os.getenv("DB_PASSWORD")
DB_HOST = os.getenv("DB_HOST")
DB_PORT = (os.getenv("DB_PORT"))
DB_NAME = os.getenv("DB_NAME")

SQLALCHEMY_DATABASE_URL = URL.create(
    drivername="mysql+asyncmy",
    username=DB_USER or None,
    password=DB_PASSWORD or None,
    host=DB_HOST or None,
    port=DB_PORT,
    database=DB_NAME or None,
)

engine = create_async_engine(SQLALCHEMY_DATABASE_URL, echo=True)

async_session = async_sessionmaker(autocommit=False, autoflush=False, bind=engine)


async def create_db_and_tables():
    import models as models
    async with engine.begin() as conn:
        await conn.run_sync(SQLModel.metadata.create_all)

