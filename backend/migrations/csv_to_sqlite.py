#!/usr/bin/env python3
"""
One-shot migration script: import existing CSV collections into SQLite.

Usage (from the backend/ directory):
    python -m migrations.csv_to_sqlite [--collections-dir ../collections] [--upsert]

Options:
    --collections-dir  Path to the collections/ folder  (default: ../collections)
    --upsert           Skip rows that already exist in the DB instead of failing
    --dry-run          Parse and report counts without writing anything
"""
import argparse
import csv
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

# Make sure the backend package is importable when run directly
_backend_dir = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_backend_dir.parent))

from backend.database import SessionLocal, create_all_tables
from backend.models.owner import Owner, Profile, OwnerPreferences
from backend.models.card import CollectionCard, WatchlistItem
from backend.models.settings import AppSettings


# ── Helpers ───────────────────────────────────────────────────────────────────

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


def sanitize_owner_id(name: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")


def owner_folder_label(name: str) -> str:
    base = (name or "").strip()
    if not base:
        return ""
    suffix = "'" if base.endswith("s") else "s"
    return f"{base}{suffix} Collection"


def parse_profile_from_filename(owner_id: str, filename: str) -> str:
    """
    Derive profile_id from filenames like:
      john-vintage-mtg_collection.csv  → "vintage"
      john-mtg_collection.csv          → "default"
    """
    stem = filename.replace("_collection.csv", "").replace("_watchlist.csv", "")
    prefix = f"{owner_id}-"
    if stem.startswith(prefix):
        remainder = stem[len(prefix):]
        # remainder could be "mtg", "pokemon", "baseball", or "{profile}-mtg", etc.
        game_slugs = ["mtg", "pokemon", "baseball", "unified"]
        for gs in game_slugs:
            if remainder == gs:
                return "default"
            if remainder.endswith(f"-{gs}"):
                return remainder[: -(len(gs) + 1)]
    return "default"


def game_from_filename(filename: str) -> str:
    fn = filename.lower()
    if "pokemon" in fn:
        return "Pokémon"
    if "baseball" in fn or "sports" in fn:
        return "Sports Cards"
    return "Magic: The Gathering"


def _parse_timestamp(v: str) -> datetime:
    if not v:
        return datetime.utcnow()
    try:
        return datetime.fromisoformat(v)
    except Exception:
        return datetime.utcnow()


# ── Main migration ────────────────────────────────────────────────────────────

def migrate(collections_dir: str, upsert: bool = False, dry_run: bool = False, unified_only: bool = False):
    collections_path = Path(collections_dir).resolve()
    if not collections_path.exists():
        print(f"ERROR: collections dir not found: {collections_path}")
        sys.exit(1)

    create_all_tables()
    db = SessionLocal()

    stats = {
        "owners": 0, "profiles": 0, "cards": 0,
        "watchlist": 0, "skipped": 0,
    }

    try:
        # ── Load api_config.json ──────────────────────────────────────────────
        api_config_path = collections_path.parent / "api_config.json"
        api_config = {}
        if api_config_path.exists():
            try:
                with open(api_config_path, encoding="utf-8") as f:
                    api_config = json.load(f)
                print(f"  Loaded api_config.json from {api_config_path}")
            except Exception as e:
                print(f"  WARNING: Could not load api_config.json: {e}")

        if not dry_run:
            existing_settings = db.query(AppSettings).first()
            if not existing_settings:
                db.add(AppSettings(api_source_config=api_config))
                db.commit()

        # ── Load owner_settings.json ──────────────────────────────────────────
        owner_prefs_path = collections_path / "owner_settings.json"
        owner_prefs_data = {}
        if owner_prefs_path.exists():
            try:
                with open(owner_prefs_path, encoding="utf-8") as f:
                    owner_prefs_data = json.load(f)
                print(f"  Loaded owner_settings.json")
            except Exception as e:
                print(f"  WARNING: Could not load owner_settings.json: {e}")

        if not dry_run:
            existing_prefs = db.query(OwnerPreferences).first()
            if not existing_prefs:
                db.add(OwnerPreferences(
                    default_owner_id=owner_prefs_data.get("default_owner_label"),
                    active_profiles=owner_prefs_data.get("active_profiles", {}),
                ))
                db.commit()

        # ── Walk owner folders ────────────────────────────────────────────────
        owner_dirs = [
            d for d in collections_path.iterdir()
            if d.is_dir() and not d.name.startswith(".")
        ]

        for owner_dir in sorted(owner_dirs):
            folder_name = owner_dir.name
            owner_id = sanitize_owner_id(folder_name)
            label = owner_folder_label(folder_name) or folder_name

            print(f"\nOwner: {folder_name!r} → owner_id={owner_id!r}, label={label!r}")

            if not dry_run:
                db_owner = db.query(Owner).filter(Owner.owner_id == owner_id).first()
                if not db_owner:
                    db_owner = Owner(owner_id=owner_id, label=label)
                    db.add(db_owner)
                    db.flush()
                    stats["owners"] += 1
                    print(f"  Created owner: {owner_id}")
            else:
                db_owner = None
                stats["owners"] += 1

            # Track profiles seen in this owner's folder
            profiles_seen: set = set()

            # ── Walk CSV files in owner folder ────────────────────────────────
            csv_files = sorted(owner_dir.glob("*.csv"))
            for csv_file in csv_files:
                fname = csv_file.name

                # Skip backup files
                if "backup" in fname:
                    continue

                # If --unified-only, skip per-game files (those without "unified")
                if unified_only and "unified" not in fname and "watchlist" not in fname:
                    print(f"  Skipping (--unified-only): {fname}")
                    continue

                is_watchlist = "watchlist" in fname
                profile_id = parse_profile_from_filename(owner_id, fname)
                game_hint = game_from_filename(fname)

                print(f"  File: {fname}  profile={profile_id!r}  game_hint={game_hint!r}")

                # Ensure profile row exists
                if not dry_run and db_owner:
                    if profile_id not in profiles_seen:
                        existing_profile = db.query(Profile).filter(
                            Profile.owner_id == db_owner.id,
                            Profile.profile_id == profile_id,
                        ).first()
                        if not existing_profile:
                            db.add(Profile(owner_id=db_owner.id, profile_id=profile_id))
                            db.flush()
                            stats["profiles"] += 1
                        profiles_seen.add(profile_id)

                # Read CSV rows
                try:
                    with open(csv_file, encoding="utf-8-sig", errors="replace") as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)
                except Exception as e:
                    print(f"    ERROR reading {fname}: {e}")
                    continue

                print(f"    Rows: {len(rows)}")

                for row in rows:
                    if not any(row.values()):
                        continue
                    name = (row.get("name") or "").strip()
                    if not name:
                        continue

                    game = (row.get("game") or game_hint).strip()

                    if is_watchlist:
                        if dry_run:
                            stats["watchlist"] += 1
                            continue
                        item = WatchlistItem(
                            owner_id=db_owner.id,
                            profile_id=profile_id,
                            game=game,
                            name=name,
                            set_name=row.get("set", ""),
                            set_code=row.get("set_code", ""),
                            card_number=row.get("card_number", ""),
                            year=row.get("year", ""),
                            link=row.get("link", ""),
                            image_url=row.get("image_url", ""),
                            price_low=_to_float(row.get("price_low")),
                            price_mid=_to_float(row.get("price_mid")),
                            price_market=_to_float(row.get("price_market")),
                            price_usd=_to_float(row.get("price_usd")),
                            price_usd_foil=_to_float(row.get("price_usd_foil")),
                            price_usd_etched=_to_float(row.get("price_usd_etched")),
                            quantity=_to_int(row.get("quantity"), 1),
                            variant=row.get("variant", ""),
                            target_price=_to_float(row.get("target_price")),
                            signed=row.get("signed", ""),
                            altered=row.get("altered", ""),
                            notes=row.get("notes", ""),
                            timestamp=_parse_timestamp(row.get("timestamp", "")),
                        )
                        db.add(item)
                        stats["watchlist"] += 1
                    else:
                        if dry_run:
                            stats["cards"] += 1
                            continue

                        if upsert:
                            # Check for existing row to skip
                            exists = db.query(CollectionCard).filter(
                                CollectionCard.owner_id == db_owner.id,
                                CollectionCard.profile_id == profile_id,
                                CollectionCard.game == game,
                                CollectionCard.name == name,
                                CollectionCard.set_code == row.get("set_code", ""),
                                CollectionCard.card_number == row.get("card_number", ""),
                                CollectionCard.variant == row.get("variant", ""),
                            ).first()
                            if exists:
                                stats["skipped"] += 1
                                continue

                        card = CollectionCard(
                            owner_id=db_owner.id,
                            profile_id=profile_id,
                            game=game,
                            name=name,
                            set_name=row.get("set", ""),
                            set_code=row.get("set_code", ""),
                            card_number=row.get("card_number", ""),
                            year=row.get("year", ""),
                            link=row.get("link", ""),
                            image_url=row.get("image_url", ""),
                            price_low=_to_float(row.get("price_low")),
                            price_mid=_to_float(row.get("price_mid")),
                            price_market=_to_float(row.get("price_market")),
                            price_usd=_to_float(row.get("price_usd")),
                            price_usd_foil=_to_float(row.get("price_usd_foil")),
                            price_usd_etched=_to_float(row.get("price_usd_etched")),
                            quantity=_to_int(row.get("quantity"), 1),
                            variant=row.get("variant", ""),
                            paid=_to_float(row.get("paid")),
                            signed=row.get("signed", ""),
                            altered=row.get("altered", ""),
                            notes=row.get("notes", ""),
                            timestamp=_parse_timestamp(row.get("timestamp", "")),
                        )
                        db.add(card)
                        stats["cards"] += 1

                if not dry_run:
                    db.commit()  # commit after each file

        if not dry_run:
            db.commit()

    finally:
        db.close()

    return stats


def main():
    parser = argparse.ArgumentParser(description="Migrate CSV collections to SQLite")
    parser.add_argument(
        "--collections-dir",
        default="../collections",
        help="Path to the collections/ directory (default: ../collections)",
    )
    parser.add_argument(
        "--upsert",
        action="store_true",
        help="Skip rows that already exist (idempotent re-run)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Parse and count without writing to the database",
    )
    parser.add_argument(
        "--unified-only",
        action="store_true",
        help="Only import *unified* CSVs; skip per-game files to avoid duplicates",
    )
    args = parser.parse_args()

    print(f"{'DRY RUN — ' if args.dry_run else ''}Migrating from: {args.collections_dir}")
    stats = migrate(
        args.collections_dir,
        upsert=args.upsert,
        dry_run=args.dry_run,
        unified_only=args.unified_only,
    )

    print("\n── Migration summary ──────────────────────")
    for key, val in stats.items():
        print(f"  {key:12s}: {val}")
    print("──────────────────────────────────────────")
    if args.dry_run:
        print("DRY RUN complete — no data written.")
    else:
        print("Migration complete.")


if __name__ == "__main__":
    main()
