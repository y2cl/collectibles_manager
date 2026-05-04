"""
AppSettings, ImportAmbiguity, and ImportHistory ORM models.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, Boolean, Float, DateTime, JSON, LargeBinary, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class AppSettings(Base):
    __tablename__ = "app_settings"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Duplicate / merge strategies
    duplicate_strategy = Column(String, default="merge")       # "merge" | "separate"
    paid_merge_strategy = Column(String, default="sum")        # "sum" | "average" | "ignore"

    # Backup
    auto_backup_enabled = Column(Boolean, default=False)
    backup_retention = Column(Integer, default=5)

    # API source toggles + eBay env stored as JSON to avoid extra table
    # Keys mirror the original api_config.json fields:
    # scryfall_enabled, pokemontcg_enabled, justtcg_enabled, pokemonpublic_enabled,
    # fallback_enabled, ebay_enabled, sportscarddatabase_enabled,
    # last_ebay_env, pokemontcg_api
    api_source_config = Column(JSON, default=dict)

    # Search UI preferences (persisted across devices)
    search_cards_per_row = Column(Integer, default=4)
    search_sort_by = Column(String, default="default")  # "default" | "name" | "set" | "year"

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class ImportAmbiguity(Base):
    """
    Stores rows from a CSV import that couldn't be auto-resolved to a single card.
    The user resolves them via the UI; on resolution the row is deleted and the
    selected card is committed to collection_cards.
    """
    __tablename__ = "import_ambiguities"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    profile_id = Column(String, nullable=False, default="default")
    row_data = Column(JSON, nullable=False)    # original CSV row as dict
    candidates = Column(JSON, nullable=False)  # list of CardResult dicts
    created_at = Column(DateTime, default=datetime.utcnow)
    # Link back to the import batch so resolved cards can be tracked for undo
    import_history_id = Column(Integer, nullable=True)

    owner = relationship("Owner", back_populates="ambiguities")


class ImportHistory(Base):
    """
    Records each CSV import batch so users can review, re-download, or undo it.
    created_card_ids accumulates the CollectionCard PKs created both during the
    initial import and during subsequent ambiguity resolution.
    """
    __tablename__ = "import_history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    profile_id = Column(String, nullable=False, default="default")
    filename = Column(String, default="")
    file_data = Column(LargeBinary, nullable=True)   # raw CSV bytes for re-download
    game = Column(String, default="")
    imported_count = Column(Integer, default=0)      # directly-imported rows
    ambiguous_count = Column(Integer, default=0)     # rows needing disambiguation
    created_card_ids = Column(JSON, default=list)    # all CollectionCard IDs in this batch
    timestamp = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner", back_populates="import_history")
