"""
CSV import service with ambiguity resolution.
Ported from collectiman.py::render_import_export_tab logic — no Streamlit.

MTG import format (new):
  Name, Set, Set Code, Collector Number, Scryfall_ID, Quantity,
  Foil, Etched, Signed, Altered, Notes

  - Foil / Etched: yes/no — used to derive the card variant.
      Etched=yes  → variant "etched"
      Foil=yes    → variant "foil"
      both no     → variant "nonfoil"
  - Signed / Altered: yes/no flags.  Use the Notes column to record
      specifics (e.g. "Signed by artist at GP Vegas 2019").
  - Scryfall_ID: when present the card is fetched directly from Scryfall
      to populate set, image, prices etc. — no fuzzy-search ambiguity.

Old-style exports (with a `variant` column, no foil/etched columns) are
still accepted; header detection is case-insensitive and space-tolerant.
"""
import csv
import io
import logging
from typing import List, Dict, Tuple, Optional

import requests as _requests
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

# New MTG import template columns (what we tell users to use)
MTG_IMPORT_COLUMNS = [
    "Name", "Set", "Set Code", "Collector Number", "Scryfall_ID",
    "Quantity", "Foil", "Etched", "Signed", "Altered", "Notes",
]


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


def _is_yes(v) -> bool:
    """Accept yes / y / true / 1 (case-insensitive) as truthy."""
    return (v or "").strip().lower() in ("yes", "y", "true", "1")


def _normalize_row(row: Dict) -> Dict:
    """Lowercase keys and replace spaces with underscores for flexible header matching."""
    return {k.strip().lower().replace(" ", "_"): (v or "").strip() for k, v in row.items()}


def _detect_game(row: Dict) -> str:
    """Guess game type from a normalised CSV row."""
    game = (row.get("game") or "").strip()
    if game:
        return game
    name = (row.get("name") or "").lower()
    if any(w in name for w in ["pikachu", "charizard", "bulbasaur", "pokémon", "pokemon"]):
        return "Pokémon"
    return "Magic: The Gathering"


def _derive_variant(row: Dict) -> str:
    """
    Derive the MTG variant from Foil / Etched yes-no columns.
    Falls back to the legacy `variant` column if neither column is present.
    """
    has_foil_col   = row.get("foil")   is not None
    has_etched_col = row.get("etched") is not None

    if has_foil_col or has_etched_col:
        if _is_yes(row.get("etched")):
            return "etched"
        if _is_yes(row.get("foil")):
            return "foil"
        return "nonfoil"

    # Legacy format — use the variant column as-is
    return row.get("variant", "")


def _fetch_scryfall_card(scryfall_id: str) -> Optional[Dict]:
    """
    Fetch a single card by Scryfall UUID.
    Returns a card_data-compatible dict, or None on failure.
    """
    try:
        resp = _requests.get(
            f"https://api.scryfall.com/cards/{scryfall_id}",
            timeout=15,
        )
        if not resp.ok:
            logger.warning("Scryfall ID lookup failed (%s): %s", resp.status_code, scryfall_id)
            return None
        c = resp.json()
        prices = c.get("prices") or {}

        img = ""
        iu = c.get("image_uris") or {}
        faces = c.get("card_faces") or []
        if iu:
            img = iu.get("normal") or iu.get("large") or ""
        elif faces:
            img = (faces[0].get("image_uris") or {}).get("normal") or ""

        def _p(key):
            try:
                v = prices.get(key)
                return float(v) if v else 0.0
            except Exception:
                return 0.0

        # Pull artist — handle double-faced cards where it lives inside card_faces
        artist = c.get("artist") or ""
        if not artist and faces:
            artist = (faces[0].get("artist") or "")

        return {
            "game":             "Magic: The Gathering",
            "name":             c.get("name", ""),
            "set_name":         c.get("set_name", ""),
            "set_code":         c.get("set", ""),
            "card_number":      c.get("collector_number", ""),
            "year":             str(c.get("released_at", ""))[:4],
            "link":             c.get("scryfall_uri", ""),
            "image_url":        img,
            "artist":           artist,
            "price_usd":        _p("usd"),
            "price_usd_foil":   _p("usd_foil"),
            "price_usd_etched": _p("usd_etched"),
        }
    except Exception as e:
        logger.warning("Scryfall ID fetch error for %s: %s", scryfall_id, e)
        return None


def _resolve_signed(signed_val: str, artist: str) -> str:
    """
    If the import row said Signed=yes (stored as the literal string "yes"),
    replace it with the card's artist name so the signed field is immediately
    meaningful and editable.  Any non-"yes" value (e.g. a name already typed
    by the user) is returned unchanged.
    """
    if signed_val == "yes" and artist:
        return artist
    return signed_val


def _row_to_card_data(row: Dict) -> Dict:
    """
    Convert a normalised CSV row to a card_data dict.
    Accepts both the new MTG format (Foil/Etched/Scryfall_ID columns)
    and the legacy export format (variant column).
    """
    variant = _derive_variant(row)

    signed  = "yes" if _is_yes(row.get("signed"))  else row.get("signed", "")
    altered = "yes" if _is_yes(row.get("altered")) else row.get("altered", "")

    return {
        "game":            _detect_game(row),
        "name":            row.get("name", ""),
        "set_name":        row.get("set", "") or row.get("set_name", ""),
        "set_code":        row.get("set_code", ""),
        "card_number":     row.get("collector_number", "") or row.get("card_number", ""),
        "year":            row.get("year", ""),
        "link":            row.get("link", ""),
        "image_url":       row.get("image_url", ""),
        "price_low":       _to_float(row.get("price_low")),
        "price_mid":       _to_float(row.get("price_mid")),
        "price_market":    _to_float(row.get("price_market")),
        "price_usd":       _to_float(row.get("price_usd")),
        "price_usd_foil":  _to_float(row.get("price_usd_foil")),
        "price_usd_etched":_to_float(row.get("price_usd_etched")),
        "quantity":        _to_int(row.get("quantity"), 1),
        "variant":         variant,
        "paid":            _to_float(row.get("paid")),
        "signed":          signed,
        "altered":         altered,
        "notes":           row.get("notes", ""),
        "target_price":    _to_float(row.get("target_price")),
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

    for raw_row in reader:
        if not any(raw_row.values()):
            continue

        # Normalise headers: lowercase + underscores so "Set Code" == "set_code" etc.
        row = _normalize_row(raw_row)

        card_data = _row_to_card_data(row)
        name = card_data.get("name", "").strip()
        if not name:
            continue

        game = card_data.get("game", "")

        # ── Scryfall ID fast-path ────────────────────────────────────────────
        # If the row carries a Scryfall UUID we can fetch the card directly and
        # skip the fuzzy-search / ambiguity flow entirely.
        scryfall_id = row.get("scryfall_id", "").strip()
        if scryfall_id and game == "Magic: The Gathering":
            api_data = _fetch_scryfall_card(scryfall_id)
            if api_data:
                # API data fills gaps; CSV-provided values (quantity, variant,
                # paid, signed, altered, notes) take precedence.
                merged = {
                    **api_data,
                    **{k: v for k, v in card_data.items() if v not in ("", 0, 0.0, None)},
                }
                # Auto-fill signed with artist name when user said Signed=yes
                merged["signed"] = _resolve_signed(merged.get("signed", ""), api_data.get("artist", ""))
                try:
                    add_card(db, owner_id_slug, profile_id, merged,
                             duplicate_strategy, paid_merge_strategy)
                    imported += 1
                except Exception as e:
                    logger.error("Failed to insert card '%s' (Scryfall ID %s): %s",
                                 name, scryfall_id, e)
                continue  # done with this row
            # If the Scryfall lookup failed, fall through to the normal search path
            logger.warning("Scryfall ID lookup failed for '%s' (%s); falling back to search",
                           name, scryfall_id)

        # ── Normal search-based path ─────────────────────────────────────────
        set_code = card_data.get("set_code", "")
        card_number = card_data.get("card_number", "")

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
            # Auto-fill signed with artist name when user said Signed=yes
            merged["signed"] = _resolve_signed(merged.get("signed", ""), candidates[0].get("artist", ""))
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
                candidates=candidates[:10],
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

        # selected_candidate is None/empty when the user chose "skip"
        candidate = res.get("selected_candidate")
        if not candidate:
            # User skipped — just delete the ambiguity record without adding to collection
            db.delete(amb)
            committed += 1
            continue

        card_data = {**candidate}
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
