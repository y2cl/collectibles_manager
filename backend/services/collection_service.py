"""
Collection business logic: duplicate handling, merge strategies, backup.
Ported from collectiman.py — no Streamlit dependencies.
"""
import re
import shutil
import logging
from datetime import datetime
from typing import Optional

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


# ── Owner / profile helpers ───────────────────────────────────────────────────

def sanitize_owner_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


def owner_folder_label(name: str) -> str:
    base = (name or "").strip()
    if not base:
        return ""
    suffix = "'" if base.endswith("s") else "s"
    return f"{base}{suffix} Collection"


def sanitize_profile_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "default"


# ── Merge helpers ─────────────────────────────────────────────────────────────

def merge_paid(existing_paid: float, new_paid: float, strategy: str) -> float:
    """Combine Paid values per strategy: 'sum' | 'average' | 'ignore'."""
    try:
        ep = float(existing_paid or 0.0)
    except Exception:
        ep = 0.0
    try:
        np_ = float(new_paid or 0.0)
    except Exception:
        np_ = 0.0
    strat = (strategy or "sum").lower()
    if strat == "average":
        return np_ if ep == 0 else (ep + np_) / 2.0
    if strat == "ignore":
        return ep
    return ep + np_  # default: sum


# ── Duplicate strategy ────────────────────────────────────────────────────────

def find_duplicate(db: Session, owner_db_id: int, profile_id: str,
                   game: str, name: str, set_code: str, card_number: str, variant: str, is_proxy: bool = False):
    """Return an existing CollectionCard row that matches the card identity, or None.

    Matching logic:
    - owner_id, profile_id, game, name must match exactly
    - is_proxy must match (proxy cards are treated as separate variants)
    - set_code, card_number, variant: if the existing card has an empty value,
      it matches any incoming value (to handle cards imported before set_code was populated)
    """
    from ..models.card import CollectionCard
    from sqlalchemy import or_, and_

    # Normalize inputs
    set_code = (set_code or "").strip()
    card_number = (card_number or "").strip()
    variant = (variant or "").strip()
    is_proxy = bool(is_proxy)

    # Query all potential matches by name/game/owner
    candidates = (
        db.query(CollectionCard)
        .filter(
            CollectionCard.owner_id == owner_db_id,
            CollectionCard.profile_id == profile_id,
            CollectionCard.game == game,
            CollectionCard.name == name,
        )
        .all()
    )

    # Find the best match
    for card in candidates:
        card_set_code = (card.set_code or "").strip()
        card_number_val = (card.card_number or "").strip()
        card_variant = (card.variant or "").strip()
        card_is_proxy = bool(card.is_proxy)

        # Check is_proxy: must match (proxy and non-proxy are separate variants)
        proxy_match = card_is_proxy == is_proxy

        # Check set_code: match if either is empty or both match
        set_match = (not card_set_code) or (not set_code) or (card_set_code == set_code)

        # Check card_number: match if either is empty or both match
        number_match = (not card_number_val) or (not card_number) or (card_number_val == card_number)

        # Check variant: match if either is empty or both match (case-insensitive)
        variant_match = (not card_variant) or (not variant) or (card_variant.lower() == variant.lower())

        if proxy_match and set_match and number_match and variant_match:
            return card

    return None


def add_card(db: Session, owner_id_slug: str, profile_id: str, card_data: dict,
             duplicate_strategy: str = "merge", paid_merge_strategy: str = "sum"):
    """
    Add a card to the collection. Applies duplicate_strategy:
    - 'merge': increment quantity + merge paid on duplicate
    - 'separate': always insert a new row
    Returns the CollectionCard instance (new or updated).
    """
    from ..models.card import CollectionCard
    from ..models.owner import Owner

    # Normalize variant: if empty, derive from finish for MTG cards
    variant = card_data.get("variant", "")
    finish = card_data.get("finish", "")
    if not variant and finish:
        variant = finish
    elif not variant and card_data.get("game") == "Magic: The Gathering":
        # Default to nonfoil for MTG if no variant or finish specified
        variant = "nonfoil"
    card_data["variant"] = variant

    owner_row = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner_row:
        raise ValueError(f"Owner '{owner_id_slug}' not found")

    if duplicate_strategy == "merge":
        existing = find_duplicate(
            db, owner_row.id, profile_id,
            card_data.get("game", ""),
            card_data.get("name", ""),
            card_data.get("set_code", ""),
            card_data.get("card_number", ""),
            card_data.get("variant", ""),
            card_data.get("is_proxy", False),
        )
        if existing:
            existing.quantity = (existing.quantity or 1) + card_data.get("quantity", 1)
            existing.paid = merge_paid(existing.paid or 0.0, card_data.get("paid", 0.0), paid_merge_strategy)
            # Update rich MTG data fields if they were provided
            if card_data.get("mana_cost"):
                existing.mana_cost = card_data.get("mana_cost")
            if card_data.get("type_line"):
                existing.type_line = card_data.get("type_line")
            if card_data.get("oracle_text"):
                existing.oracle_text = card_data.get("oracle_text")
            if card_data.get("keywords"):
                existing.keywords = card_data.get("keywords")
            if card_data.get("power"):
                existing.power = card_data.get("power")
            if card_data.get("toughness"):
                existing.toughness = card_data.get("toughness")
            if card_data.get("rarity"):
                existing.rarity = card_data.get("rarity")
            if card_data.get("color_identity"):
                existing.color_identity = card_data.get("color_identity")
            if card_data.get("finish"):
                existing.finish = card_data.get("finish")
            if card_data.get("scryfall_id"):
                existing.scryfall_id = card_data.get("scryfall_id")
            if card_data.get("tcg_link"):
                existing.tcg_link = card_data.get("tcg_link")
            # Update is_proxy if provided
            if card_data.get("is_proxy") is not None:
                existing.is_proxy = card_data.get("is_proxy")
            # Update new MTG fields
            if card_data.get("frame_effects"):
                existing.frame_effects = card_data.get("frame_effects")
            if card_data.get("full_art") is not None:
                existing.full_art = card_data.get("full_art")
            if card_data.get("promo_types"):
                existing.promo_types = card_data.get("promo_types")
            if card_data.get("scryfall_data"):
                existing.scryfall_data = card_data.get("scryfall_data")
            if card_data.get("legalities"):
                existing.legalities = card_data.get("legalities")
            db.commit()
            db.refresh(existing)
            return existing

    new_card = CollectionCard(
        owner_id=owner_row.id,
        profile_id=profile_id,
        game=card_data.get("game", ""),
        sport=card_data.get("sport"),
        name=card_data.get("name", ""),
        set_name=card_data.get("set_name", card_data.get("set", "")),
        set_code=card_data.get("set_code", ""),
        card_number=card_data.get("card_number", ""),
        year=card_data.get("year", ""),
        # Rich MTG data fields (for Cube Maker sync)
        scryfall_id=card_data.get("scryfall_id"),
        mana_cost=card_data.get("mana_cost"),
        type_line=card_data.get("type_line"),
        oracle_text=card_data.get("oracle_text"),
        keywords=card_data.get("keywords"),
        power=card_data.get("power"),
        toughness=card_data.get("toughness"),
        rarity=card_data.get("rarity"),
        color_identity=card_data.get("color_identity"),
        finish=card_data.get("finish"),
        tcg_link=card_data.get("tcg_link"),
        frame_effects=card_data.get("frame_effects"),
        full_art=card_data.get("full_art", False),
        promo_types=card_data.get("promo_types"),
        scryfall_data=card_data.get("scryfall_data"),
        legalities=card_data.get("legalities"),
        link=card_data.get("link", ""),
        image_url=card_data.get("image_url", ""),
        manufacturer=card_data.get("manufacturer"),
        upc=card_data.get("upc"),
        grading_company=card_data.get("grading_company"),
        grade=card_data.get("grade"),
        serial_number=card_data.get("serial_number"),
        print_run=card_data.get("print_run"),
        rc=card_data.get("rc", False),
        price_low=card_data.get("price_low"),
        price_mid=card_data.get("price_mid"),
        price_market=card_data.get("price_market"),
        price_usd=card_data.get("price_usd", 0.0),
        price_usd_foil=card_data.get("price_usd_foil", 0.0),
        price_usd_etched=card_data.get("price_usd_etched", 0.0),
        quantity=card_data.get("quantity", 1),
        variant=card_data.get("variant", ""),
        paid=card_data.get("paid", 0.0),
        signed=card_data.get("signed", ""),
        altered=card_data.get("altered", ""),
        notes=card_data.get("notes", ""),
        is_proxy=card_data.get("is_proxy", False),
        # Coin-specific fields
        denomination=card_data.get("denomination"),
        country=card_data.get("country"),
        coin_or_bill=card_data.get("coin_or_bill"),
        silver_amount=card_data.get("silver_amount"),
        mint_mark=card_data.get("mint_mark"),
        timestamp=datetime.utcnow(),
    )
    db.add(new_card)
    db.commit()
    db.refresh(new_card)
    return new_card


# ── Database backup ───────────────────────────────────────────────────────────

def backup_database(db_path: str, retention: int = 5) -> Optional[str]:
    """
    Create a timestamped copy of the SQLite DB file.
    Deletes old backups beyond the retention count.
    Returns the backup file path on success, None on failure.
    """
    import glob
    import os

    try:
        ts = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
        backup_path = db_path.replace(".db", f"_backup_{ts}.db")
        shutil.copy2(db_path, backup_path)
        logger.info("Database backed up to %s", backup_path)

        # Remove old backups beyond retention
        pattern = db_path.replace(".db", "_backup_*.db")
        backups = sorted(glob.glob(pattern))
        for old in backups[:-retention]:
            try:
                os.remove(old)
            except Exception:
                pass

        return backup_path
    except Exception as e:
        logger.error("Backup failed: %s", e)
        return None
