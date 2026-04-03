"""
Search service: orchestrates the multi-source search fallback chain.

Priority order (cache-first):
  1. Local offline cache (fast, offline-capable)       ← checked first
  2. Live API (Scryfall / Pokémon TCG / eBay)          ← only if cache misses or force_refresh=True

Pass force_refresh=True to skip the local cache and go straight to the API,
then repopulate the cache with fresh data (useful for price updates).
"""
import logging
from typing import List, Dict, Tuple, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


def _normalize_pokemon_local(raw: Dict) -> Dict:
    """
    Convert a raw pokemon card dict from find_pokemon_cards_local (which mirrors
    the Pokémon TCG API shape) into the flat UI-ready format that _to_card_result
    and the CardResult schema expect.
    """
    set_obj = raw.get("set") or {}
    if isinstance(set_obj, dict):
        set_name = set_obj.get("name", "")
        set_code = set_obj.get("id", "")
        released = set_obj.get("releaseDate", "")
        year = str(released)[:4] if released else ""
    else:
        # already a string (shouldn't happen, but be safe)
        set_name = str(set_obj)
        set_code = ""
        year = ""

    images = raw.get("images") or {}
    if isinstance(images, str):
        try:
            import json as _json
            images = _json.loads(images)
        except Exception:
            images = {}
    img_url = images.get("small") or images.get("large") or ""

    tcg = raw.get("tcgplayer") or {}
    if isinstance(tcg, str):
        try:
            import json as _json
            tcg = _json.loads(tcg)
        except Exception:
            tcg = {}

    prices = (tcg.get("prices") or {})
    market_price = 0.0
    prices_map: Dict = {}
    for k in ["normal", "holofoil", "reverseHolofoil", "1stEditionHolofoil",
              "1stEdition", "unlimited", "unlimitedHolofoil"]:
        p = prices.get(k) or {}
        try:
            low_v = float(p.get("low") or 0)
            mid_v = float(p.get("mid") or 0)
            mkt_v = float(p.get("market") or 0)
        except Exception:
            low_v = mid_v = mkt_v = 0.0
        if any([low_v, mid_v, mkt_v]):
            prices_map[k] = {"low": low_v, "mid": mid_v, "market": mkt_v}
            market_price = mkt_v or market_price

    link = (
        (tcg.get("url") or "")
        or f"https://pokemontcg.io/card/{raw.get('id', '')}"
    )

    return {
        "game": "Pokémon",
        "name": raw.get("name", ""),
        "set": set_name,
        "set_code": set_code,
        "year": year,
        "card_number": raw.get("number", ""),
        "image_url": img_url,
        "link": link,
        "price_usd": market_price,
        "price_usd_foil": 0.0,
        "price_usd_etched": 0.0,
        "price_low": None,
        "price_mid": None,
        "price_market": market_price or None,
        "quantity": 1,
        "variant": "",
        "prices_map": prices_map,
        "tcgplayer": tcg,
        "source": "Local Cache",
        "has_nonfoil": True,
        "has_foil": False,
        "artist": "",
    }


def _get_api_config(db: Session) -> Dict:
    """Load API source config from DB settings, or return safe defaults."""
    from ..models.settings import AppSettings
    row = db.query(AppSettings).first()
    if row and row.api_source_config:
        return row.api_source_config
    return {
        "scryfall_enabled": True,
        "pokemontcg_enabled": False,
        "pokemonpublic_enabled": True,
        "fallback_enabled": True,
        "ebay_enabled": True,
        "sportscarddatabase_enabled": True,
        "last_ebay_env": "Sandbox",
        "pokemontcg_api": "https://api.pokemontcg.io/v2/cards",
    }


def search_mtg(
    card_name: str,
    set_hint: str = "",
    collector_number: str = "",
    db: Optional[Session] = None,
    force_refresh: bool = False,
) -> Tuple[List[Dict], int, int, str]:
    """
    MTG search — local cache first, then Scryfall.

    force_refresh=True: skip cache, hit Scryfall, repopulate cache.
    """
    cfg = _get_api_config(db) if db else {}
    fallback_enabled = cfg.get("fallback_enabled", True)
    scryfall_enabled = cfg.get("scryfall_enabled", True)

    # ── 1. Local cache (unless force_refresh) ────────────────────────────────
    if fallback_enabled and not force_refresh:
        try:
            from ..legacy.fallback_manager import find_mtg_cards_local
            cards = find_mtg_cards_local(card_name, set_hint)
            if cards:
                logger.debug("MTG cache hit: %d cards for %r", len(cards), card_name)
                return cards, len(cards), len(cards), "Local Cache"
        except Exception as e:
            logger.warning("MTG local cache read error: %s", e)

    # ── 2. Live API ───────────────────────────────────────────────────────────
    if scryfall_enabled:
        from ..external.scryfall import search_mtg_scryfall
        cards, shown, total, source = search_mtg_scryfall(
            card_name, set_hint, collector_number,
            fallback_enabled=fallback_enabled,   # stores results to cache
        )
        if cards:
            logger.debug("Scryfall hit: %d cards for %r", len(cards), card_name)
            return cards, shown, total, source
        logger.info("Scryfall returned no results for %r", card_name)

    return [], 0, 0, "No results"


def search_pokemon(
    card_name: str,
    set_hint: str = "",
    number: str = "",
    db: Optional[Session] = None,
    force_refresh: bool = False,
) -> Tuple[List[Dict], int, int, str]:
    """
    Pokémon search — local cache first, then Pokémon TCG API.

    force_refresh=True: skip cache, hit API, repopulate cache.
    """
    from ..config import settings as app_settings

    cfg = _get_api_config(db) if db else {}
    fallback_enabled = cfg.get("fallback_enabled", True)
    pokemon_enabled = cfg.get("pokemontcg_enabled", False) or cfg.get("pokemonpublic_enabled", True)
    api_url = cfg.get("pokemontcg_api", "https://api.pokemontcg.io/v2/cards")
    api_key = app_settings.pokemontcg_api_key if cfg.get("pokemontcg_enabled", False) else ""

    # ── 1. Local cache (unless force_refresh) ────────────────────────────────
    if fallback_enabled and not force_refresh:
        try:
            from ..legacy.fallback_manager import find_pokemon_cards_local
            raw_cards = find_pokemon_cards_local(card_name, set_hint)
            if raw_cards:
                cards = [_normalize_pokemon_local(c) for c in raw_cards]
                logger.debug("Pokémon cache hit: %d cards for %r", len(cards), card_name)
                return cards, len(cards), len(cards), "Local Cache"
        except Exception as e:
            logger.warning("Pokémon local cache read error: %s", e)

    # ── 2. Live API ───────────────────────────────────────────────────────────
    if pokemon_enabled:
        from ..external.pokemon_tcg import search_pokemon_tcg
        cards, shown, total, source = search_pokemon_tcg(
            card_name, set_hint, number,
            api_key=api_key,
            api_url=api_url,
            fallback_enabled=fallback_enabled,   # stores results to cache
        )
        if cards:
            logger.debug("Pokémon TCG API hit: %d cards for %r", len(cards), card_name)
            return cards, shown, total, source
        logger.info("Pokémon TCG API returned no results for %r", card_name)

    return [], 0, 0, "No results"


def search_sports(
    player_name: str,
    sport: str = "baseball",
    year: str = "",
    team: str = "",
    set_name: str = "",
    card_number: str = "",
    db: Optional[Session] = None,
    force_refresh: bool = False,
) -> Tuple[List[Dict], int, int, str]:
    """
    Sports card search — eBay first, then SportsCardDatabase.
    (Sports cards have no local CSV cache, so force_refresh has no effect here.)
    """
    from ..config import settings as app_settings

    cfg = _get_api_config(db) if db else {}
    ebay_env = cfg.get("last_ebay_env", "Sandbox")

    if cfg.get("ebay_enabled", True) or cfg.get("ebay_sports_enabled", True):
        ebay_key = (
            app_settings.ebay_app_id if ebay_env == "Production" else app_settings.ebay_app_id_sbx
        )
        from ..external.ebay import search_ebay_sports
        cards, shown, total, source = search_ebay_sports(
            player_name, year, team, set_name, card_number,
            sport=sport,
            ebay_app_id=ebay_key,
            ebay_env=ebay_env,
        )
        if cards:
            return cards, shown, total, source

    if cfg.get("sportscarddatabase_enabled", True):
        from ..external.sportscard_db import search_sportscard_database
        return search_sportscard_database(player_name, year, set_name, card_number)

    return [], 0, 0, "No results"


# Backwards-compatible alias
def search_baseball(
    player_name: str,
    year: str = "",
    team: str = "",
    set_name: str = "",
    card_number: str = "",
    db: Optional[Session] = None,
    force_refresh: bool = False,
) -> Tuple[List[Dict], int, int, str]:
    return search_sports(
        player_name=player_name,
        sport="baseball",
        year=year,
        team=team,
        set_name=set_name,
        card_number=card_number,
        db=db,
        force_refresh=force_refresh,
    )
