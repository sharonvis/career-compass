"""Database connection and session setup; importing this module creates no tables."""

from pathlib import Path
from contextlib import contextmanager

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


def init_db():
    """Explicitly create the data directory and registered database tables."""
    from database import models  # Register models before creating tables.

    DATABASE_PATH.parent.mkdir(parents=True, exist_ok=True)
    Base.metadata.create_all(bind=engine)


@contextmanager
def session_scope():
    """Commit one successful action, roll back failures, and always close."""
    session = SessionLocal()
    try:
        yield session
        session.commit()
    except BaseException:
        session.rollback()
        raise
    finally:
        session.close()
