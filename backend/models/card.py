"""
CollectionCard and WatchlistItem ORM models.
Maps the existing CSV schema to SQLite columns.
"""
from datetime import datetime
from sqlalchemy import (
    Column, Integer, String, Float, DateTime, Boolean, Index, ForeignKey
)
from sqlalchemy.orm import relationship
from ..database import Base


class CollectionCard(Base):
    __tablename__ = "collection_cards"

    id = Column(Integer, primary_key=True, autoincrement=True)

    # Owner / profile context
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    profile_id = Column(String, nullable=False, default="default")

    # Card identity
    game = Column(String, nullable=False)        # "Magic: The Gathering" | "Pokémon" | "Baseball Cards"
    name = Column(String, nullable=False)
    set_name = Column(String, default="")
    set_code = Column(String, default="")
    card_number = Column(String, default="")
    year = Column(String, default="")
    link = Column(String, default="")
    image_url = Column(String, default="")

    # Pricing (MTG uses price_usd/foil/etched; Pokémon uses low/mid/market)
    price_low = Column(Float, nullable=True)
    price_mid = Column(Float, nullable=True)
    price_market = Column(Float, nullable=True)
    price_usd = Column(Float, default=0.0)
    price_usd_foil = Column(Float, default=0.0)
    price_usd_etched = Column(Float, default=0.0)

    # Collection metadata
    quantity = Column(Integer, default=1)
    variant = Column(String, default="")         # e.g. "nonfoil", "foil", "normal", "holofoil"
    paid = Column(Float, default=0.0)
    signed = Column(String, default="")
    altered = Column(String, default="")
    notes = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner", back_populates="cards")

    __table_args__ = (
        Index("ix_cc_owner_profile_game", "owner_id", "profile_id", "game"),
        Index("ix_cc_name", "name"),
    )


class WatchlistItem(Base):
    __tablename__ = "watchlist_items"

    id = Column(Integer, primary_key=True, autoincrement=True)

    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)
    profile_id = Column(String, nullable=False, default="default")

    game = Column(String, nullable=False)
    name = Column(String, nullable=False)
    set_name = Column(String, default="")
    set_code = Column(String, default="")
    card_number = Column(String, default="")
    year = Column(String, default="")
    link = Column(String, default="")
    image_url = Column(String, default="")

    price_usd = Column(Float, default=0.0)
    price_usd_foil = Column(Float, default=0.0)
    price_usd_etched = Column(Float, default=0.0)
    price_low = Column(Float, nullable=True)
    price_mid = Column(Float, nullable=True)
    price_market = Column(Float, nullable=True)

    quantity = Column(Integer, default=1)
    variant = Column(String, default="")
    target_price = Column(Float, default=0.0)
    signed = Column(String, default="")
    altered = Column(String, default="")
    notes = Column(String, default="")
    timestamp = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner", back_populates="watchlist")

    __table_args__ = (
        Index("ix_wl_owner_profile", "owner_id", "profile_id"),
    )
