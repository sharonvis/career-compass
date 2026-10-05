"""Database connection and session setup; importing this module creates no tables."""

from pathlib import Path

from sqlalchemy import create_engine, event
from sqlalchemy.orm import DeclarativeBase, sessionmaker

BASE_DIR = Path(__file__).resolve().parent.parent
DATABASE_PATH = BASE_DIR / "data" / "career_compass.db"
DATABASE_URL = f"sqlite:///{DATABASE_PATH}"

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False},
)


def configure_sqlite_foreign_keys(engine):
    """Enable SQLite foreign keys for new connections on this engine."""
    @event.listens_for(engine, "connect")
    def enable_foreign_keys(dbapi_connection, connection_record):
        cursor = dbapi_connection.cursor()
        try:
            cursor.execute("PRAGMA foreign_keys=ON")
        finally:
            cursor.close()


configure_sqlite_foreign_keys(engine)


SessionLocal = sessionmaker(bind=engine)


class Base(DeclarativeBase):
    """Shared base for all database models."""
