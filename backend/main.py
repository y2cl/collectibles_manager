"""
Collectibles Manager — FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .database import create_all_tables

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Starting up — creating database tables if needed")
    create_all_tables()
    yield
    logger.info("Shutting down")


app = FastAPI(
    title="Collectibles Manager API",
    description="FastAPI backend for the Collectibles Manager (MTG, Pokémon, Baseball)",
    version="2.4.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ───────────────────────────────────────────────────────────────────
from .routers.search import router as search_router
from .routers.collection import router as collection_router
from .routers.watchlist import router as watchlist_router
from .routers.owners import router as owners_router
from .routers.settings import router as settings_router
from .routers.sets import router as sets_router
from .routers.export import router as export_router
from .routers.lookup import router as lookup_router
from .routers.changelog import router as changelog_router
from .routers.dev import router as dev_router

app.include_router(search_router)
app.include_router(collection_router)
app.include_router(watchlist_router)
app.include_router(owners_router)
app.include_router(settings_router)
app.include_router(sets_router)
app.include_router(export_router)
app.include_router(lookup_router)
app.include_router(changelog_router)
app.include_router(dev_router)


@app.get("/api/health")
def health():
    return {"status": "ok", "version": "2.4.0"}


@app.get("/health")
def health_root():
    """Root health endpoint for external integrations (e.g., MTG Cube Maker)"""
    return {"status": "ok", "version": "2.4.0"}
