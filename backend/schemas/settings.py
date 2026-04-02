"""
Pydantic schemas for app settings and API source configuration.
"""
from typing import Optional, Dict, Any
from pydantic import BaseModel


class ApiSourceConfig(BaseModel):
    source_id: str
    name: str
    game: str
    enabled: bool
    free: bool
    description: str = ""


class AppSettingsRead(BaseModel):
    duplicate_strategy: str = "merge"
    paid_merge_strategy: str = "sum"
    auto_backup_enabled: bool = False
    backup_retention: int = 5
    api_source_config: Dict[str, Any] = {}

    class Config:
        from_attributes = True


class AppSettingsUpdate(BaseModel):
    duplicate_strategy: Optional[str] = None
    paid_merge_strategy: Optional[str] = None
    auto_backup_enabled: Optional[bool] = None
    backup_retention: Optional[int] = None


class ApiSourceUpdate(BaseModel):
    source_id: str
    enabled: bool
    ebay_env: Optional[str] = None   # "Sandbox" | "Production"
    pokemontcg_api: Optional[str] = None  # custom API URL override


class ImportCsvResponse(BaseModel):
    imported: int
    ambiguous: int
    ambiguities: list[Dict[str, Any]] = []


class AmbiguityResolution(BaseModel):
    ambiguity_id: int
    selected_candidate: Dict[str, Any]
    quantity: int = 1
    variant: str = ""
    paid: float = 0.0


class ResolveAmbiguitiesRequest(BaseModel):
    owner_id: str
    profile_id: str = "default"
    resolutions: list[AmbiguityResolution]


class BackupRequest(BaseModel):
    owner_id: str
    profile_id: Optional[str] = None
    retention: int = 5
