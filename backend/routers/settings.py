"""
App settings endpoints.
"""
from typing import List
from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from ..database import get_db
from ..models.settings import AppSettings
from ..schemas.settings import AppSettingsRead, AppSettingsUpdate, ApiSourceUpdate, ApiSourceConfig
from ..legacy.constants import API_SOURCES

router = APIRouter(prefix="/api/settings", tags=["settings"])

_DEFAULT_API_CONFIG = {
    "scryfall_enabled": True,
    "pokemontcg_enabled": False,
    "pokemonpublic_enabled": True,
    "fallback_enabled": True,
    "ebay_enabled": True,
    "sportscarddatabase_enabled": True,
    "last_ebay_env": "Sandbox",
    "pokemontcg_api": "https://api.pokemontcg.io/v2/cards",
}


def _get_or_create_settings(db: Session) -> AppSettings:
    row = db.query(AppSettings).first()
    if not row:
        row = AppSettings(api_source_config=_DEFAULT_API_CONFIG)
        db.add(row)
        db.commit()
        db.refresh(row)
    return row


@router.get("", response_model=AppSettingsRead)
def get_settings(db: Session = Depends(get_db)):
    return _get_or_create_settings(db)


@router.put("", response_model=AppSettingsRead)
def update_settings(payload: AppSettingsUpdate, db: Session = Depends(get_db)):
    row = _get_or_create_settings(db)
    for field, value in payload.model_dump(exclude_none=True).items():
        setattr(row, field, value)
    db.commit()
    db.refresh(row)
    return row


@router.get("/api-sources", response_model=List[ApiSourceConfig])
def get_api_sources(db: Session = Depends(get_db)):
    row = _get_or_create_settings(db)
    cfg = row.api_source_config or _DEFAULT_API_CONFIG
    sources = []
    for source_id, meta in API_SOURCES.items():
        enabled_key = meta.get("enabled_key", f"{source_id}_enabled")
        sources.append(ApiSourceConfig(
            source_id=source_id,
            name=meta.get("name", source_id),
            game=meta.get("game", ""),
            enabled=bool(cfg.get(enabled_key, False)),
            free=bool(meta.get("free", True)),
            description=meta.get("description", ""),
        ))
    return sources


@router.put("/api-sources", response_model=List[ApiSourceConfig])
def update_api_sources(updates: List[ApiSourceUpdate], db: Session = Depends(get_db)):
    row = _get_or_create_settings(db)
    cfg = dict(row.api_source_config or _DEFAULT_API_CONFIG)
    for update in updates:
        meta = API_SOURCES.get(update.source_id, {})
        enabled_key = meta.get("enabled_key", f"{update.source_id}_enabled")
        cfg[enabled_key] = update.enabled
        if update.ebay_env:
            cfg["last_ebay_env"] = update.ebay_env
        if update.pokemontcg_api:
            cfg["pokemontcg_api"] = update.pokemontcg_api
    row.api_source_config = cfg
    db.commit()
    db.refresh(row)
    # Return refreshed source list
    sources = []
    for source_id, meta in API_SOURCES.items():
        enabled_key = meta.get("enabled_key", f"{source_id}_enabled")
        sources.append(ApiSourceConfig(
            source_id=source_id,
            name=meta.get("name", source_id),
            game=meta.get("game", ""),
            enabled=bool(cfg.get(enabled_key, False)),
            free=bool(meta.get("free", True)),
            description=meta.get("description", ""),
        ))
    return sources
