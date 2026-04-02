"""
SQLAlchemy engine and session factory.
Uses SQLite by default (configured via DATABASE_URL in .env).
"""
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from .config import settings

engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},  # needed for SQLite
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

Base = declarative_base()


def get_db():
    """FastAPI dependency: yields a database session and ensures it is closed."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_all_tables():
    """Create all tables defined in ORM models. Called on app startup."""
    # Import models so Base.metadata knows about them
    from .models import card, owner, settings as settings_model  # noqa: F401
    Base.metadata.create_all(bind=engine)
