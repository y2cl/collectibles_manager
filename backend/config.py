"""
Application configuration via pydantic-settings.
All secrets/keys are read from environment variables or a .env file.
No API keys are ever sent to the frontend.
"""
from pathlib import Path
from typing import List
from pydantic import computed_field
from pydantic_settings import BaseSettings

# Always resolve .env relative to this file (backend/.env),
# regardless of which directory uvicorn is launched from.
_ENV_FILE = Path(__file__).parent / ".env"


class Settings(BaseSettings):
    # External API keys
    pokemontcg_api_key: str = ""
    ebay_app_id: str = ""
    ebay_app_id_sbx: str = ""
    justtcg_api_key: str = ""
    upcitemdb_api_key: str = ""   # optional — trial endpoint works without a key (100 req/day)
    serpapi_key: str = ""         # SerpAPI key for Google Images search (250 searches/month free)
    comic_vine_api_key: str = ""  # Comic Vine API key — register at comicvine.gamespot.com/api/

    # Database (relative to project root when run as `uvicorn backend.main:app`)
    database_url: str = "sqlite:///./collectibles.db"

    # Server
    # Stored as a raw comma-separated string so pydantic-settings doesn't try
    # to JSON-parse it; exposed as a list via the computed field below.
    cors_origins_raw: str = "http://localhost:5173,http://localhost:3000"
    host: str = "0.0.0.0"
    port: int = 8000

    # Paths (relative to project root)
    fallback_data_dir: str = "backend/fallback_data"
    collections_dir: str = "collections"

    @computed_field  # type: ignore[misc]
    @property
    def cors_origins(self) -> List[str]:
        return [o.strip() for o in self.cors_origins_raw.split(",") if o.strip()]

    model_config = {
        "env_file": str(_ENV_FILE),
        "env_file_encoding": "utf-8",
        "extra": "ignore",
    }


settings = Settings()
