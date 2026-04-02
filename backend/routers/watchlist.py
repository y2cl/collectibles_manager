"""
Watchlist endpoints: CRUD for watchlist items.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.card import WatchlistItem
from ..models.owner import Owner
from ..schemas.card import WatchlistItemCreate, WatchlistItemRead, WatchlistItemUpdate

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


def _require_owner(db: Session, owner_id_slug: str) -> Owner:
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail=f"Owner '{owner_id_slug}' not found")
    return owner


@router.get("", response_model=List[WatchlistItemRead])
def get_watchlist(
    owner_id: str = Query(...),
    profile_id: str = Query("default"),
    db: Session = Depends(get_db),
):
    owner = _require_owner(db, owner_id)
    return (
        db.query(WatchlistItem)
        .filter(
            WatchlistItem.owner_id == owner.id,
            WatchlistItem.profile_id == profile_id,
        )
        .order_by(WatchlistItem.timestamp.desc())
        .all()
    )


@router.post("", response_model=WatchlistItemRead, status_code=201)
def add_watchlist_item(payload: WatchlistItemCreate, db: Session = Depends(get_db)):
    owner = _require_owner(db, payload.owner_id)
    item = WatchlistItem(
        owner_id=owner.id,
        profile_id=payload.profile_id,
        **{k: v for k, v in payload.model_dump().items() if k not in ("owner_id", "profile_id")},
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


@router.patch("/{item_id}", response_model=WatchlistItemRead)
def update_watchlist_item(item_id: int, payload: WatchlistItemUpdate, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(item, field, value)
    db.commit()
    db.refresh(item)
    return item


@router.delete("/{item_id}", status_code=200)
def delete_watchlist_item(item_id: int, db: Session = Depends(get_db)):
    item = db.query(WatchlistItem).filter(WatchlistItem.id == item_id).first()
    if not item:
        raise HTTPException(status_code=404, detail="Watchlist item not found")
    db.delete(item)
    db.commit()
    return {"deleted": True}
