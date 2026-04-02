"""
Pydantic schemas for owners, profiles, and preferences.
"""
from datetime import datetime
from typing import Optional, Dict
from pydantic import BaseModel


class ProfileRead(BaseModel):
    id: int
    owner_id: int
    profile_id: str
    created_at: datetime

    class Config:
        from_attributes = True


class OwnerCreate(BaseModel):
    name: str


class OwnerRead(BaseModel):
    id: int
    owner_id: str
    label: str
    created_at: datetime
    profiles: list[ProfileRead] = []

    class Config:
        from_attributes = True


class ProfileCreate(BaseModel):
    name: str


class OwnerUpdate(BaseModel):
    label: str


class ProfileUpdate(BaseModel):
    profile_id: str


class OwnerPreferencesRead(BaseModel):
    default_owner_id: Optional[str] = None
    active_profiles: Dict[str, str] = {}  # { owner_id_slug: profile_id }

    class Config:
        from_attributes = True


class OwnerPreferencesUpdate(BaseModel):
    default_owner_id: Optional[str] = None
    active_profiles: Optional[Dict[str, str]] = None
