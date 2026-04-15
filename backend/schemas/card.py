"""
Pydantic schemas for cards, collection entries, and watchlist items.
"""
from datetime import datetime
from typing import Optional, Dict, Any, List
from pydantic import BaseModel


# ── Search result (returned by /api/search/*) ─────────────────────────────────

class CardResult(BaseModel):
    game: str
    sport: Optional[str] = None        # for Sports Cards
    name: str
    set_name: str = ""                 # also Line/Series for Collectibles
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    image_url: str = ""
    image_url_back: str = ""           # back face for double-faced cards
    link: str = ""
    manufacturer: Optional[str] = None  # brand for Collectibles
    upc: Optional[str] = None           # barcode for Collectibles

    # MTG prices
    price_usd: float = 0.0
    price_usd_foil: float = 0.0
    price_usd_etched: float = 0.0

    # Pokémon prices
    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None
    prices_map: Optional[Dict[str, Any]] = None  # raw Pokémon variant prices

    # Coin-specific fields (auto-populated from NGC scraper)
    denomination: Optional[str] = None   # face value, e.g. "$1.00", "$0.25"
    country: Optional[str] = None        # e.g. "USA"
    coin_or_bill: Optional[str] = None   # "Coin" | "Bill"
    silver_amount: Optional[float] = None  # decimal, e.g. 0.90 = 90% silver
    mint_mark: Optional[str] = None      # e.g. "S", "D", "CC", "" for Philadelphia

    # Coin type selector (MS / MS PL / MS DPL etc.)
    coin_type_options: Optional[List[str]] = None
    coin_types_data: Optional[Dict[str, Any]] = None

    # Comics-specific fields
    issue_number: Optional[str] = None
    story_arc: Optional[str] = None
    writer: Optional[str] = None
    comic_artist: Optional[str] = None
    publisher: Optional[str] = None
    is_key_issue: Optional[bool] = False
    cgc_cert_number: Optional[str] = None

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
    sport: Optional[str] = None        # for Sports Cards
    name: str
    set_name: str = ""                 # also Line/Series for Collectibles
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    link: str = ""
    image_url: str = ""
    manufacturer: Optional[str] = None  # brand for Collectibles
    upc: Optional[str] = None           # barcode for Collectibles
    grading_company: Optional[str] = None
    grade: Optional[str] = None
    serial_number: Optional[str] = None  # grading cert number
    print_run: Optional[str] = None      # serialized print run, e.g. 23/99
    rc: Optional[bool] = None            # rookie card

    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None
    price_usd: float = 0.0
    price_usd_foil: float = 0.0
    price_usd_etched: float = 0.0

    # Coin-specific fields
    denomination: Optional[str] = None
    country: Optional[str] = None
    coin_or_bill: Optional[str] = None
    silver_amount: Optional[float] = None
    mint_mark: Optional[str] = None

    # Comics-specific fields
    issue_number: Optional[str] = None
    story_arc: Optional[str] = None
    writer: Optional[str] = None
    comic_artist: Optional[str] = None
    publisher: Optional[str] = None
    is_key_issue: Optional[bool] = False
    cgc_cert_number: Optional[str] = None

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
    # Identity fields (editable for manual-entry games)
    name: Optional[str] = None
    card_number: Optional[str] = None
    set_name: Optional[str] = None
    year: Optional[str] = None
    sport: Optional[str] = None
    manufacturer: Optional[str] = None
    upc: Optional[str] = None
    image_url: Optional[str] = None
    # Collection metadata
    quantity: Optional[int] = None
    paid: Optional[float] = None
    variant: Optional[str] = None
    notes: Optional[str] = None
    signed: Optional[str] = None
    altered: Optional[str] = None
    grading_company: Optional[str] = None
    grade: Optional[str] = None
    serial_number: Optional[str] = None
    print_run: Optional[str] = None
    rc: Optional[bool] = None
    price_usd: Optional[float] = None
    price_usd_foil: Optional[float] = None
    price_usd_etched: Optional[float] = None
    price_low: Optional[float] = None
    price_mid: Optional[float] = None
    price_market: Optional[float] = None
    # Coin fields
    denomination: Optional[str] = None
    country: Optional[str] = None
    coin_or_bill: Optional[str] = None
    silver_amount: Optional[float] = None
    mint_mark: Optional[str] = None
    # Comics fields
    issue_number: Optional[str] = None
    story_arc: Optional[str] = None
    writer: Optional[str] = None
    comic_artist: Optional[str] = None
    publisher: Optional[str] = None
    is_key_issue: Optional[bool] = None
    cgc_cert_number: Optional[str] = None


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


class BulkMoveRequest(BaseModel):
    card_ids: list[int]
    target_owner_id: str   # owner slug
    target_profile_id: str = "default"


class BulkRefreshRequest(BaseModel):
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
    sport: Optional[str] = None        # for Sports Cards
    name: str
    set_name: str = ""                 # also Line/Series for Collectibles
    set_code: str = ""
    card_number: str = ""
    year: str = ""
    link: str = ""
    image_url: str = ""
    manufacturer: Optional[str] = None  # brand for Collectibles
    upc: Optional[str] = None           # barcode for Collectibles

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
