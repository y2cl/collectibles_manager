"""
Collection endpoints: CRUD for collection cards.
"""
from typing import Optional, List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.card import CollectionCard
from ..models.owner import Owner
from ..models.settings import AppSettings
from ..schemas.card import (
    CollectionCardCreate, CollectionCardRead, CollectionCardUpdate,
    BulkDeleteRequest, CollectionResponse, CollectionStats,
)
from ..services.collection_service import add_card

router = APIRouter(prefix="/api/collection", tags=["collection"])


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


@router.get("", response_model=CollectionResponse)
def get_collection(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    game: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    owner = _require_owner(db, owner_id)
    q = db.query(CollectionCard).filter(
        CollectionCard.owner_id == owner.id,
        CollectionCard.profile_id == profile_id,
    )
    if game:
        q = q.filter(CollectionCard.game == game)
    cards = q.order_by(CollectionCard.timestamp.desc()).all()

    total_cards = sum(c.quantity or 1 for c in cards)
    unique_cards = len(cards)
    unique_sets = len({f"{c.year} {c.set_name}" for c in cards})
    total_value = sum((c.price_usd or 0) * (c.quantity or 1) for c in cards)

    return CollectionResponse(
        cards=cards,
        stats=CollectionStats(
            total_cards=total_cards,
            unique_cards=unique_cards,
            unique_sets=unique_sets,
            total_value=round(total_value, 2),
        ),
    )


@router.post("/cards", response_model=CollectionCardRead, status_code=201)
def add_card_endpoint(payload: CollectionCardCreate, db: Session = Depends(get_db)):
    settings = _get_settings(db)
    cfg = settings.api_source_config or {}
    duplicate_strategy = settings.duplicate_strategy or "merge"
    paid_merge_strategy = settings.paid_merge_strategy or "sum"

    card_data = payload.model_dump()
    result = add_card(
        db,
        owner_id_slug=payload.owner_id,
        profile_id=payload.profile_id,
        card_data=card_data,
        duplicate_strategy=duplicate_strategy,
        paid_merge_strategy=paid_merge_strategy,
    )
    return result


@router.patch("/cards/{card_id}", response_model=CollectionCardRead)
def update_card(card_id: int, payload: CollectionCardUpdate, db: Session = Depends(get_db)):
    card = db.query(CollectionCard).filter(CollectionCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")

    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(card, field, value)

    db.commit()
    db.refresh(card)
    return card


@router.delete("/cards/{card_id}", status_code=200)
def delete_card(card_id: int, db: Session = Depends(get_db)):
    card = db.query(CollectionCard).filter(CollectionCard.id == card_id).first()
    if not card:
        raise HTTPException(status_code=404, detail="Card not found")
    db.delete(card)
    db.commit()
    return {"deleted": True}


@router.delete("/cards", status_code=200)
def bulk_delete_cards(payload: BulkDeleteRequest, db: Session = Depends(get_db)):
    owner = _require_owner(db, payload.owner_id)
    deleted = (
        db.query(CollectionCard)
        .filter(
            CollectionCard.owner_id == owner.id,
            CollectionCard.profile_id == payload.profile_id,
            CollectionCard.id.in_(payload.card_ids),
        )
        .all()
    )
    count = len(deleted)
    for card in deleted:
        db.delete(card)
    db.commit()
    return {"deleted_count": count}
