# Collectibles Manager

A personal trading card collection manager supporting **Magic: The Gathering**, **Pokémon TCG**, and **Baseball cards**. Built with a FastAPI backend and a React + TypeScript frontend.

Search live card prices, manage your collection across multiple owners and profiles, track a watchlist, import/export CSV files, and browse set catalogs — all in one app.

---

## Prerequisites

| Tool | Minimum version | Notes |
|---|---|---|
| Python | 3.9+ | 3.11+ recommended |
| Node.js | 20+ | Managed via nvm |
| nvm | any | [install guide](https://github.com/nvm-sh/nvm#installing-and-updating) |

---

## First-Time Setup

### 1. Clone and enter the project

```bash
git clone <repo-url> collectibles_manager
cd collectibles_manager
```

### 2. Set the correct Node version

```bash
nvm install   # reads .nvmrc — installs Node 20 if needed
nvm use       # activates Node 20 for this session
```

### 3. Create the Python virtual environment and install backend dependencies

```bash
python3 -m venv .venv-backend
.venv-backend/bin/pip install -r backend/requirements.txt
```

**Backend Python packages installed:**

| Package | Purpose |
|---|---|
| `fastapi` | REST API framework |
| `uvicorn[standard]` | ASGI server with hot-reload |
| `sqlalchemy` | ORM / database layer |
| `alembic` | Database migrations |
| `pydantic` / `pydantic-settings` | Data validation and `.env` config |
| `requests` | HTTP client for external APIs |
| `beautifulsoup4` | HTML parsing (SportsCardDatabase) |
| `python-multipart` | CSV file upload support |

### 4. Install root npm dependencies (concurrently)

```bash
npm install
```

### 5. Install frontend dependencies

```bash
cd frontend && npm install && cd ..
```

**Key frontend packages:**

| Package | Purpose |
|---|---|
| `vite` | Dev server and bundler |
| `react` / `react-dom` | UI framework |
| `react-router-dom` | Client-side routing |
| `@tanstack/react-query` | Server state / data fetching |
| `@tanstack/react-table` | Collection data grid |
| `zustand` | Client-side state (owner/profile selection) |
| `axios` | HTTP client |
| `recharts` | Investment charts |

### 6. Configure API keys (optional)

Copy the example env file and fill in any keys you have:

```bash
cp backend/.env.example backend/.env
```

Edit `backend/.env`:

```ini
# Pokemon TCG API — free key from https://pokemontcg.io
POKEMONTCG_API_KEY=

# eBay API — https://developer.ebay.com
EBAY_APP_ID=
EBAY_APP_ID_SBX=        # sandbox key for testing

# JustTCG API
JUSTTCG_API_KEY=
```

> All keys are optional. Scryfall (MTG) and the public Pokémon endpoint work without a key. Per-source toggles are available in the app's Settings page.

---

## Running the App

### Both backend + frontend (recommended)

```bash
nvm use && npm run dev
```

This starts both servers in a single terminal with color-coded output:

```
[backend]  INFO:     Uvicorn running on http://127.0.0.1:8000
[frontend] VITE v4.x  ready in 300ms → http://localhost:5173
```

Press **Ctrl+C** to stop both.

### Individual servers (if needed)

```bash
npm run backend    # FastAPI on http://localhost:8000
npm run frontend   # Vite on  http://localhost:5173
```

Open **http://localhost:5173** in your browser.

---

## Database

The app uses a local SQLite file (`collectibles.db`) created automatically at first run. It is gitignored and stays local.

To apply any pending schema migrations:

```bash
cd backend && ../.venv-backend/bin/alembic upgrade head && cd ..
```

To migrate existing CSV collection data into the database:

```bash
.venv-backend/bin/python -m backend.migrations.csv_to_sqlite
```

---

## Project Structure

See [`docs/PROJECT_STRUCTURE.md`](docs/PROJECT_STRUCTURE.md) for a full breakdown of every directory and file.

---

## API Overview

The backend exposes a REST API at `http://localhost:8000/api/`. Interactive docs are available at:

- **Swagger UI:** http://localhost:8000/docs
- **ReDoc:** http://localhost:8000/redoc

Key endpoint groups:

| Prefix | Description |
|---|---|
| `/api/search/{mtg\|pokemon\|baseball}` | Live card price search |
| `/api/collection` | Collection CRUD |
| `/api/watchlist` | Watchlist CRUD |
| `/api/owners` | Owner and profile management |
| `/api/sets` | Set catalog browsing |
| `/api/settings` | App and API source settings |
| `/api/export` | CSV / ZIP export and manual backup |
| `/api/import` | CSV import and ambiguity resolution |
