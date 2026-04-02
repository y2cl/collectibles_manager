"""
Owner and profile management endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.owner import Owner, Profile, OwnerPreferences
from ..models.card import CollectionCard
from ..schemas.owner import (
    OwnerCreate, OwnerRead, OwnerUpdate,
    ProfileCreate, ProfileRead, ProfileUpdate,
    OwnerPreferencesRead, OwnerPreferencesUpdate,
)
from ..services.collection_service import sanitize_owner_id, owner_folder_label, sanitize_profile_id

router = APIRouter(prefix="/api/owners", tags=["owners"])


def _get_or_create_preferences(db: Session) -> OwnerPreferences:
    prefs = db.query(OwnerPreferences).first()
    if not prefs:
        prefs = OwnerPreferences(default_owner_id=None, active_profiles={})
        db.add(prefs)
        db.commit()
        db.refresh(prefs)
    return prefs


@router.get("", response_model=List[OwnerRead])
def list_owners(db: Session = Depends(get_db)):
    return db.query(Owner).order_by(Owner.label).all()


@router.post("", response_model=OwnerRead, status_code=201)
def create_owner(payload: OwnerCreate, db: Session = Depends(get_db)):
    owner_id = sanitize_owner_id(payload.name)
    if not owner_id:
        raise HTTPException(status_code=400, detail="Invalid owner name")

    existing = db.query(Owner).filter(Owner.owner_id == owner_id).first()
    if existing:
        raise HTTPException(status_code=409, detail=f"Owner '{owner_id}' already exists")

    label = owner_folder_label(payload.name)
    owner = Owner(owner_id=owner_id, label=label)
    db.add(owner)
    db.flush()  # get owner.id before adding default profile

    # Every owner starts with a 'default' profile
    default_profile = Profile(owner_id=owner.id, profile_id="default")
    db.add(default_profile)
    db.commit()
    db.refresh(owner)
    return owner


@router.get("/{owner_id_slug}/profiles", response_model=List[ProfileRead])
def list_profiles(owner_id_slug: str, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return db.query(Profile).filter(Profile.owner_id == owner.id).all()


@router.post("/{owner_id_slug}/profiles", response_model=ProfileRead, status_code=201)
def create_profile(owner_id_slug: str, payload: ProfileCreate, db: Session = Depends(get_db)):
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")

    profile_id = sanitize_profile_id(payload.name)
    existing = (
        db.query(Profile)
        .filter(Profile.owner_id == owner.id, Profile.profile_id == profile_id)
        .first()
    )
    if existing:
        raise HTTPException(status_code=409, detail=f"Profile '{profile_id}' already exists for this owner")

    profile = Profile(owner_id=owner.id, profile_id=profile_id)
    db.add(profile)
    db.commit()
    db.refresh(profile)
    return profile


def _require_owner(db: Session, owner_id_slug: str) -> Owner:
    owner = db.query(Owner).filter(Owner.owner_id == owner_id_slug).first()
    if not owner:
        raise HTTPException(status_code=404, detail="Owner not found")
    return owner


@router.get("/preferences", response_model=OwnerPreferencesRead)
def get_preferences(db: Session = Depends(get_db)):
    return _get_or_create_preferences(db)


@router.put("/preferences", response_model=OwnerPreferencesRead)
def update_preferences(payload: OwnerPreferencesUpdate, db: Session = Depends(get_db)):
    prefs = _get_or_create_preferences(db)
    if payload.default_owner_id is not None:
        prefs.default_owner_id = payload.default_owner_id
    if payload.active_profiles is not None:
        prefs.active_profiles = payload.active_profiles
    db.commit()
    db.refresh(prefs)
    return prefs


@router.put("/{owner_id_slug}", response_model=OwnerRead)
def update_owner(owner_id_slug: str, payload: OwnerUpdate, db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    owner.label = payload.label
    db.commit()
    db.refresh(owner)
    return owner


@router.delete("/{owner_id_slug}", status_code=200)
def delete_owner(owner_id_slug: str, db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    db.delete(owner)
    db.commit()
    return {"deleted": True}


@router.put("/{owner_id_slug}/profiles/{profile_id}", response_model=ProfileRead)
def update_profile(owner_id_slug: str, profile_id: str, payload: ProfileUpdate, db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    profile = db.query(Profile).filter_by(owner_id=owner.id, profile_id=profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.query(CollectionCard).filter_by(owner_id=owner.id, profile_id=profile_id).update({"profile_id": payload.profile_id})
    profile.profile_id = payload.profile_id
    db.commit()
    db.refresh(profile)
    return profile


@router.delete("/{owner_id_slug}/profiles/{profile_id}", status_code=200)
def delete_profile(owner_id_slug: str, profile_id: str, db: Session = Depends(get_db)):
    owner = _require_owner(db, owner_id_slug)
    profile = db.query(Profile).filter_by(owner_id=owner.id, profile_id=profile_id).first()
    if not profile:
        raise HTTPException(status_code=404, detail="Profile not found")
    db.delete(profile)
    db.commit()
    return {"deleted": True}
