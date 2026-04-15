"""
Search endpoints: GET /api/search/mtg, /api/search/pokemon, /api/search/sports

Query params shared by all endpoints:
  force_refresh=true  — skip local cache, fetch from live API, repopulate cache
"""
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..schemas.card import SearchResponse, CardResult
from ..services.search_service import search_mtg, search_pokemon, search_sports, search_coins, search_comics, search_comic_issues, search_comic_find_issue

router = APIRouter(prefix="/api/search", tags=["search"])


def _to_card_result(card: dict) -> CardResult:
    return CardResult(
        game=card.get("game", ""),
        sport=card.get("sport"),
        name=card.get("name", ""),
        set_name=card.get("set", ""),
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
        # Coin-specific
        denomination=card.get("denomination"),
        country=card.get("country"),
        coin_or_bill=card.get("coin_or_bill"),
        silver_amount=card.get("silver_amount"),
        mint_mark=card.get("mint_mark"),
        coin_type_options=card.get("coin_type_options"),
        coin_types_data=card.get("coin_types_data"),
        # Comics-specific
        issue_number=card.get("issue_number"),
        story_arc=card.get("story_arc"),
        writer=card.get("writer"),
        comic_artist=card.get("comic_artist") or card.get("artist", ""),
        publisher=card.get("publisher"),
        is_key_issue=card.get("is_key_issue", False),
        cgc_cert_number=card.get("cgc_cert_number"),
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


@router.get("/sports", response_model=SearchResponse)
def search_sports_endpoint(
    player_name: str = Query(..., description="Player name"),
    sport: str = Query("baseball", description="Sport type: baseball, football, basketball, hockey, soccer, other"),
    year: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    set_name: Optional[str] = Query(None),
    card_number: Optional[str] = Query(None),
    force_refresh: bool = Query(False, description="Force live API fetch (no local cache for sports cards)"),
    db: Session = Depends(get_db),
):
    cards_raw, shown, total, source = search_sports(
        player_name=player_name,
        sport=sport,
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


@router.get("/coins", response_model=SearchResponse)
def search_coins_endpoint(
    name: str = Query(..., description="Coin name or series to search (e.g. 'Morgan Dollar', 'Lincoln Cent')"),
    year: Optional[str] = Query(None, description="Mint year filter (e.g. '1921')"),
    mint_mark: Optional[str] = Query(None, description="Mint mark filter (e.g. 'D', 'S', 'O')"),
    force_refresh: bool = Query(False, description="Skip local cache and fetch live from NGC / USA Coin Book"),
    db: Session = Depends(get_db),
):
    cards_raw, shown, total, source = search_coins(
        coin_name=name,
        year=year or "",
        mint_mark=mint_mark or "",
        db=db,
        force_refresh=force_refresh,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/comics", response_model=SearchResponse)
def search_comics_endpoint(
    name: str = Query(..., description="Series title to search (e.g. 'Action Comics')"),
    force_refresh: bool = Query(False, description="Force live API fetch"),
    db: Session = Depends(get_db),
):
    """Phase 1: Search for comic series/volumes by title."""
    cards_raw, shown, total, source = search_comics(
        comic_name=name,
        db=db,
        force_refresh=force_refresh,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/comics/find-issue", response_model=SearchResponse)
def find_comic_issue_endpoint(
    name: str = Query(..., description="Series title (e.g. 'Action Comics')"),
    issue_number: str = Query(..., description="Issue number (e.g. '252')"),
    db: Session = Depends(get_db),
):
    """Direct issue search: series name + issue number → specific issue(s)."""
    cards_raw, shown, total, source = search_comic_find_issue(
        series_name=name,
        issue_number=issue_number,
        db=db,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/comics/issues", response_model=SearchResponse)
def search_comic_issues_endpoint(
    volume_id: str = Query(..., description="Comic Vine volume ID (from series search result)"),
    issue_number: Optional[str] = Query(None, description="Filter to a specific issue number (e.g. '252')"),
    db: Session = Depends(get_db),
):
    """Phase 2: Get issues for a specific volume, optionally filtered by issue number."""
    cards_raw, shown, total, source = search_comic_issues(
        volume_id=volume_id,
        issue_number=issue_number or "",
        db=db,
    )
    return SearchResponse(
        cards=[_to_card_result(c) for c in cards_raw],
        total=total,
        shown=shown,
        source=source,
    )


@router.get("/baseball", response_model=SearchResponse)
def search_baseball_endpoint(
    player_name: str = Query(..., description="Player name (deprecated: use /sports?sport=baseball)"),
    year: Optional[str] = Query(None),
    team: Optional[str] = Query(None),
    set_name: Optional[str] = Query(None),
    card_number: Optional[str] = Query(None),
    force_refresh: bool = Query(False),
    db: Session = Depends(get_db),
):
    """Deprecated alias for /sports?sport=baseball."""
    cards_raw, shown, total, source = search_sports(
        player_name=player_name,
        sport="baseball",
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
