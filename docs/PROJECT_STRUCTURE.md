# Collectibles Manager — Project Structure

## Root Directory

```
collectibles_manager/
├── package.json              # Root npm scripts (dev, backend, frontend)
├── package-lock.json         # npm lockfile for concurrently
├── .nvmrc                    # Pins Node version to 20
├── .gitignore
│
├── backend/                  # FastAPI REST API
├── frontend/                 # React + TypeScript (Vite)
│
├── collections/              # Owner collection data (gitignored CSVs)
├── fallback_data/            # Offline card/set cache (gitignored)
│   ├── MTG/
│   │   ├── mtgsets.csv
│   │   ├── SetImages/
│   │   └── CardImages/
│   └── Pokemon/
│       ├── pokemonsets.csv
│       ├── SetImages/
│       └── CardImages/
│
├── collectibles.db           # SQLite database (gitignored, auto-created)
├── constants.py              # Legacy constants (referenced by backend/legacy/)
├── fallback_manager.py       # Legacy fallback manager (referenced by backend/legacy/)
├── image_sources.py          # Legacy image source helpers
│
├── docs/                     # Developer documentation
├── utility/                  # Maintenance and migration scripts
│   └── old/                  # Archived / deprecated scripts
└── logs/                     # Runtime logs (gitignored)
```

---

## Backend (`backend/`)

```
backend/
├── main.py                   # FastAPI app entry point, CORS, router registration
├── config.py                 # pydantic-settings: reads backend/.env for API keys
├── database.py               # SQLAlchemy engine + session factory (SQLite)
│
├── models/                   # SQLAlchemy ORM models
│   ├── card.py               # CollectionCard, WatchlistItem
│   ├── owner.py              # Owner, Profile, OwnerPreferences
│   └── settings.py           # AppSettings, ImportAmbiguity
│
├── schemas/                  # Pydantic request/response schemas
│   ├── card.py
│   ├── owner.py
│   ├── search.py
│   └── settings.py
│
├── routers/                  # FastAPI route handlers
│   ├── search.py             # GET /api/search/{mtg|pokemon|baseball}
│   ├── collection.py         # CRUD /api/collection/cards
│   ├── watchlist.py          # CRUD /api/watchlist
│   ├── sets.py               # GET /api/sets
│   ├── owners.py             # CRUD /api/owners + /api/owners/{id}/profiles
│   ├── settings.py           # GET/PUT /api/settings
│   └── export.py             # POST /api/export/{csv|zip}, /api/backup
│
├── services/                 # Business logic
│   ├── search_service.py     # Fallback chain orchestration
│   ├── collection_service.py # Merge/duplicate/backup logic
│   ├── import_service.py     # CSV import + ambiguity resolution
│   └── stats_service.py      # Investment analysis aggregation
│
├── external/                 # External API clients
│   ├── scryfall.py           # MTG search via Scryfall
│   ├── pokemon_tcg.py        # Pokemon TCG API
│   ├── ebay.py               # eBay sold listings
│   └── sportscard_db.py      # SportsCardDatabase search
│
├── legacy/                   # Ported from original Streamlit app (no st.* calls)
│   ├── constants.py
│   ├── fallback_manager.py   # Offline CSV cache; stays as CSV, not in SQLite
│   └── image_sources.py
│
├── migrations/
│   ├── env.py                # Alembic environment
│   ├── versions/             # Migration scripts
│   └── csv_to_sqlite.py      # One-shot CSV → SQLite migration (idempotent)
│
├── fallback_data/            # Symlink / copy of root fallback_data/
├── requirements.txt          # Python dependencies
├── alembic.ini
└── .env                      # Local secrets (gitignored — copy from .env.example)
```

---

## Frontend (`frontend/`)

```
frontend/
├── package.json
├── vite.config.ts
├── tsconfig.json
└── src/
    ├── App.tsx               # Router setup
    ├── api/                  # Axios API client + per-domain functions
    │   └── client.ts, search.ts, collection.ts, watchlist.ts,
    │       sets.ts, owners.ts, settings.ts, export.ts
    ├── store/
    │   ├── ownerStore.ts     # Zustand: currentOwnerId, currentProfileId (localStorage)
    │   └── settingsStore.ts  # Zustand: viewMode, cardsPerRow, imageWidth (localStorage)
    ├── hooks/                # React Query hooks (useSearch, useCollection, etc.)
    ├── pages/
    │   ├── HomePage.tsx      # Search (MTG / Pokemon / Baseball tabs)
    │   ├── CollectionPage.tsx
    │   ├── SetsPage.tsx
    │   ├── SettingsPage.tsx
    │   └── HelpPage.tsx
    ├── components/
    │   ├── layout/           # Sidebar (owner/profile selector + nav), Layout shell
    │   ├── search/           # Search forms + SearchResultsGrid
    │   ├── collection/       # Collection tabs, AmbiguityResolver
    │   ├── sets/             # SetsTable, SetFilters
    │   ├── settings/         # Settings panels
    │   └── shared/           # CardImage, VariantSelector, stat cards, etc.
    └── types/                # TypeScript interfaces (card.ts, owner.ts, settings.ts)
```

---

## Key Conventions

| Item | Convention |
|---|---|
| Python files | `snake_case.py` |
| React components | `PascalCase.tsx` |
| API hooks | `use<Resource>.ts` |
| Zustand stores | `<name>Store.ts` |
| Documentation | `UPPER_SNAKE_CASE.md` in `docs/` |
| Env secrets | `backend/.env` (never committed) |
| DB file | `collectibles.db` at project root (never committed) |
