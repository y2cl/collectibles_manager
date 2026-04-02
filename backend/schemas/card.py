"""
Pydantic schemas for cards, collection entries, and watchlist items.
"""
from datetime import datetime
from typing import Optional, Dict, Any
from pydantic import BaseModel, Field


# ── Search result (returned by /api/search/*) ─────────────────────────────────

class CardResult(BaseModel):
    game: str
    name: str
    set_name: str = Field("", alias="set")
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    image_url: str = ""
    image_url_back: str = ""   # back face for double-faced cards
    link: str = ""

    # MTG prices
    price_usd: float = 0.0
    price_usd_foil: float = 0.0
    price_usd_etched: float = 0.0

    # Pokémon prices
    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None
    prices_map: Optional[Dict[str, Any]] = None  # raw Pokémon variant prices

    # Availability flags (MTG)
    has_nonfoil: bool = True
    has_foil: bool = False

    source: str = ""
    artist: str = ""

    class Config:
        populate_by_name = True


class SearchResponse(BaseModel):
    cards: list[CardResult]
    total: int
    shown: int
    source: str


# ── Collection card (stored in DB) ────────────────────────────────────────────

class CollectionCardBase(BaseModel):
    game: str
    name: str
    set_name: str = ""
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    link: str = ""
    image_url: str = ""

    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None
    price_usd: float = 0.0
    price_usd_foil: float = 0.0
    price_usd_etched: float = 0.0

    quantity: int = 1
    variant: str = ""
    paid: float = 0.0
    signed: str = ""
    altered: str = ""
    notes: str = ""


class CollectionCardCreate(CollectionCardBase):
    owner_id: str   # owner slug
    profile_id: str = "default"


class CollectionCardUpdate(BaseModel):
    quantity: Optional[int] = None
    paid: Optional[float] = None
    variant: Optional[str] = None
    notes: Optional[str] = None
    signed: Optional[str] = None
    altered: Optional[str] = None
    price_usd: Optional[float] = None
    price_usd_foil: Optional[float] = None
    price_usd_etched: Optional[float] = None
    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None


class CollectionCardRead(CollectionCardBase):
    id: int
    owner_id: int
    profile_id: str
    timestamp: datetime

    class Config:
        from_attributes = True


class BulkDeleteRequest(BaseModel):
    owner_id: str
    profile_id: str = "default"
    card_ids: list[int]


class CollectionStats(BaseModel):
    total_cards: int
    unique_cards: int
    unique_sets: int
    total_value: float


class CollectionResponse(BaseModel):
    cards: list[CollectionCardRead]
    stats: CollectionStats


# ── Watchlist ─────────────────────────────────────────────────────────────────

class WatchlistItemBase(BaseModel):
    game: str
    name: str
    set_name: str = ""
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    link: str = ""
    image_url: str = ""

    price_usd: float = 0.0
    price_usd_foil: float = 0.0
    price_usd_etched: float = 0.0
    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None

    quantity: int = 1
    variant: str = ""
    target_price: float = 0.0
    signed: str = ""
    altered: str = ""
    notes: str = ""


class WatchlistItemCreate(WatchlistItemBase):
    owner_id: str
    profile_id: str = "default"


class WatchlistItemUpdate(BaseModel):
    quantity: Optional[int] = None
    target_price: Optional[float] = None
    notes: Optional[str] = None
    variant: Optional[str] = None


class WatchlistItemRead(WatchlistItemBase):
    id: int
    owner_id: int
    profile_id: str
    timestamp: datetime

    class Config:
        from_attributes = True
