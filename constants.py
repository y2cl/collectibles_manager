"""
Constants and configuration for TCG Price Tracker
"""

import os

# Get the script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))

# Card display constants
CARD_IMAGE_WIDTH = 200
DEFAULT_CARDS_PER_ROW = 5
DEFAULT_RESULTS_PER_PAGE = 20

# Game constants
GAMES = {
    "mtg": "Magic: The Gathering",
    "pokemon": "Pokémon",
    "sports": "Sports Cards",
    "collectibles": "Collectibles",
}

SPORTS_CARD_CATEGORIES = {
    "baseball": "212",
    "football": "214",
    "basketball": "217",
    "hockey": "216",
    "soccer": "218",
    "other": "219",
}

# API source constants
API_SOURCES = {
    "scryfall": {
        "name": "Scryfall API",
        "game": "mtg",
        "free": True,
        "enabled_key": "scryfall_enabled"
    },
    "pokemontcg": {
        "name": "Pokémon TCG API", 
        "game": "pokemon",
        "free": False,
        "enabled_key": "pokemon_enabled",
        "secret_key": "POKEMONTCG_API_KEY"
    },
    "justtcg": {
        "name": "JustTCG API",
        "game": "multi",  # Multi-TCG
        "free": False,
        "enabled_key": "justtcg_enabled", 
        "secret_key": "JUSTTCG_API_KEY"
    },
    "public": {
        "name": "Public Endpoint",
        "game": "pokemon",
        "free": True,
        "enabled_key": "public_enabled"
    },
    "fallback": {
        "name": "Fallback Data",
        "game": "pokemon", 
        "free": True,
        "enabled_key": "fallback_enabled"
    },
    "sportscarddatabase": {
        "name": "SportsCardDatabase.com",
        "game": "sports",
        "free": True,
        "enabled_key": "sportscarddatabase_enabled",
        "description": "Free sports card database with comprehensive collection"
    },
    "ebay_sports": {
        "name": "eBay Sports Cards",
        "game": "sports",
        "free": False,
        "enabled_key": "ebay_sports_enabled",
        "secret_key": "EBAY_APP_ID",
        "sandbox_key": "EBAY_APP_ID_SBX",
        "description": "eBay marketplace for sports cards with real listings"
    }
}

# Cache file names (using absolute paths)
CACHE_FILES = {
    "pokemon_sets": os.path.join(SCRIPT_DIR, "fallback_data/Pokemon/pokemonsets.csv"),  # Pokemon now uses CSV
    "mtg_sets": os.path.join(SCRIPT_DIR, "fallback_data/MTG/mtgsets.csv")  # MTG now uses CSV as single source of truth
}

# Collection file names (using absolute paths)
COLLECTION_FILE = os.path.join(SCRIPT_DIR, "tcg_collection.csv")
WATCHLIST_FILE = os.path.join(SCRIPT_DIR, "tcg_watchlist.csv")

# UI constants
VIEW_MODES = ["Grid", "List"]
RESULTS_PER_PAGE_OPTIONS = [20, 40, 60]
QUANTITY_RANGE = (1, 999)

# Price field mappings
PRICE_FIELDS = {
    "mtg": ["usd", "usd_foil", "usd_etched"],
    "pokemon": ["low", "mid", "market"]
}

# Session state keys
SESSION_KEYS = {
    "collection": "collection",
    "api_settings": "api_settings", 
    "debug_mode": "debug_mode",
    "view_mode": "view_mode",
    "cards_per_row": "cards_per_row",
    "image_width": "image_width",
    "compact_mode": "compact_mode",
    "quick_mode_pkmn": "quick_mode_pkmn",
    "per_page": "per_page",
    "sort_option": "sort_option",
    "last_query": "last_query",
    "page_mtg": "page_mtg",
    "page_pkmn": "page_pkmn",
    "show_collection_view": "show_collection_view",
    "show_sets_view": "show_sets_view", 
    "show_mtg_sets_view": "show_mtg_sets_view"
}
