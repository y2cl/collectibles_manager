"""
CSV import service with ambiguity resolution.
Ported from collectiman.py::render_import_export_tab logic — no Streamlit.
"""
import csv
import io
import logging
from typing import List, Dict, Tuple, Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

# CSV columns exported by the app (same order as original)
COLLECTION_COLUMNS = [
    "game", "name", "set", "set_code", "card_number", "year", "link", "image_url",
    "price_low", "price_mid", "price_market", "price_usd", "price_usd_foil",
    "price_usd_etched", "quantity", "variant", "total_value", "paid",
    "signed", "altered", "notes", "timestamp",
]

WATCHLIST_COLUMNS = COLLECTION_COLUMNS + ["target_price"]


def _to_float(v) -> float:
    try:
        return float(v) if v not in (None, "", "None", "nan") else 0.0
    except Exception:
        return 0.0


def _to_int(v, default: int = 1) -> int:
    try:
        return int(float(v)) if v not in (None, "", "None") else default
    except Exception:
        return default


def _detect_game(row: Dict) -> str:
    """Guess game type from a CSV row."""
    game = (row.get("game") or "").strip()
    if game:
        return game
    name = (row.get("name") or "").lower()
    if any(w in name for w in ["pikachu", "charizard", "bulbasaur", "pokémon", "pokemon"]):
        return "Pokémon"
    return "Magic: The Gathering"


def _row_to_card_data(row: Dict) -> Dict:
    return {
        "game": _detect_game(row),
        "name": row.get("name", ""),
        "set_name": row.get("set", ""),
        "set_code": row.get("set_code", ""),
        "card_number": row.get("card_number", "") or row.get("collector_number", ""),
        "year": row.get("year", ""),
        "link": row.get("link", ""),
        "image_url": row.get("image_url", ""),
        "price_low": _to_float(row.get("price_low")),
        "price_mid": _to_float(row.get("price_mid")),
        "price_market": _to_float(row.get("price_market")),
        "price_usd": _to_float(row.get("price_usd")),
        "price_usd_foil": _to_float(row.get("price_usd_foil")),
        "price_usd_etched": _to_float(row.get("price_usd_etched")),
        "quantity": _to_int(row.get("quantity"), 1),
        "variant": row.get("variant", ""),
        "paid": _to_float(row.get("paid")),
        "signed": row.get("signed", ""),
        "altered": row.get("altered", ""),
        "notes": row.get("notes", ""),
        "target_price": _to_float(row.get("target_price")),
    }


def import_csv(
    file_content: bytes,
    owner_id_slug: str,
    profile_id: str,
    db: Session,
    duplicate_strategy: str = "merge",
    paid_merge_strategy: str = "sum",
) -> Tuple[int, int, List[Dict]]:
    """
    Parse a CSV import file.
    Returns (imported_count, ambiguous_count, ambiguity_dicts).
    Unambiguous rows are inserted immediately.
    Ambiguous rows are stored in the import_ambiguities table for later resolution.
    """
    from ..models.owner import Owner
    from ..models.settings import ImportAmbiguity
    from ..services.collection_service import add_card
    from ..services.search_service import search_mtg, search_pokemon

    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise ValueError(f"Owner '{owner_id_slug}' not found")

    text = file_content.decode("utf-8-sig", errors="replace")
    reader = csv.DictReader(io.StringIO(text))

    imported = 0
    ambiguous_rows: List[Dict] = []

    for row in reader:
        if not any(row.values()):
            continue
        card_data = _row_to_card_data(row)
        name = card_data.get("name", "").strip()
        if not name:
            continue

        game = card_data.get("game", "")
        set_code = card_data.get("set_code", "")
        card_number = card_data.get("card_number", "")

        # Try to find a single authoritative match via search
        candidates: List[Dict] = []
        try:
            if game == "Pokémon":
                results, _, _, _ = search_pokemon(name, set_code, card_number, db=db)
                candidates = results
            else:
                results, _, _, _ = search_mtg(name, set_code, card_number, db=db)
                candidates = results
        except Exception as e:
            logger.warning("Search during import failed for '%s': %s", name, e)

        if len(candidates) == 1:
            # Merge search result data with import data (import values take precedence)
            merged = {**candidates[0], **{k: v for k, v in card_data.items() if v}}
            try:
                add_card(db, owner_id_slug, profile_id, merged,
                         duplicate_strategy, paid_merge_strategy)
                imported += 1
            except Exception as e:
                logger.error("Failed to insert card '%s': %s", name, e)
        elif len(candidates) == 0:
            # No match found — insert with import data as-is
            try:
                add_card(db, owner_id_slug, profile_id, card_data,
                         duplicate_strategy, paid_merge_strategy)
                imported += 1
            except Exception as e:
                logger.error("Failed to insert card '%s': %s", name, e)
        else:
            # Multiple candidates — store for user disambiguation
            ambiguity = ImportAmbiguity(
                owner_id=owner.id,
                profile_id=profile_id,
                row_data=card_data,
                candidates=candidates[:10],  # cap at 10 candidates
            )
            db.add(ambiguity)
            db.flush()
            ambiguous_rows.append({
                "id": ambiguity.id,
                "row_data": card_data,
                "candidates": candidates[:10],
            })

    db.commit()
    return imported, len(ambiguous_rows), ambiguous_rows


def resolve_ambiguities(
    owner_id_slug: str,
    profile_id: str,
    resolutions: List[Dict],
    db: Session,
    duplicate_strategy: str = "merge",
    paid_merge_strategy: str = "sum",
) -> int:
    """
    Commit user-resolved ambiguities to the collection.
    Each resolution: { ambiguity_id, selected_candidate, quantity, variant, paid }
    Returns count of rows committed.
    """
    from ..models.settings import ImportAmbiguity
    from ..services.collection_service import add_card

    committed = 0
    for res in resolutions:
        ambiguity_id = res.get("ambiguity_id")
        amb = db.query(ImportAmbiguity).filter(ImportAmbiguity.id == ambiguity_id).first()
        if not amb:
            continue

        card_data = {**res.get("selected_candidate", {})}
        card_data["quantity"] = res.get("quantity", 1)
        card_data["variant"] = res.get("variant", "")
        card_data["paid"] = res.get("paid", 0.0)

        try:
            add_card(db, owner_id_slug, profile_id, card_data,
                     duplicate_strategy, paid_merge_strategy)
            db.delete(amb)
            committed += 1
        except Exception as e:
            logger.error("Failed to commit resolution for ambiguity %d: %s", ambiguity_id, e)

    db.commit()
    return committed
