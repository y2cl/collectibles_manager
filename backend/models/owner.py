"""
Owner, Profile, and OwnerPreferences ORM models.
"""
from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, UniqueConstraint, JSON, ForeignKey
from sqlalchemy.orm import relationship
from ..database import Base


class Owner(Base):
    __tablename__ = "owners"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(String, unique=True, nullable=False)  # sanitized slug, e.g. "john"
    label = Column(String, nullable=False)                  # display name, e.g. "John's Collection"
    created_at = Column(DateTime, default=datetime.utcnow)

    profiles = relationship("Profile", back_populates="owner", cascade="all, delete-orphan")
    cards = relationship("CollectionCard", back_populates="owner", cascade="all, delete-orphan")
    watchlist = relationship("WatchlistItem", back_populates="owner", cascade="all, delete-orphan")
    ambiguities = relationship("ImportAmbiguity", back_populates="owner", cascade="all, delete-orphan")
    import_history = relationship("ImportHistory", back_populates="owner", cascade="all, delete-orphan")


class Profile(Base):
    __tablename__ = "profiles"

    id = Column(Integer, primary_key=True, autoincrement=True)
    owner_id = Column(Integer, ForeignKey("owners.id"), nullable=False)  # FK to owners.id
    profile_id = Column(String, nullable=False)  # e.g. "default", "vintage"
    created_at = Column(DateTime, default=datetime.utcnow)

    owner = relationship("Owner", back_populates="profiles")

    __table_args__ = (
        UniqueConstraint("owner_id", "profile_id", name="uq_owner_profile"),
    )


class OwnerPreferences(Base):
    __tablename__ = "owner_preferences"

    id = Column(Integer, primary_key=True, autoincrement=True)
    default_owner_id = Column(String, nullable=True)   # owner.owner_id slug of default owner
    active_profiles = Column(JSON, default=dict)        # { owner_id_slug: profile_id }
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
