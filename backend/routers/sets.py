"""
Card sets catalog endpoints.
Reads MTG and Pokémon set data from the fallback_data CSV files.
"""
import csv
import json
import os
import re
import time
from typing import Optional, List, Dict

import requests
from fastapi import APIRouter, Depends, Query, BackgroundTasks
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..config import settings as app_settings

router = APIRouter(prefix="/api/sets", tags=["sets"])

# Resolve the legacy fallback_data directory relative to this file.
# backend/routers/sets.py → up one level → backend/ → legacy/fallback_data
_LEGACY_BASE = os.path.normpath(os.path.join(os.path.dirname(__file__), "..", "legacy", "fallback_data"))
_MTG_DIR = os.path.join(_LEGACY_BASE, "MTG")
_MTG_SETS_CSV = os.path.join(_MTG_DIR, "mtgsets.csv")
_PKMN_SETS_CSV = os.path.join(_LEGACY_BASE, "Pokemon", "pokemonsets.csv")


def _normalize_year(value: str) -> str:
    y = str(value or "").strip()
    m4 = re.search(r"(19\d{2}|20\d{2})", y)
    if m4:
        return m4.group(1)
    m2 = re.search(r"(?:^|[^0-9])(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?:[^0-9]|$)", y)
    if m2:
        yy = int(m2.group(3))
        return str(1900 + yy) if yy >= 90 else str(2000 + yy)
    if re.fullmatch(r"\d{2}", y):
        yy = int(y)
        return str(1900 + yy) if yy >= 90 else str(2000 + yy)
    return y


# ---------------------------------------------------------------------------
# Game-type categorisation (mirrors utility/enhanced_mtg_sets.py)
# ---------------------------------------------------------------------------

_GAME_TYPE_MAP: Dict[str, str] = {
    "core": "Main", "expansion": "Main", "masters": "Main", "eternal": "Main",
    "masterpiece": "Main", "from_the_vault": "Main", "starter": "Main",
    "draft_innovation": "Main",
    "alchemy": "Digital", "treasure_chest": "Digital",
    "arsenal": "Commander", "spellbook": "Commander", "commander": "Commander",
    "planechase": "Planechase",
    "premium_deck": "Pre-Built", "duel_deck": "Pre-Built", "archenemy": "Pre-Built",
    "vanguard": "Vanguard",
    "funny": "Funny",
    "box": "Other", "promo": "Other", "token": "Other",
    "memorabilia": "Other", "minigame": "Other",
}


def _game_type(set_type: str) -> str:
    return _GAME_TYPE_MAP.get((set_type or "").lower(), "Other")


# ---------------------------------------------------------------------------
# Scryfall sets fetcher
# ---------------------------------------------------------------------------

def _fetch_scryfall_sets() -> List[Dict]:
    """Download all set records from Scryfall (handles pagination)."""
    all_sets: List[Dict] = []
    url: Optional[str] = "https://api.scryfall.com/sets"
    while url:
        resp = requests.get(url, timeout=30)
        resp.raise_for_status()
        data = resp.json()
        all_sets.extend(data.get("data", []))
        url = data.get("next_page") if data.get("has_more") else None
        if url:
            time.sleep(0.1)  # be polite to Scryfall
    return all_sets


def _flatten_set(s: Dict) -> Dict:
    """Flatten a raw Scryfall set dict for CSV storage."""
    flat: Dict = {}
    for k, v in s.items():
        if v is None:
            flat[k] = ""
        elif isinstance(v, (dict, list)):
            flat[k] = json.dumps(v)
        else:
            flat[k] = v
    # digital:true takes priority — overrides whatever the set_type mapping would say
    if s.get("digital"):
        flat["game_type"] = "Digital"
    else:
        flat["game_type"] = _game_type(s.get("set_type", ""))
    return flat


def _load_existing_sets_csv(path: str) -> Dict[str, Dict]:
    """Load existing mtgsets.csv into {code: row_dict}."""
    existing: Dict[str, Dict] = {}
    if not os.path.exists(path):
        return existing
    with open(path, "r", encoding="utf-8") as f:
        for row in csv.DictReader(f):
            code = row.get("code", "")
            if code:
                existing[code] = row
    return existing


def _sets_differ(existing: Dict, new: Dict) -> bool:
    """Return True if any tracked field changed."""
    for field in ("name", "card_count", "released_at", "set_type", "digital"):
        if str(existing.get(field, "")).strip() != str(new.get(field, "")).strip():
            return True
    return False


def _write_sets_csv(path: str, rows: List[Dict]) -> None:
    """Write rows to CSV, using the union of all keys as headers."""
    if not rows:
        return
    os.makedirs(os.path.dirname(path), exist_ok=True)
    # Build a stable, sorted fieldname list
    fieldnames = sorted({k for row in rows for k in row.keys()})
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            # Ensure every row has every field (fill missing with "")
            writer.writerow({fn: row.get(fn, "") for fn in fieldnames})


# ---------------------------------------------------------------------------
# Catalog loader (read path)
# ---------------------------------------------------------------------------

def load_sets_catalog() -> List[Dict]:
    """Load MTG and Pokémon sets from fallback_data CSVs with normalised fields."""
    sets: List[Dict] = []

    # MTG
    try:
        if os.path.exists(_MTG_SETS_CSV):
            with open(_MTG_SETS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rl = {(k or "").lower(): v for k, v in row.items()}
                    name = rl.get("name") or rl.get("set") or rl.get("set_name") or ""
                    code = rl.get("code") or rl.get("set_code") or rl.get("id") or ""
                    year_raw = (
                        rl.get("released_at") or rl.get("year") or rl.get("releasedate")
                        or rl.get("release_date") or ""
                    )
                    is_digital = str(rl.get("digital") or "").lower() in ("true", "1", "yes")
                    game_type = "Digital" if is_digital else (rl.get("game_type") or "")
                    released_at = rl.get("released_at") or rl.get("releasedate") or rl.get("release_date") or ""
                    sets.append({
                        "game": "Magic: The Gathering",
                        "name": name,
                        "code": code.upper(),
                        "year": _normalize_year(year_raw),
                        "released_at": released_at,
                        "set_type": rl.get("set_type") or rl.get("type") or "",
                        "game_type": game_type,
                        "card_count": rl.get("card_count") or rl.get("cardcount") or rl.get("count") or "",
                        "icon_url": rl.get("icon_svg_uri") or rl.get("icon_url") or "",
                        "scryfall_uri": rl.get("scryfall_uri") or rl.get("uri") or "",
                    })
    except Exception:
        pass

    # Pokémon
    try:
        if os.path.exists(_PKMN_SETS_CSV):
            with open(_PKMN_SETS_CSV, "r", encoding="utf-8") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rl = {(k or "").lower(): v for k, v in row.items()}
                    name = rl.get("name") or rl.get("set_name") or ""
                    code = rl.get("id") or rl.get("code") or rl.get("set_code") or ""
                    year_raw = (
                        rl.get("releasedate") or rl.get("release_date") or rl.get("released_at") or ""
                    )
                    sets.append({
                        "game": "Pokémon",
                        "name": name,
                        "code": code.upper(),
                        "year": _normalize_year(year_raw),
                        "released_at": year_raw,
                        "set_type": rl.get("series") or "",
                        "game_type": "",
                        "card_count": rl.get("printedtotal") or rl.get("card_count") or rl.get("total") or "",
                        "icon_url": rl.get("images_symbol") or rl.get("icon_url") or "",
                        "scryfall_uri": "",
                    })
    except Exception:
        pass

    return sets


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@router.get("")
def get_sets(
    game: Optional[str] = Query(None, description="'mtg' or 'pokemon'"),
    search: Optional[str] = Query(None, description="Name search"),
    set_type: Optional[str] = Query(None),
    game_type: Optional[str] = Query(None, description="MTG game type category"),
    year: Optional[str] = Query(None),
    limit: int = Query(5000, ge=1, le=10000),
    offset: int = Query(0, ge=0),
):
    sets = load_sets_catalog()

    if game:
        gl = game.lower()
        sets = [s for s in sets if s["game"].lower().startswith(gl)]
    if search:
        sl = search.lower()
        sets = [s for s in sets if sl in s["name"].lower() or sl in s["code"].lower()]
    if set_type:
        sets = [s for s in sets if s["set_type"].lower() == set_type.lower()]
    if game_type:
        sets = [s for s in sets if s["game_type"].lower() == game_type.lower()]
    if year:
        sets = [s for s in sets if s["year"] == year]

    total = len(sets)
    page = sets[offset: offset + limit]
    return {"sets": page, "total": total}


@router.get("/cache-summary")
def get_cache_summary():
    """
    Return cached card counts per game, keyed by set_code (lowercase).
    { "mtg": { "lea": 295, ... }, "pokemon": { "base1": 102, ... } }
    """
    from ..legacy.fallback_manager import MTG_CARDS_CSV, POKEMON_CARDS_CSV

    mtg: Dict[str, int] = {}
    pokemon: Dict[str, int] = {}

    try:
        if os.path.exists(MTG_CARDS_CSV):
            with open(MTG_CARDS_CSV, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    code = (row.get("set_code") or "").lower().strip()
                    if code:
                        mtg[code] = mtg.get(code, 0) + 1
    except Exception:
        pass

    try:
        if os.path.exists(POKEMON_CARDS_CSV):
            with open(POKEMON_CARDS_CSV, "r", encoding="utf-8") as f:
                for row in csv.DictReader(f):
                    # Pokémon card IDs are "{set_id}-{number}", e.g. "base1-1"
                    cid = (row.get("id") or "").strip()
                    code = cid.split("-", 1)[0].lower() if "-" in cid else ""
                    if code:
                        pokemon[code] = pokemon.get(code, 0) + 1
    except Exception:
        pass

    return {"mtg": mtg, "pokemon": pokemon}


@router.post("/sync/mtg")
def sync_mtg_sets():
    """
    Fetch all MTG sets from Scryfall and update backend/legacy/fallback_data/MTG/mtgsets.csv.
    Returns a summary of changes: { total, added, updated, unchanged }.
    """
    try:
        raw_sets = _fetch_scryfall_sets()
    except Exception as exc:
        return JSONResponse(status_code=502, content={"error": f"Scryfall request failed: {exc}"})

    if not raw_sets:
        return JSONResponse(status_code=502, content={"error": "Scryfall returned no sets"})

    existing = _load_existing_sets_csv(_MTG_SETS_CSV)

    added: List[str] = []
    updated: List[str] = []
    unchanged: List[str] = []
    merged: Dict[str, Dict] = {}

    for s in raw_sets:
        code = s.get("code", "")
        if not code:
            continue
        flat = _flatten_set(s)
        if code not in existing:
            added.append(code)
            merged[code] = flat
        elif _sets_differ(existing[code], flat):
            updated.append(code)
            merged[code] = flat
        else:
            unchanged.append(code)
            merged[code] = existing[code]  # keep existing row as-is

    # Also preserve any codes in existing CSV that Scryfall no longer returns
    for code, row in existing.items():
        if code not in merged:
            merged[code] = row

    _write_sets_csv(_MTG_SETS_CSV, list(merged.values()))

    return {
        "total": len(merged),
        "added": len(added),
        "updated": len(updated),
        "unchanged": len(unchanged),
        "csv_path": _MTG_SETS_CSV,
    }


@router.post("/sync/pokemon")
def sync_pokemon_sets():
    """
    Fetch all Pokémon sets from the Pokémon TCG API and update pokemonsets.csv.
    Returns { total, added, updated, unchanged }.
    """
    from ..legacy.fallback_manager import POKEMON_SETS_CSV, _get_existing_ids
    from ..config import settings as cfg
    import json as _json

    headers: Dict[str, str] = {}
    if cfg.pokemontcg_api_key:
        headers["X-Api-Key"] = cfg.pokemontcg_api_key

    # Fetch all pages
    all_sets: List[Dict] = []
    page = 1
    page_size = 250
    try:
        while True:
            resp = requests.get(
                "https://api.pokemontcg.io/v2/sets",
                params={"pageSize": page_size, "page": page},
                headers=headers,
                timeout=30,
            )
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("data", [])
            all_sets.extend(batch)
            if len(all_sets) >= data.get("totalCount", 0) or not batch:
                break
            page += 1
            time.sleep(0.05)
    except requests.RequestException as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

    if not all_sets:
        return JSONResponse(status_code=502, content={"error": "Pokémon TCG API returned no sets"})

    # Load existing by id
    existing_ids = _get_existing_ids(POKEMON_SETS_CSV, "id")

    fieldnames = ["id", "name", "series", "printedTotal", "total", "legalities",
                  "ptcgoCode", "releaseDate", "updatedAt", "images", "tcgplayer"]

    added = 0
    updated = 0
    unchanged = 0

    # We'll collect all rows for a full rewrite (so updated sets replace old ones)
    all_rows: List[Dict] = []
    seen_ids: set = set()

    for s in all_sets:
        sid = str(s.get("id", ""))
        if not sid:
            continue
        flat = {
            "id": sid,
            "name": s.get("name", ""),
            "series": s.get("series", ""),
            "printedTotal": s.get("printedTotal", 0),
            "total": s.get("total", 0),
            "legalities": _json.dumps(s.get("legalities", {})),
            "ptcgoCode": s.get("ptcgoCode", ""),
            "releaseDate": s.get("releaseDate", ""),
            "updatedAt": s.get("updatedAt", ""),
            "images": _json.dumps(s.get("images", {})),
            "tcgplayer": _json.dumps(s.get("tcgplayer", {})),
        }
        if sid not in existing_ids:
            added += 1
        else:
            updated += 1   # treat all existing as updated (prices/counts may change)
        seen_ids.add(sid)
        all_rows.append(flat)

    unchanged = len(existing_ids) - len(seen_ids.intersection(existing_ids))

    # Write full file (merge: new API data wins, preserves any local-only rows if needed)
    os.makedirs(os.path.dirname(POKEMON_SETS_CSV), exist_ok=True)
    with open(POKEMON_SETS_CSV, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, extrasaction="ignore")
        writer.writeheader()
        for row in all_rows:
            writer.writerow({fn: row.get(fn, "") for fn in fieldnames})

    return {
        "total": len(all_rows),
        "added": added,
        "updated": updated,
        "unchanged": unchanged,
        "csv_path": POKEMON_SETS_CSV,
    }


@router.post("/{set_code}/cache-cards")
def cache_set_cards(set_code: str, game: str = Query("mtg", description="'mtg' or 'pokemon'")):
    """
    Fetch every card in a set and store in the local fallback cache.
    game='mtg'     → Scryfall → mtgcards.csv
    game='pokemon' → Pokémon TCG API → pokemoncards.csv

    Returns { set_code, set_name, total_fetched, stored, skipped }.
    """
    sc = set_code.lower().strip()

    if game.lower() == "pokemon":
        return _cache_pokemon_cards(sc)
    return _cache_mtg_cards(sc)


def _cache_mtg_cards(sc: str):
    from ..legacy.fallback_manager import MTG_CARDS_CSV, _get_existing_ids, store_mtg_card

    url: Optional[str] = (
        f"https://api.scryfall.com/cards/search"
        f"?q=set%3A{sc}&unique=prints&order=collector_number"
    )
    all_cards: List[Dict] = []
    set_name = ""

    try:
        while url:
            resp = requests.get(url, timeout=30)
            if resp.status_code == 404:
                return JSONResponse(status_code=404, content={"error": f"Set '{sc}' not found on Scryfall"})
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("data", [])
            all_cards.extend(batch)
            if not set_name and batch:
                set_name = batch[0].get("set_name", sc.upper())
            url = data.get("next_page") if data.get("has_more") else None
            if url:
                time.sleep(0.05)
    except requests.RequestException as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

    existing_ids = _get_existing_ids(MTG_CARDS_CSV, "id")
    stored = 0
    skipped = 0
    for card in all_cards:
        cid = str(card.get("id", ""))
        if cid and cid in existing_ids:
            skipped += 1
            continue
        try:
            store_mtg_card(card)
            existing_ids.add(cid)
            stored += 1
        except Exception:
            skipped += 1

    return {"set_code": sc, "set_name": set_name, "total_fetched": len(all_cards), "stored": stored, "skipped": skipped}


def _cache_pokemon_cards(sc: str):
    from ..legacy.fallback_manager import POKEMON_CARDS_CSV, _get_existing_ids, store_pokemon_card
    from ..config import settings as cfg

    headers: Dict[str, str] = {}
    if cfg.pokemontcg_api_key:
        headers["X-Api-Key"] = cfg.pokemontcg_api_key

    all_cards: List[Dict] = []
    set_name = ""
    page = 1
    page_size = 250

    try:
        while True:
            resp = requests.get(
                "https://api.pokemontcg.io/v2/cards",
                params={"q": f"set.id:{sc}", "pageSize": page_size, "page": page},
                headers=headers,
                timeout=30,
            )
            if resp.status_code == 404:
                return JSONResponse(status_code=404, content={"error": f"Set '{sc}' not found in Pokémon TCG API"})
            resp.raise_for_status()
            data = resp.json()
            batch = data.get("data", [])
            all_cards.extend(batch)
            if not set_name and batch:
                set_name = (batch[0].get("set") or {}).get("name", sc.upper())
            if len(all_cards) >= data.get("totalCount", 0) or not batch:
                break
            page += 1
            time.sleep(0.05)
    except requests.RequestException as exc:
        return JSONResponse(status_code=502, content={"error": str(exc)})

    existing_ids = _get_existing_ids(POKEMON_CARDS_CSV, "id")
    stored = 0
    skipped = 0
    for card in all_cards:
        cid = str(card.get("id", ""))
        if cid and cid in existing_ids:
            skipped += 1
            continue
        try:
            store_pokemon_card(card)
            existing_ids.add(cid)
            stored += 1
        except Exception:
            skipped += 1

    return {"set_code": sc, "set_name": set_name, "total_fetched": len(all_cards), "stored": stored, "skipped": skipped}


@router.get("/{set_code}/owned-count")
def get_owned_count(
    set_code: str,
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    from ..models.card import CollectionCard
    from ..models.owner import Owner
    owner = db.query(Owner).filter(Owner.owner_id == owner_id).first()
    if not owner:
        return {"set_code": set_code, "owned_count": 0}
    owned = (
        db.query(CollectionCard)
        .filter(
            CollectionCard.owner_id == owner.id,
            CollectionCard.profile_id == profile_id,
            CollectionCard.set_code == set_code.lower(),
        )
        .count()
    )
    return {"set_code": set_code, "owned_count": owned}
