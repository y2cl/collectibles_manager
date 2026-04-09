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
                   game: str, name: str, set_code: str, card_number: str, variant: str):
    """Return an existing CollectionCard row that matches the card identity, or None."""
    from ..models.card import CollectionCard
    return (
        db.query(CollectionCard)
        .filter(
            CollectionCard.owner_id == owner_db_id,
            CollectionCard.profile_id == profile_id,
            CollectionCard.game == game,
            CollectionCard.name == name,
            CollectionCard.set_code == set_code,
            CollectionCard.card_number == card_number,
            CollectionCard.variant == variant,
        )
        .first()
    )


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
        )
        if existing:
            existing.quantity = (existing.quantity or 1) + card_data.get("quantity", 1)
            existing.paid = merge_paid(existing.paid or 0.0, card_data.get("paid", 0.0), paid_merge_strategy)
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
