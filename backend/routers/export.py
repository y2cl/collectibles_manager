"""
Import / Export / Backup endpoints.
"""
import csv
import io
import os
import zipfile
import logging
from typing import List, Optional

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.card import CollectionCard, WatchlistItem
from ..models.owner import Owner
from ..models.settings import AppSettings, ImportAmbiguity, ImportHistory
from ..schemas.settings import (
    ImportCsvResponse, ResolveAmbiguitiesRequest, BackupRequest
)
from ..services.import_service import import_csv, import_csv_stream, resolve_ambiguities, COLLECTION_COLUMNS
from ..services.stats_service import get_collection_stats

router = APIRouter(prefix="/api", tags=["import-export"])
logger = logging.getLogger(__name__)


def _get_settings(db: Session) -> AppSettings:
    row = db.query(AppSettings).first()
    if not row:
        row = AppSettings()
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


def _require_owner(db: Session, owner_id_slug: str) -> Owner:
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail=f"Owner '{owner_id_slug}' not found")
    return owner


# ── Import ────────────────────────────────────────────────────────────────────

@router.post("/import/csv", response_model=ImportCsvResponse)
async def import_csv_endpoint(
    file: UploadFile = File(...),
    owner_id: str = Form(...),
    profile_id: str = Form("default"),
    column_mapping: Optional[str] = Form(None),
    game: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    import json
    settings = _get_settings(db)
    content = await file.read()
    mapping = None
    if column_mapping:
        try:
            mapping = json.loads(column_mapping)
        except Exception:
            logger.warning("Invalid column_mapping JSON, ignoring: %s", column_mapping)
    imported, ambiguous, ambiguities = import_csv(
        file_content=content,
        owner_id_slug=owner_id,
        profile_id=profile_id,
        db=db,
        duplicate_strategy=settings.duplicate_strategy or "merge",
        paid_merge_strategy=settings.paid_merge_strategy or "sum",
        column_mapping=mapping,
        game_override=game or None,
        filename=file.filename or "import.csv",
    )
    return ImportCsvResponse(imported=imported, ambiguous=ambiguous, ambiguities=ambiguities)


@router.post("/import/csv/stream")
async def import_csv_stream_endpoint(
    file: UploadFile = File(...),
    owner_id: str = Form(...),
    profile_id: str = Form("default"),
    column_mapping: Optional[str] = Form(None),
    game: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    """
    Stream import progress as Server-Sent Events.
    Each SSE event is a JSON object:
      {"type": "start",    "total": N}
      {"type": "progress", "current": i, "total": N, "name": "...", "status": "..."}
      {"type": "done",     "imported": N, "ambiguous": M, "ambiguities": [...]}
      {"type": "error",    "message": "..."}
    """
    import json as _json

    settings = _get_settings(db)
    content = await file.read()
    mapping = None
    if column_mapping:
        try:
            mapping = _json.loads(column_mapping)
        except Exception:
            logger.warning("Invalid column_mapping JSON, ignoring: %s", column_mapping)

    def _generate():
        for event in import_csv_stream(
            file_content=content,
            owner_id_slug=owner_id,
            profile_id=profile_id,
            db=db,
            duplicate_strategy=settings.duplicate_strategy or "merge",
            paid_merge_strategy=settings.paid_merge_strategy or "sum",
            column_mapping=mapping,
            game_override=game or None,
            filename=file.filename or "import.csv",
        ):
            yield f"data: {_json.dumps(event)}\n\n"

    return StreamingResponse(
        _generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",   # disable nginx buffering
        },
    )


@router.get("/import/ambiguities/{owner_id_slug}")
def get_ambiguities(owner_id_slug: str, profile_id: str = Query("default"), db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    rows = (
        db.query(ImportAmbiguity)
        .filter(
            ImportAmbiguity.owner_id == owner.id,
            ImportAmbiguity.profile_id == profile_id,
        )
        .all()
    )
    return [{"id": r.id, "row_data": r.row_data, "candidates": r.candidates} for r in rows]


@router.delete("/import/ambiguities/{owner_id_slug}", status_code=200)
def clear_ambiguities(owner_id_slug: str, profile_id: str = Query("default"), db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    deleted = (
        db.query(ImportAmbiguity)
        .filter(
            ImportAmbiguity.owner_id == owner.id,
            ImportAmbiguity.profile_id == profile_id,
        )
        .all()
    )
    count = len(deleted)
    for row in deleted:
        db.delete(row)
    db.commit()
    return {"cleared": count}


@router.post("/import/resolve-ambiguities")
def resolve_ambiguities_endpoint(payload: ResolveAmbiguitiesRequest, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    resolutions = [r.model_dump() for r in payload.resolutions]
    committed = resolve_ambiguities(
        owner_id_slug=payload.owner_id,
        profile_id=payload.profile_id,
        resolutions=resolutions,
        db=db,
        duplicate_strategy=settings.duplicate_strategy or "merge",
        paid_merge_strategy=settings.paid_merge_strategy or "sum",
    )
    return {"committed": committed}


# ── Import History ────────────────────────────────────────────────────────────

@router.get("/import/history/{owner_id_slug}")
def get_import_history(
    owner_id_slug: str,
    profile_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    """Return import history records (without file bytes) for a given owner/profile."""
    owner = _require_owner(db, owner_id_slug)
    rows = (
        db.query(ImportHistory)
        .filter(
            ImportHistory.owner_id == owner.id,
            ImportHistory.profile_id == profile_id,
        )
        .order_by(ImportHistory.timestamp.desc())
        .all()
    )
    return [
        {
            "id":              r.id,
            "filename":        r.filename,
            "game":            r.game,
            "imported_count":  r.imported_count,
            "ambiguous_count": r.ambiguous_count,
            "card_count":      len(r.created_card_ids or []),
            "timestamp":       r.timestamp.isoformat() if r.timestamp else None,
        }
        for r in rows
    ]


@router.get("/import/history/{owner_id_slug}/{history_id}/file")
def download_import_file(
    owner_id_slug: str,
    history_id: int,
    db: Session = Depends(get_db),
):
    """Stream the original CSV bytes back to the browser."""
    owner = _require_owner(db, owner_id_slug)
    record = db.query(ImportHistory).filter(
        ImportHistory.id == history_id,
        ImportHistory.owner_id == owner.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")
    if not record.file_data:
        raise HTTPException(status_code=404, detail="File data not stored for this import")
    filename = record.filename or "import.csv"
    return StreamingResponse(
        io.BytesIO(record.file_data),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.delete("/import/history/{owner_id_slug}/{history_id}", status_code=200)
def delete_import(
    owner_id_slug: str,
    history_id: int,
    db: Session = Depends(get_db),
):
    """
    Undo an import: delete all CollectionCards created by this batch,
    then remove the ImportHistory record and any linked ambiguities.
    """
    from ..models.card import CollectionCard

    owner = _require_owner(db, owner_id_slug)
    record = db.query(ImportHistory).filter(
        ImportHistory.id == history_id,
        ImportHistory.owner_id == owner.id,
    ).first()
    if not record:
        raise HTTPException(status_code=404, detail="Import record not found")

    card_ids = list(record.created_card_ids or [])
    deleted_cards = 0
    if card_ids:
        deleted_cards = (
            db.query(CollectionCard)
            .filter(
                CollectionCard.id.in_(card_ids),
                CollectionCard.owner_id == owner.id,
            )
            .delete(synchronize_session=False)
        )

    # Remove any still-pending ambiguities for this batch
    db.query(ImportAmbiguity).filter(
        ImportAmbiguity.import_history_id == history_id
    ).delete(synchronize_session=False)

    db.delete(record)
    db.commit()
    return {"deleted_cards": deleted_cards, "history_id": history_id}


# ── Export ────────────────────────────────────────────────────────────────────

MANABOX_COLUMNS = [
    "Card name", "Set code", "Set name", "Collector number",
    "Foil", "Quantity", "Language", "Condition",
    "Purchase price", "Purchase currency", "Misprint", "Altered", "Scryfall ID",
]


def _cards_to_manabox_csv_bytes(cards: List[CollectionCard]) -> bytes:
    """Export MTG cards in Manabox-compatible import CSV format."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=MANABOX_COLUMNS)
    writer.writeheader()
    for c in cards:
        variant = (c.variant or "").lower()
        foil = "foil" if variant in ("foil", "etched") else "normal"
        altered_val = (c.altered or "").strip().lower()
        altered = "altered" if altered_val in ("yes", "y", "true", "1", "altered") else ""
        writer.writerow({
            "Card name":        c.name,
            "Set code":         c.set_code or "",
            "Set name":         c.set_name or "",
            "Collector number": c.card_number or "",
            "Foil":             foil,
            "Quantity":         c.quantity or 1,
            "Language":         "en",
            "Condition":        "",
            "Purchase price":   c.paid or "",
            "Purchase currency": "USD" if c.paid else "",
            "Misprint":         "",
            "Altered":          altered,
            "Scryfall ID":      "",
        })
    return buf.getvalue().encode("utf-8")


def _cards_to_csv_bytes(cards: List[CollectionCard]) -> bytes:
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=COLLECTION_COLUMNS, extrasaction="ignore")
    writer.writeheader()
    for c in cards:
        writer.writerow({
            "game": c.game,
            "name": c.name,
            "set": c.set_name,
            "set_code": c.set_code,
            "card_number": c.card_number,
            "year": c.year,
            "link": c.link,
            "image_url": c.image_url,
            "price_low": c.price_low or "",
            "price_mid": c.price_mid or "",
            "price_market": c.price_market or "",
            "price_usd": c.price_usd or 0.0,
            "price_usd_foil": c.price_usd_foil or 0.0,
            "price_usd_etched": c.price_usd_etched or 0.0,
            "quantity": c.quantity or 1,
            "variant": c.variant or "",
            "total_value": round((c.price_usd or 0.0) * (c.quantity or 1), 2),
            "paid": c.paid or 0.0,
            "signed": c.signed or "",
            "altered": c.altered or "",
            "notes": c.notes or "",
            "timestamp": c.timestamp.isoformat() if c.timestamp else "",
        })
    return buf.getvalue().encode("utf-8")


@router.post("/export/csv")
def export_csv(
    owner_id: str = Form(...),
    profile_id: str = Form("default"),
    game: Optional[str] = Form(None),
    db: Session = Depends(get_db),
):
    owner = _require_owner(db, owner_id)
    q = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
    )
    if game:
        q = q.filter(CollectionCard.game == game)
    cards = q.all()

    csv_bytes = _cards_to_csv_bytes(cards)
    filename = f"{owner_id}-{profile_id}-collection.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/manabox")
def export_manabox(
    owner_id: str = Form(...),
    profile_id: str = Form("default"),
    db: Session = Depends(get_db),
):
    """Export MTG collection in Manabox-compatible CSV import format."""
    owner = _require_owner(db, owner_id)
    cards = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
        CollectionCard.game == "Magic: The Gathering",
    ).all()

    csv_bytes = _cards_to_manabox_csv_bytes(cards)
    filename = f"{owner_id}-{profile_id}-manabox.csv"
    return StreamingResponse(
        io.BytesIO(csv_bytes),
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


@router.post("/export/zip")
def export_zip(owner_id: str = Form(...), db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id)

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        # Export all profiles
        profiles_rows = db.query(CollectionCard.profile_id).filter(
            CollectionCard.owner_id == owner.id
        ).distinct().all()
        profiles = {r[0] for r in profiles_rows} or {"default"}

        for profile_id in profiles:
            for game_label, game_slug in [
                ("Magic: The Gathering", "mtg"),
                ("Pokémon", "pokemon"),
                ("Sports Cards", "sports"),
            ]:
                cards = db.query(CollectionCard).filter(
                    CollectionCard.owner_id == owner.id,
                    CollectionCard.profile_id == profile_id,
                    CollectionCard.game == game_label,
                ).all()
                if cards:
                    csv_bytes = _cards_to_csv_bytes(cards)
                    fname = (
                        f"{owner.owner_id}-{profile_id}-{game_slug}_collection.csv"
                        if profile_id != "default"
                        else f"{owner.owner_id}-{game_slug}_collection.csv"
                    )
                    zf.writestr(fname, csv_bytes.decode("utf-8"))

        # Watchlist
        wl = db.query(WatchlistItem).filter(WatchlistItem.owner_id == owner.id).all()
        if wl:
            wl_buf = io.StringIO()
            wl_cols = COLLECTION_COLUMNS + ["target_price"]
            writer = csv.DictWriter(wl_buf, fieldnames=wl_cols, extrasaction="ignore")
            writer.writeheader()
            for w in wl:
                writer.writerow({
                    "game": w.game, "name": w.name, "set": w.set_name,
                    "set_code": w.set_code, "card_number": w.card_number, "year": w.year,
                    "link": w.link, "image_url": w.image_url,
                    "price_usd": w.price_usd, "price_usd_foil": w.price_usd_foil,
                    "price_usd_etched": w.price_usd_etched,
                    "price_low": w.price_low or "", "price_mid": w.price_mid or "",
                    "price_market": w.price_market or "",
                    "quantity": w.quantity, "variant": w.variant,
                    "paid": 0.0, "signed": w.signed, "altered": w.altered,
                    "notes": w.notes, "total_value": 0.0,
                    "timestamp": w.timestamp.isoformat() if w.timestamp else "",
                    "target_price": w.target_price or 0.0,
                })
            zf.writestr(f"{owner.owner_id}-watchlist.csv", wl_buf.getvalue())

    buf.seek(0)
    filename = f"{owner_id}-collection-export.zip"
    return StreamingResponse(
        buf,
        media_type="application/zip",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Backup ────────────────────────────────────────────────────────────────────

@router.post("/backup")
def trigger_backup(payload: BackupRequest, db: Session = Depends(get_db)):
    from ..config import settings as app_settings
    from ..services.collection_service import backup_database

    db_url = app_settings.database_url
    db_path = db_url.replace("sqlite:///", "").replace("sqlite://", "")
    if not os.path.exists(db_path):
        raise HTTPException(status_code=404, detail="Database file not found")

    backup_path = backup_database(db_path, retention=payload.retention)
    if not backup_path:
        raise HTTPException(status_code=500, detail="Backup failed")
    return {"backup_path": backup_path, "created": True}


# ── Stats ─────────────────────────────────────────────────────────────────────

@router.get("/stats")
def get_stats(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    game: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    owner = _require_owner(db, owner_id)
    return get_collection_stats(db, owner.id, profile_id, game)


# ── Debug ─────────────────────────────────────────────────────────────────────

@router.get("/debug/fallback-stats")
def fallback_stats():
    try:
        from ..legacy.fallback_manager import get_fallback_stats
        return get_fallback_stats()
    except Exception as e:
        return {"error": str(e)}
