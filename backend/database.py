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
    from .models import card, owner, settings as settings_model, sports_set  # noqa: F401
    Base.metadata.create_all(bind=engine)  # creates new tables (import_history etc.)
    _apply_migrations()


def _apply_migrations():
    """Apply lightweight column migrations for existing DBs that predate Alembic."""
    from sqlalchemy import text
    card_columns = [
        ("sport", "TEXT"),
        ("manufacturer", "TEXT"),
        ("upc", "TEXT"),
        ("grading_company", "TEXT"),
        ("grade", "TEXT"),
        ("serial_number", "TEXT"),
        ("print_run", "TEXT"),
        ("rc", "BOOLEAN"),
        ("signed", "TEXT"),
        ("notes", "TEXT"),
        # Coin-specific fields
        ("denomination", "TEXT"),
        ("country", "TEXT"),
        ("coin_or_bill", "TEXT"),
        ("silver_amount", "REAL"),
        ("mint_mark", "TEXT"),
    ]
    with engine.connect() as conn:
        for table in ("collection_cards", "watchlist_items"):
            for col, col_type in card_columns:
                try:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {col} {col_type}"))
                    conn.commit()
                except Exception:
                    pass

        # import_ambiguities: link back to import batch for undo support
        try:
            conn.execute(text("ALTER TABLE import_ambiguities ADD COLUMN import_history_id INTEGER"))
            conn.commit()
        except Exception:
            pass
