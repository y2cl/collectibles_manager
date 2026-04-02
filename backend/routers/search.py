"""
Search endpoints: GET /api/search/mtg, /api/search/pokemon, /api/search/baseball

Query params shared by all endpoints:
  force_refresh=true  — skip local cache, fetch from live API, repopulate cache
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.card import SearchResponse, CardResult
from ..services.search_service import search_mtg, search_pokemon, search_baseball

router = APIRouter(prefix="/api/search", tags=["search"])


def _to_card_result(card: dict) -> CardResult:
    return CardResult(
        game=card.get("game", ""),
        name=card.get("name", ""),
        set=card.get("set", ""),
        set_code=card.get("set_code", ""),
        card_number=card.get("card_number", ""),
        year=card.get("year", ""),
        image_url=card.get("image_url", ""),
        image_url_back=card.get("image_url_back", ""),
        link=card.get("link", ""),
        price_usd=card.get("price_usd", 0.0),
        price_usd_foil=card.get("price_usd_foil", 0.0),
        price_usd_etched=card.get("price_usd_etched", 0.0),
        price_low=card.get("price_low"),
        price_mid=card.get("price_mid"),
        price_market=card.get("price_market"),
        prices_map=card.get("prices_map"),
        has_nonfoil=card.get("has_nonfoil", True),
        has_foil=card.get("has_foil", False),
        source=card.get("source", ""),
        artist=card.get("artist", ""),
    )


@router.get("/mtg", response_model=SearchResponse)
def search_mtg_endpoint(
    name: str = Query(..., description="Card name to search"),
    set_hint: Optional[str] = Query(None, description="Set name or code hint"),
    collector_number: Optional[str] = Query(None, description="Collector number"),
    force_refresh: bool = Query(False, description="Skip local cache and fetch live from Scryfall"),
    db: Session = Depends(get_db),
):
    cards_raw, shown, total, source = search_mtg(
        card_name=name,
        set_hint=set_hint or "",
        collector_number=collector_number or "",
        db=db,
        force_refresh=force_refresh,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/pokemon", response_model=SearchResponse)
def search_pokemon_endpoint(
    name: str = Query(..., description="Card name to search"),
    set_hint: Optional[str] = Query(None, description="Set name or code hint"),
    number: Optional[str] = Query(None, description="Card number"),
    force_refresh: bool = Query(False, description="Skip local cache and fetch live from Pokémon TCG API"),
    db: Session = Depends(get_db),
):
    cards_raw, shown, total, source = search_pokemon(
        card_name=name,
        set_hint=set_hint or "",
        number=number or "",
        db=db,
        force_refresh=force_refresh,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/baseball", response_model=SearchResponse)
def search_baseball_endpoint(
    player_name: str = Query(..., description="Player name"),
    year: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    set_name: Optional[str] = Query(None),
    card_number: Optional[str] = Query(None),
    force_refresh: bool = Query(False, description="Force live API fetch (no local cache for baseball)"),
    db: Session = Depends(get_db),
):
    cards_raw, shown, total, source = search_baseball(
        player_name=player_name,
        year=year or "",
        team=team or "",
        set_name=set_name or "",
        card_number=card_number or "",
        db=db,
        force_refresh=force_refresh,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )
