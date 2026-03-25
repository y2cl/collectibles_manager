import os
import io
import shutil
import zipfile
import time
import math
import json
import logging
import requests
import pandas as pd
import streamlit as st
from datetime import datetime, timezone
from typing import Dict, List, Optional, Tuple, Any, Union
import csv
import re
import hashlib
import urllib.parse
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote

# Import our modules
from constants import (
    CARD_IMAGE_WIDTH, DEFAULT_CARDS_PER_ROW, DEFAULT_RESULTS_PER_PAGE,
    GAMES, API_SOURCES, CACHE_FILES, COLLECTION_FILE, WATCHLIST_FILE,
    VIEW_MODES, RESULTS_PER_PAGE_OPTIONS, QUANTITY_RANGE,
    PRICE_FIELDS, SESSION_KEYS
)
from fallback_manager import (
    store_pokemon_card, store_pokemon_set, store_mtg_card, store_mtg_set, get_fallback_stats,
    find_pokemon_cards_local, find_mtg_cards_local,
)
from image_sources import find_baseball_card_image

# Paths
def get_collections_dir() -> str:
    """Return absolute path to the collections directory next to this script."""
    base_dir = os.path.dirname(__file__)
    coll_dir = os.path.join(base_dir, "collections")
    try:
        os.makedirs(coll_dir, exist_ok=True)
    except Exception:
        pass
    return coll_dir

# Owner helpers
def _sanitize_owner_id(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")

def _owner_folder_label(name: str) -> str:
    base = (name or "").strip()
    if not base:
        return ""
    return f"{base}" + ("'" if base.endswith("s") else "s") + " Collection"

def list_owner_folders() -> List[str]:
    """List existing owner folders under collections/."""
    out: List[str] = []
    try:
        coll_dir = get_collections_dir()
        for entry in os.listdir(coll_dir):
            p = os.path.join(coll_dir, entry)
            if os.path.isdir(p):
                out.append(entry)
    except Exception:
        pass
    return sorted(out)

def _owner_prefs_path() -> str:
    base = get_collections_dir()
    return os.path.join(base, 'owner_settings.json')

def load_owner_prefs() -> Dict:
    try:
        path = _owner_prefs_path()
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def save_owner_prefs(prefs: Dict) -> bool:
    try:
        path = _owner_prefs_path()
        with open(path, 'w', encoding='utf-8') as f:
            json.dump(prefs or {}, f, ensure_ascii=False, indent=2)
        return True
    except Exception:
        return False

def _sanitize_profile_id(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-") or "default"

def _get_active_profile_map() -> Dict[str, str]:
    """Returns mapping {owner_label: profile_id}. Stored in session and on disk."""
    m = st.session_state.get('active_profiles')
    if isinstance(m, dict):
        return m
    prefs = load_owner_prefs()
    m2 = prefs.get('active_profiles', {}) if isinstance(prefs, dict) else {}
    if not isinstance(m2, dict):
        m2 = {}
    st.session_state['active_profiles'] = m2
    return m2

def _get_active_profile_for_owner_label(owner_label: str) -> str:
    m = _get_active_profile_map()
    return m.get(owner_label, 'default')

def _set_active_profile_for_owner_label(owner_label: str, profile_id: str) -> None:
    m = _get_active_profile_map()
    m[owner_label] = profile_id or 'default'
    st.session_state['active_profiles'] = m
    # persist
    prefs = load_owner_prefs()
    if not isinstance(prefs, dict):
        prefs = {}
    prefs['active_profiles'] = m
    save_owner_prefs(prefs)

def owner_relative_filename(owner: Optional[str], base_filename: str) -> str:
    """Return a path relative to collections/ honoring owner folder and prefix, or base file when no owner."""
    owner = (owner or '').strip()
    if not owner or owner.lower() == 'default':
        return base_filename
    folder = _owner_folder_label(owner)
    oid = _sanitize_owner_id(owner)
    # Convert mtg_collection.csv -> {oid}-mtg_collection.csv
    parts = base_filename.split('/')[-1]
    # Insert active profile if not default
    profile = _get_active_profile_for_owner_label(folder)
    if profile and profile != 'default':
        rel = os.path.join(folder, f"{oid}-{profile}-{parts}")
    else:
        rel = os.path.join(folder, f"{oid}-{parts}")
    return rel

def ensure_owner_backfill(owner: str, current_collection: List[Dict]):
    """If selecting a non-default owner and their CSVs don't exist yet, backfill from current data."""
    if not owner or owner.lower() == 'default':
        return
    coll_dir = get_collections_dir()
    # Build owner file paths
    mtg_rel = owner_relative_filename(owner, 'mtg_collection.csv')
    pkmn_rel = owner_relative_filename(owner, 'pokemon_collection.csv')
    uni_rel = owner_relative_filename(owner, 'unified_collection.csv')
    paths = [mtg_rel, pkmn_rel, uni_rel]
    need_backfill = False
    for rel in paths:
        if not os.path.exists(os.path.join(coll_dir, rel)):
            need_backfill = True
            break
    if not need_backfill:
        return
    # Prepare per-game subsets
    mtg_cards = [c for c in current_collection if c.get('game') == 'Magic: The Gathering']
    pokemon_cards = [c for c in current_collection if c.get('game') == 'Pokémon']
    # Save
    save_collection_to_csv(current_collection, uni_rel)
    if mtg_cards:
        save_collection_to_csv(mtg_cards, mtg_rel)
    if pokemon_cards:
        save_collection_to_csv(pokemon_cards, pkmn_rel)

# Initialize session state defaults
def load_csv_collections():
    """Load collections from CSV files in the collections folder"""
    collections = []
    coll_dir = get_collections_dir()
    # Resolve owner-aware file locations
    try:
        owner_label = st.session_state.get('current_owner_label', st.session_state.get('default_owner_label', 'Default'))
    except Exception:
        owner_label = 'Default'
    owner = _owner_from_folder_label(owner_label)
    
    # Load MTG collection
    try:
        mtg_rel = owner_relative_filename(owner, "mtg_collection.csv")
        mtg_file = os.path.join(coll_dir, mtg_rel)
        if os.path.exists(mtg_file):
            with open(mtg_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('name'):  # Skip empty rows
                        # derive price_usd using available columns
                        price_low = row.get('price_low') or ''
                        price_mid = row.get('price_mid') or ''
                        price_market = row.get('price_market') or ''
                        price_usd_raw = row.get('price_usd') or ''
                        price_candidates = [price_usd_raw, price_market, price_mid, price_low]
                        price_clean = next((p for p in price_candidates if str(p).strip() not in ('', 'None')), '0')
                        try:
                            price_val = float(price_clean)
                        except Exception:
                            try:
                                price_val = float(str(price_clean).replace('$','').replace(',',''))
                            except Exception:
                                price_val = 0.0
                        # parse paid if present
                        paid_raw = row.get('paid') or row.get('Paid') or ''
                        try:
                            paid_val = float(str(paid_raw).replace('$','').replace(',','')) if str(paid_raw).strip() else 0.0
                        except Exception:
                            paid_val = 0.0

                        card = {
                            "game": row.get('game', 'Magic: The Gathering'),
                            "name": row.get('name', ''),
                            "set": row.get('set', ''),
                            "set_code": row.get('set_code', ''),
                            "link": row.get('link', ''),
                            "image_url": row.get('image_url', ''),
                            "price_usd": price_val,
                            "price_low": float(price_low) if str(price_low).strip() not in ('', 'None') else None,
                            "price_mid": float(price_mid) if str(price_mid).strip() not in ('', 'None') else None,
                            "price_market": float(price_market) if str(price_market).strip() not in ('', 'None') else None,
                            "paid": paid_val,
                            "price_usd_foil": float(row.get('price_usd_foil', 0)) if row.get('price_usd_foil') else 0,
                            "price_usd_etched": float(row.get('price_usd_etched', 0)) if row.get('price_usd_etched') else 0,
                            "quantity": int(row.get('quantity', 1)) if row.get('quantity') else 1,
                            "variant": row.get('variant', ''),
                            "date_added": row.get('timestamp', ''),
                            "card_number": row.get('card_number', '') or row.get('collector_number', ''),
                            "year": row.get('year', ''),
                            "source": "CSV Collection"
                        }
                        # Add additional fields for consistency
                        card.update({
                            "team": "",
                            "position": ""
                        })
                        collections.append(card)
            print(f"✅ Loaded {len([c for c in collections if c['game'] == 'Magic: The Gathering'])} MTG cards from CSV")
    except Exception as e:
        print(f"❌ Error loading MTG collection: {e}")
    
    # Load Pokemon collection
    try:
        pokemon_rel = owner_relative_filename(owner, "pokemon_collection.csv")
        unified_rel = owner_relative_filename(owner, "unified_collection.csv")
        pokemon_file = os.path.join(coll_dir, pokemon_rel)
        unified_file = os.path.join(coll_dir, unified_rel)
        if os.path.exists(pokemon_file):
            with open(pokemon_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('name'):  # Skip empty rows
                        # derive price_usd using available columns
                        price_low = row.get('price_low') or ''
                        price_mid = row.get('price_mid') or ''
                        price_market = row.get('price_market') or ''
                        price_usd_raw = row.get('price_usd') or ''
                        price_candidates = [price_usd_raw, price_market, price_mid, price_low]
                        price_clean = next((p for p in price_candidates if str(p).strip() not in ('', 'None')), '0')
                        try:
                            price_val = float(price_clean)
                        except Exception:
                            try:
                                price_val = float(str(price_clean).replace('$','').replace(',',''))
                            except Exception:
                                price_val = 0.0
                        # parse paid if present
                        paid_raw = row.get('paid') or row.get('Paid') or ''
                        try:
                            paid_val = float(str(paid_raw).replace('$','').replace(',','')) if str(paid_raw).strip() else 0.0
                        except Exception:
                            paid_val = 0.0

                        card = {
                            "game": row.get('game', 'Pokémon'),
                            "name": row.get('name', ''),
                            "set": row.get('set', ''),
                            "set_code": row.get('set_code', ''),
                            "link": row.get('link', ''),
                            "image_url": row.get('image_url', ''),
                            "price_usd": price_val,
                            "price_low": float(price_low) if str(price_low).strip() not in ('', 'None') else None,
                            "price_mid": float(price_mid) if str(price_mid).strip() not in ('', 'None') else None,
                            "price_market": float(price_market) if str(price_market).strip() not in ('', 'None') else None,
                            "paid": paid_val,
                            "price_usd_foil": float(row.get('price_usd_foil', 0)) if row.get('price_usd_foil') else 0,
                            "quantity": int(row.get('quantity', 1)) if row.get('quantity') else 1,
                            "variant": row.get('variant', ''),
                            "date_added": row.get('timestamp', ''),
                            "card_number": row.get('card_number', ''),
                            "year": row.get('year', ''),
                            "source": "CSV Collection"
                        }
                        # Add additional fields for consistency
                        card.update({
                            "team": "",
                            "position": "",
                            "price_usd_etched": 0
                        })
                        collections.append(card)
            print(f"✅ Loaded {len([c for c in collections if c['game'] == 'Pokémon'])} Pokémon cards from CSV")
    except Exception as e:
        print(f"❌ Error loading Pokemon collection: {e}")
    
    # Unified file is deprecated as a stored source; per-game files are sources of truth.

    return collections

def load_watchlist_from_csv(filename: str = "watchlist.csv") -> List[Dict]:
    """Load watchlist items from collections/watchlist.csv."""
    items: List[Dict] = []
    try:
        coll_dir = get_collections_dir()
        try:
            owner_label = st.session_state.get('current_owner_label', st.session_state.get('default_owner_label', 'Default'))
        except Exception:
            owner_label = 'Default'
        owner = _owner_from_folder_label(owner_label)
        rel = owner_relative_filename(owner, filename)
        filepath = os.path.join(coll_dir, rel)
        if not os.path.exists(filepath):
            return items
        with open(filepath, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                if not row.get('name'):
                    continue
                def _to_float(v):
                    try:
                        return float(v)
                    except Exception:
                        try:
                            return float(str(v).replace('$','').replace(',',''))
                        except Exception:
                            return 0.0
                def _to_int(v):
                    try:
                        return int(v)
                    except Exception:
                        return 1
                item = {
                    'game': row.get('game', ''),
                    'name': row.get('name', ''),
                    'set': row.get('set', ''),
                    'link': row.get('link', ''),
                    'image_url': row.get('image_url', ''),
                    'price_usd': _to_float(row.get('price_usd', 0)),
                    'price_usd_foil': _to_float(row.get('price_usd_foil', 0)),
                    'price_usd_etched': _to_float(row.get('price_usd_etched', 0)),
                    'quantity': _to_int(row.get('quantity', 1)),
                    'variant': row.get('variant', ''),
                    'target_price': _to_float(row.get('target_price', 0)),
                    'signed': row.get('signed', ''),
                    'altered': row.get('altered', ''),
                    'notes': row.get('notes', ''),
                    'date_added': row.get('timestamp', ''),
                    # fields that may not be present in watchlist CSV
                    'year': row.get('year', ''),
                    'card_number': row.get('card_number', ''),
                    'source': 'CSV Watchlist',
                }
                items.append(item)
        print(f"✅ Loaded {len(items)} watchlist item(s) from CSV")
    except Exception as e:
        print(f"❌ Error loading watchlist: {e}")
    return items

def save_collection_to_csv(collection: List[Dict], filename: str):
    """Save collection to CSV file in collections folder"""
    try:
        coll_dir = get_collections_dir()
        try:
            owner_label = st.session_state.get('current_owner_label', st.session_state.get('default_owner_label', 'Default'))
        except Exception:
            owner_label = 'Default'
        owner = _owner_from_folder_label(owner_label)
        rel = filename if ('/' in filename or filename.startswith('.')) else owner_relative_filename(owner, filename)
        filepath = os.path.join(coll_dir, rel)
        # Define CSV headers
        headers = [
            'game', 'name', 'set', 'set_code', 'card_number', 'year', 'link', 'image_url', 'price_low', 'price_mid', 'price_market',
            'price_usd', 'price_usd_foil', 'price_usd_etched', 'quantity', 'variant', 'total_value', 'paid', 'signed', 'altered', 'notes', 'timestamp'
        ]
        
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            
            for card in collection:
                # compute market value and total
                try:
                    mv = card.get('price_market') if card.get('price_market') is not None else card.get('price_usd', 0)
                except Exception:
                    mv = card.get('price_usd', 0)
                try:
                    qty = int(card.get('quantity', 1) or 1)
                except Exception:
                    qty = 1
                total_val = (mv or 0) * qty

                row = {
                    'game': card.get('game', ''),
                    'name': card.get('name', ''),
                    'set': card.get('set', ''),
                    'set_code': card.get('set_code', ''),
                    'card_number': card.get('card_number', ''),
                    'year': card.get('year', ''),
                    'link': card.get('link', ''),
                    'image_url': card.get('image_url', ''),
                    'price_low': '',  # Not used in current structure
                    'price_mid': '',  # Not used in current structure
                    'price_market': '',  # Not used in current structure
                    'price_usd': card.get('price_usd', 0),
                    'price_usd_foil': card.get('price_usd_foil', 0),
                    'price_usd_etched': card.get('price_usd_etched', 0),
                    'quantity': card.get('quantity', 1),
                    'variant': card.get('variant', ''),
                    'total_value': total_val,
                    'paid': card.get('paid', 0.0),
                    'signed': card.get('signed', ''),
                    'altered': card.get('altered', ''),
                    'notes': card.get('notes', ''),
                    'timestamp': card.get('date_added', '')
                }
                writer.writerow(row)
        
        print(f"✅ Saved {len(collection)} cards to {filepath}")
        return True
    except Exception as e:
        print(f"❌ Error saving collection to CSV: {e}")
        return False

def save_watchlist_to_csv(watchlist: List[Dict], filename: str = "watchlist.csv"):
    """Save watchlist to CSV file in collections folder (same schema as collection)."""
    try:
        coll_dir = get_collections_dir()
        try:
            owner_label = st.session_state.get('current_owner_label', st.session_state.get('default_owner_label', 'Default'))
        except Exception:
            owner_label = 'Default'
        owner = _owner_from_folder_label(owner_label)
        rel = owner_relative_filename(owner, filename)
        filepath = os.path.join(coll_dir, rel)
        headers = [
            'game', 'name', 'set', 'link', 'image_url', 'price_low', 'price_mid', 'price_market',
            'price_usd', 'price_usd_foil', 'price_usd_etched', 'quantity', 'variant', 'target_price', 'signed', 'altered', 'notes', 'timestamp'
        ]
        with open(filepath, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=headers)
            writer.writeheader()
            for card in watchlist:
                row = {
                    'game': card.get('game', ''),
                    'name': card.get('name', ''),
                    'set': card.get('set', ''),
                    'link': card.get('link', ''),
                    'image_url': card.get('image_url', ''),
                    'price_low': '',
                    'price_mid': '',
                    'price_market': '',
                    'price_usd': card.get('price_usd', 0),
                    'price_usd_foil': card.get('price_usd_foil', 0),
                    'price_usd_etched': card.get('price_usd_etched', 0),
                    'quantity': card.get('quantity', 1),
                    'variant': card.get('variant', ''),
                    'target_price': card.get('target_price', 0.0),
                    'signed': card.get('signed', ''),
                    'altered': card.get('altered', ''),
                    'notes': card.get('notes', ''),
                    'timestamp': card.get('date_added', '')
                }
                writer.writerow(row)
        print(f"✅ Saved {len(watchlist)} items to {filepath}")
        return True
    except Exception as e:
        print(f"❌ Error saving watchlist to CSV: {e}")
        return False

def initialize_session_state():
    """Initialize Streamlit session state variables"""
    # Load CSV collections first
    csv_collections = load_csv_collections()
    
    # Load Watchlist from CSV as well
    csv_watchlist = load_watchlist_from_csv()

    defaults = {
        SESSION_KEYS["collection"]: csv_collections,  # Load from CSV files
        SESSION_KEYS["api_settings"]: {},
        SESSION_KEYS["debug_mode"]: False,
        SESSION_KEYS["view_mode"]: "Grid",
        SESSION_KEYS["cards_per_row"]: DEFAULT_CARDS_PER_ROW,
        SESSION_KEYS["image_width"]: CARD_IMAGE_WIDTH,
        SESSION_KEYS["compact_mode"]: False,
        SESSION_KEYS["quick_mode_pkmn"]: False,
        SESSION_KEYS["per_page"]: DEFAULT_RESULTS_PER_PAGE,
        SESSION_KEYS["sort_option"]: "Set Number",
        SESSION_KEYS["last_query"]: {},
        SESSION_KEYS["page_mtg"]: 1,
        SESSION_KEYS["page_pkmn"]: 1,
        SESSION_KEYS["show_collection_view"]: False,
        SESSION_KEYS["show_sets_view"]: False,
        SESSION_KEYS["show_mtg_sets_view"]: False,
        # local view flag for settings page
        "show_settings_view": False,
        "scryfall_enabled": True,
        "pokemontcg_enabled": False,
        "justtcg_enabled": False,
        "pokemonpublic_enabled": True,
        "fallback_enabled": True,
        "sportscarddatabase_enabled": True,
        "sportscardspro_enabled": False,
        "ebay_enabled": True,
        "last_ebay_env": "Sandbox",
        "watchlist": csv_watchlist,
        # Settings defaults
        "duplicate_strategy": "merge",  # 'merge' or 'separate'
        "paid_merge_strategy": "sum"    # placeholder for future use: 'sum'|'average'|'ignore'
    }
    
    # Merge in API config defaults if provided
    api_cfg = load_api_config()
    if isinstance(api_cfg, dict):
        for k, v in api_cfg.items():
            if k in defaults:
                defaults[k] = v
        # keep a copy of full API config in session
        st.session_state["api_config"] = api_cfg

    # Load owner preferences (default owner) from disk, if any
    owner_prefs = load_owner_prefs()
    if isinstance(owner_prefs, dict):
        def_owner = owner_prefs.get('default_owner_label')
        if def_owner:
            defaults['default_owner_label'] = def_owner
        if isinstance(owner_prefs.get('active_profiles'), dict):
            st.session_state['active_profiles'] = owner_prefs.get('active_profiles')

    for key, default_value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = default_value
    
    # Print collection loading info
    if csv_collections:
        print(f"📚 Loaded {len(csv_collections)} total cards from CSV files")
        mtg_count = len([c for c in csv_collections if c['game'] == 'Magic: The Gathering'])
        pokemon_count = len([c for c in csv_collections if c['game'] == 'Pokémon'])
        print(f"   - MTG: {mtg_count} cards")
        print(f"   - Pokémon: {pokemon_count} cards")
    else:
        print("📝 No CSV collections found or loaded")

def get_secret(key: str) -> Optional[str]:
    """Get secret from Streamlit secrets or environment variables"""
    try:
        # Try Streamlit secrets first
        if hasattr(st, 'secrets') and key in st.secrets:
            return st.secrets[key]
        # Fall back to environment variables
        return os.getenv(key)
    except Exception:
        return None

def load_api_config() -> dict:
    """Load API source configuration from api_config.json if present."""
    try:
        base_dir = os.path.dirname(__file__)
        path = os.path.join(base_dir, 'api_config.json')
        if os.path.exists(path):
            with open(path, 'r', encoding='utf-8') as f:
                data = json.load(f)
                return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}

def render_add_to_collection_button(card_data: Dict, button_key: str, quantity_key: str, variant: Dict = None):
    """Render add to collection button"""
    with st.container():
        col1, col2 = st.columns([1, 2])
        with col1:
            quantity = st.number_input("Qty", min_value=1, max_value=999, value=1, key=quantity_key)
        with col2:
            if st.button("Add to Collection", key=button_key):
                # Add to collection
                collection = st.session_state.get(SESSION_KEYS["collection"], [])
                
                # Create a copy of the card data with quantity
                card_copy = card_data.copy()
                card_copy["quantity"] = quantity
                card_copy["date_added"] = datetime.now().isoformat()
                
                # Check if card already exists in collection
                existing_card = None
                for i, existing in enumerate(collection):
                    # Prefer set_code when present on either side
                    ex_set = existing.get("set_code") or existing.get("set")
                    new_set = card_copy.get("set_code") or card_copy.get("set")
                    if (existing.get("name") == card_copy.get("name") and 
                        ex_set == new_set and
                        existing.get("card_number") == card_copy.get("card_number") and
                        existing.get("variety") == card_copy.get("variety")):
                        existing_card = i
                        break
                
                if existing_card is not None:
                    # Update existing card quantity
                    collection[existing_card]["quantity"] += quantity
                    st.success(f"Updated quantity! Now have {collection[existing_card]['quantity']} of this card")
                else:
                    # Add new card to collection
                    collection.append(card_copy)
                    st.success(f"Added {quantity} to collection!")
                
                # Save to session state
                st.session_state[SESSION_KEYS["collection"]] = collection
                
                # Also save to game-specific CSV files
                mtg_cards = [c for c in collection if c.get("game") == "Magic: The Gathering"]
                pokemon_cards = [c for c in collection if c.get("game") == "Pokémon"]
                
                if mtg_cards:
                    save_collection_to_csv(mtg_cards, "mtg_collection.csv")
                if pokemon_cards:
                    save_collection_to_csv(pokemon_cards, "pokemon_collection.csv")
                
                st.rerun()

def render_add_to_watchlist_button(card_data: Dict, button_key: str):
    """Render add to watchlist button"""
    if st.button("⭐ Add to Watchlist", key=button_key):
        st.success("Added to watchlist!")

def render_variant_selector(game: str, prices: Dict, selector_key: str) -> Dict:
    """Render variant selector for card pricing"""
    variants = []
    selected_prices = {}
    
    if game == "Magic: The Gathering":
        if prices.get("usd") is not None:
            variants.append("nonfoil")
            selected_prices["nonfoil"] = prices["usd"]
        if prices.get("usd_foil") is not None:
            variants.append("foil")
            selected_prices["foil"] = prices["usd_foil"]
        if prices.get("usd_etched") is not None:
            variants.append("etched")
            selected_prices["etched"] = prices["usd_etched"]
    elif game == "Pokémon":
        # Support TCGPlayer-style keys and map to friendly variant names
        # prices may include: normal, holofoil, reverseHolofoil, 1stEditionHolofoil, 1stEdition
        mapping = {
            "normal": "normal",
            "holofoil": "holo",
            "reverseHolofoil": "reverse_holo",
            "1stEditionHolofoil": "1st_edition_holo",
            "1stEdition": "1st_edition"
        }
        for src_key, vname in mapping.items():
            if prices.get(src_key) is not None:
                variants.append(vname)
                selected_prices[vname] = prices.get(src_key) or 0.0
    elif game == "Baseball Cards":
        if prices.get("price_usd") is not None:
            variants.append("base")
            selected_prices["base"] = prices["price_usd"]
    
    if not variants:
        return {}
    
    selected = st.selectbox(
        "Variant:",
        options=variants,
        key=selector_key,
        format_func=lambda x: x.replace("_", " ").title()
    )
    
    return {
        "selected": selected,
        "price": selected_prices.get(selected, 0.0),
        "all_prices": selected_prices
    }

def create_mock_baseball_cards(player_name: str, year: str = "", team: str = "", set_name: str = "", card_number: str = "", source: str = "Mock Data") -> List[Dict]:
    """Create mock baseball cards for testing when no real data is available"""
    cards = []
    
    # Default sets if none provided
    if not set_name:
        if year:
            set_name = f"{year} Topps"
        else:
            set_name = "2023 Topps"
    
    # Create 3 mock cards with different varieties
    varieties = ["Base", "Rookie", "Refractor"]
    colors = ["4169E1", "FFD700", "FF6347"]  # Blue, Gold, Red
    
    for i, (variety, color) in enumerate(zip(varieties, colors)):
        card = {
            "name": player_name,
            "set": set_name,
            "year": year or "2023",
            "team": team or "Unknown Team",
            "card_number": card_number or str(i + 1),
            "position": "Fielder",
            "variety": variety,
            "price_usd": round(10.0 + (i * 5.0), 2),  # Mock prices
            "image_url": f"https://picsum.photos/seed/{player_name.replace(' ', '_')}{year}{set_name.replace(' ', '_')}{card_number or str(i+1)}/300/420",
            "link": f"https://example.com/card/{i+1}",
            "game": "Baseball Cards",
            "quantity": 1,
            "variant": "",
            "source": source
        }
        cards.append(card)
    
    print(f"🧪 Created {len(cards)} mock baseball cards")
    return cards

def baseball_search_ebay(player_name: str, year: str = "", team: str = "", set_name: str = "", card_number: str = "") -> Tuple[List[Dict], int, int, str]:
    """Search eBay for baseball cards"""
    try:
        # Check which eBay environment to use
        ebay_env = st.session_state.get("last_ebay_env", "Sandbox")
        
        if ebay_env == "Production":
            ebay_app_id = get_secret("EBAY_APP_ID")
            base_url = "https://svcs.ebay.com/services/search/FindingService/v1"
            print("🚀 Using eBay Production API")
        else:
            ebay_app_id = get_secret("EBAY_APP_ID_SBX")
            base_url = "https://svcs.sandbox.ebay.com/services/search/FindingService/v1"
            print("🧪 Using eBay Sandbox API")
        
        if not ebay_app_id:
            st.error(f"❌ eBay API key not configured for {ebay_env} environment")
            print(f"❌ eBay API key not configured for {ebay_env}")
            return [], 0, 0, f"eBay API key not configured for {ebay_env}"
        
        print(f"🔑 eBay App ID: {ebay_app_id[:15]}... ({ebay_env})")
        
        # Build search query
        query_parts = [player_name.strip()]
        if year:
            query_parts.append(year)
        if team:
            query_parts.append(team)
        if set_name:
            query_parts.append(set_name)
        if card_number:
            query_parts.append(f"#{card_number}")
        
        query = " ".join(query_parts) + " baseball card"
        print(f"🔍 Search query: {query}")
        
        # API parameters
        params = {
            "OPERATION-NAME": "findItemsAdvanced",
            "SERVICE-VERSION": "1.0.0",
            "SECURITY-APPNAME": ebay_app_id,
            "RESPONSE-DATA-FORMAT": "JSON",
            "REST-PAYLOAD": "",
            "keywords": query,
            "categoryId": "212",  # Baseball cards
            "itemFilter(0).name": "Condition",
            "itemFilter(0).value": "New",
            "itemFilter(1).name": "ListingType",
            "itemFilter(1).value": "AuctionWithBIN",
            "sortOrder": "BestMatch",
            "paginationInput.entriesPerPage": "50"
        }
        
        print(f"🌐 Making request to: {base_url}")
        
        response = requests.get(base_url, params=params, timeout=30)
        
        print(f"📊 Response status: {response.status_code}")
        
        # Check HTTP status codes
        if response.status_code == 401 or response.status_code == 403:
            print("🧪 eBay authentication failed - using mock data")
            st.warning("🧪 eBay authentication failed - using mock data")
            return create_mock_baseball_cards(player_name, year, team, set_name, card_number, f"eBay {ebay_env} - Authentication failed"), 3, 3, f"eBay {ebay_env} (Mock Data)"
        
        response.raise_for_status()
        data = response.json()
        
        # Parse response for errors
        find_response = data.get("findItemsAdvancedResponse", [{}])[0]
        errors = find_response.get("errors", [])
        
        if errors and isinstance(errors, list) and len(errors) > 0:
            error_info = errors[0]
            error_id = error_info.get("errorId", [])
            message = error_info.get("message", [])
            
            print(f"❌ eBay Error ID: {error_id}")
            print(f"❌ eBay Error Message: {message}")
            st.error(f"❌ eBay Error: {message}")
            
            if (isinstance(error_id, list) and "11002" in error_id) or \
               (isinstance(message, list) and any("Invalid Application" in str(msg) for msg in message)):
                print("🧪 eBay Sandbox App ID not registered - using mock data")
                st.warning("🧪 eBay Sandbox App ID not registered - using mock data")
                return create_mock_baseball_cards(player_name, year, team, set_name, card_number, f"eBay {ebay_env} - App ID not registered"), 3, 3, f"eBay {ebay_env} (Mock Data)"
        
        # Parse results
        search_result = find_response.get("searchResult", [{}])[0].get("item", [])
        print(f"🎯 Found {len(search_result)} items in search results")
        
        if len(search_result) == 0:
            st.warning(f"🔍 No items found in eBay {ebay_env.lower()}. This is normal for sandbox - limited test data.")
            st.info("💡 Using mock data for demonstration purposes.")
            cards = create_mock_baseball_cards(player_name, year, team, set_name, card_number)
            return cards, len(cards), len(cards), f"eBay {ebay_env} (Mock Data)"
        
        # Process real results
        cards = []
        for item in search_result:
            try:
                # Extract item details
                title = item.get("title", [{}])[0]
                item_id = item.get("itemId", [{}])[0]
                gallery_url = item.get("galleryURL", [{}])[0]
                view_item_url = item.get("viewItemURL", [{}])[0]
                
                # Create card data
                card_data = {
                    "name": player_name,
                    "set": set_name or "Unknown Set",
                    "year": year or "",
                    "team": team or "",
                    "card_number": card_number or "",
                    "position": "",
                    "variety": "Base",
                    "price_usd": 0.0,
                    "image_url": gallery_url,
                    "link": view_item_url,
                    "game": "Baseball Cards",
                    "quantity": 1,
                    "variant": "",
                    "source": f"eBay {ebay_env}"
                }
                cards.append(card_data)
                
            except Exception as e:
                print(f"⚠️ Error processing eBay item: {e}")
                continue
        
        print(f"✅ Successfully processed {len(cards)} cards from eBay {ebay_env}")
        return cards, len(cards), len(cards), f"eBay {ebay_env}"
        
    except Exception as e:
        error_msg = f"eBay {ebay_env} Error: {str(e)}"
        print(error_msg)
        st.error(f"❌ {error_msg}")
        return [], 0, 0, error_msg

def search_mtg_scryfall(card_name: str, set_hint: str = "", collector_number: str = "") -> Tuple[List[Dict], int, int, str]:
    try:
        if not st.session_state.get("scryfall_enabled", True):
            return [], 0, 0, "Scryfall Disabled"
        q = card_name.strip()
        if set_hint.strip():
            q = f"{q} {set_hint.strip()}"
        if collector_number and str(collector_number).strip():
            q = f"{q} cn:{str(collector_number).strip()}"
        params = {
            "q": q,
            "order": "released",
            "unique": "prints"
        }
        url = "https://api.scryfall.com/cards/search"
        resp = requests.get(url, params=params, timeout=30)
        if resp.status_code == 404:
            return [], 0, 0, "Scryfall"
        resp.raise_for_status()
        data = resp.json()
        items = data.get("data", [])
        cards: List[Dict] = []
        import re as _re
        for c in items:
            try:
                set_name = c.get("set_name", "")
                released = c.get("released_at", "")
                m4 = _re.search(r"(19\d{2}|20\d{2})", str(released))
                year = m4.group(1) if m4 else str(released)
                img = None
                iu = c.get("image_uris") or {}
                if iu:
                    img = iu.get("normal") or iu.get("large") or iu.get("small")
                else:
                    faces = c.get("card_faces") or []
                    if faces and isinstance(faces, list):
                        iu2 = faces[0].get("image_uris") or {}
                        img = iu2.get("normal") or iu2.get("large") or iu2.get("small")
                prices = c.get("prices") or {}
                def _to_float(v):
                    try:
                        return float(v) if v not in (None, "", "None") else 0.0
                    except Exception:
                        return 0.0
                # Variant availability flags from Scryfall
                has_nonfoil = bool(c.get('nonfoil'))
                has_foil = bool(c.get('foil'))
                card = {
                    "game": "Magic: The Gathering",
                    "name": c.get("name", ""),
                    "set": set_name,
                    "set_code": c.get("set", ""),
                    "year": year,
                    "artist": c.get("artist") or ( (c.get("card_faces") or [{}])[0].get("artist") if isinstance(c.get("card_faces"), list) and c.get("card_faces") else "" ),
                    "team": "",
                    "position": "",
                    "card_number": c.get("collector_number", ""),
                    "variety": "",
                    "price_usd": _to_float(prices.get("usd")),
                    "price_usd_foil": _to_float(prices.get("usd_foil")),
                    "price_usd_etched": _to_float(prices.get("usd_etched")),
                    "image_url": img or "",
                    "link": c.get("scryfall_uri", ""),
                    "quantity": 1,
                    "variant": "",
                    "source": "Scryfall",
                    "has_nonfoil": has_nonfoil,
                    "has_foil": has_foil
                }
                cards.append(card)
                # Persist full raw card to fallback for offline use
                try:
                    if st.session_state.get("fallback_enabled", True):
                        store_mtg_card(c)
                except Exception:
                    pass
            except Exception:
                continue
        return cards, len(cards), len(items), "Scryfall"
    except Exception as e:
        return [], 0, 0, f"Scryfall Error: {str(e)}"

def search_pokemon_tcg(card_name: str, set_hint: str = "", number: str = "") -> Tuple[List[Dict], int, int, str]:
    """Search Pokémon cards via the Pokémon TCG API.
    Returns (cards, shown_count, total_count, source_label).
    """
    try:
        # Check toggles
        enabled = bool(st.session_state.get("pokemontcg_enabled", False) or st.session_state.get("pokemonpublic_enabled", False))
        if not enabled:
            return [], 0, 0, "Pokémon TCG Disabled"

        # Build query string per API syntax: q=name:Pikachu set.name:"Base Set" number:58
        qs: List[str] = []
        nm = (card_name or "").strip()
        if nm:
            qs.append(f"name:{nm}")
        sh = (set_hint or "").strip()
        if sh:
            # Prefer set.id when a short uppercase code is provided; else set.name
            if len(sh) <= 5 and sh.upper() == sh:
                qs.append(f"set.id:{sh}")
            else:
                qs.append(f"set.name:\"{sh}\"")
        num = (number or "").strip()
        if num:
            qs.append(f"number:{num}")
        q = " ".join(qs) if qs else nm

        params = {"q": q, "orderBy": "set.releaseDate"}
        url = st.session_state.get("pokemontcg_api", "https://api.pokemontcg.io/v2/cards")
        headers = {}
        # Optional API key
        try:
            api_key = st.secrets.get("POKEMONTCG_API_KEY", "")
        except Exception:
            api_key = ""
        if st.session_state.get("pokemontcg_enabled", False) and api_key:
            headers["X-Api-Key"] = api_key

        resp = requests.get(url, params=params, headers=headers, timeout=30)
        resp.raise_for_status()
        data = resp.json() or {}
        items = data.get("data", [])
        # If no results and a number was provided, retry without number and do a client-side prefix match.
        if not items and num:
            params_no_num = {"q": " ".join([s for s in qs if not s.startswith("number:")]) or nm, "orderBy": "set.releaseDate"}
            resp2 = requests.get(url, params=params_no_num, headers=headers, timeout=30)
            if resp2.ok:
                data2 = resp2.json() or {}
                items = [c for c in (data2.get("data", []) or []) if str(c.get("number", "")).startswith(num)]
        cards: List[Dict] = []
        for c in items:
            try:
                set_obj = c.get("set", {}) or {}
                set_name = set_obj.get("name", "")
                set_code = set_obj.get("id", "")
                released = set_obj.get("releaseDate", "")
                year = (str(released)[:4] if released else "")
                imgs = (c.get("images") or {})
                img_url = imgs.get("small") or imgs.get("large") or ""
                # Prefer tcgplayer url when available for a public-facing link
                link = ( (c.get("tcgplayer") or {}).get("url")
                         or (c.get("cardmarket") or {}).get("url")
                         or f"https://pokemontcg.io/card/{c.get('id','')}")
                # TCGPlayer prices structure: normal/holofoil/etc -> { low, mid, market }
                prices = ((c.get("tcgplayer") or {}).get("prices") or {})
                # Choose prices; collect low/mid/market
                def _pluck_market(pr: Dict) -> float:
                    try:
                        return float((pr or {}).get("market") or 0)
                    except Exception:
                        return 0.0
                def _pluck_low(pr: Dict) -> float:
                    try:
                        return float((pr or {}).get("low") or 0)
                    except Exception:
                        return 0.0
                def _pluck_mid(pr: Dict) -> float:
                    try:
                        return float((pr or {}).get("mid") or 0)
                    except Exception:
                        return 0.0
                market_price = 0.0
                prices_map = {}
                for k in [
                    "normal",
                    "holofoil",
                    "reverseHolofoil",
                    "1stEditionHolofoil",
                    "1stEdition",
                    "unlimited",
                    "unlimitedHolofoil",
                ]:
                    p = prices.get(k) or {}
                    low_v = _pluck_low(p)
                    mid_v = _pluck_mid(p)
                    mkt_v = _pluck_market(p)
                    if any([low_v, mid_v, mkt_v]):
                        prices_map[k] = {"low": low_v, "mid": mid_v, "market": mkt_v}
                        market_price = mkt_v or market_price
                card = {
                    "game": "Pokémon",
                    "name": c.get("name", ""),
                    "set": set_name,
                    "set_code": set_code,
                    "year": year,
                    "card_number": c.get("number", ""),
                    "image_url": img_url,
                    "link": link,
                    "price_usd": market_price,
                    "quantity": 1,
                    "variety": "",
                    "prices_map": prices_map,
                    "source": "Pokémon TCG"
                }
                # Fallback persistence: store full raw card and set objects
                try:
                    if st.session_state.get("fallback_enabled", True):
                        store_pokemon_card(c)
                        if set_obj:
                            store_pokemon_set(set_obj)
                except Exception:
                    pass
                cards.append(card)
            except Exception:
                continue
        return cards, len(cards), len(items), "Pokémon TCG"
    except Exception as e:
        return [], 0, 0, f"Pokémon TCG Error: {str(e)}"

def render_pokemon_search_results(cards: List[Dict]):
    """Render Pokémon search results with image, details, price, and actions."""
    if not cards:
        st.info("No results to display.")
        return
    try:
        st.session_state["pkmn_last_results"] = cards
        st.session_state["pkmn_results_visible"] = True
    except Exception:
        pass
    # View controls (defaults tuned for larger images)
    vc1, vc2 = st.columns(2)
    with vc1:
        cols_per_row = st.slider("Cards per Row", 1, 6, value=4, key="pkmn_cards_per_row")
    with vc2:
        image_width = st.slider("Image Width", 120, 500, value=280, key="pkmn_image_width")
    for i, card in enumerate(cards):
        if i % cols_per_row == 0:
            row = st.columns(cols_per_row)
        with row[i % cols_per_row]:
            with st.container(border=True):
                # Top row: Image (left) and Meta (right)
                top_l, top_r = st.columns([2,3])
                with top_l:
                    if card.get('image_url'):
                        st.image(card['image_url'], width=image_width)
                with top_r:
                    st.markdown(f"**{card.get('name','')}**")
                    set_code = (card.get('set_code') or '').upper()
                    set_line = f"[{set_code}] {card.get('set','')}" if set_code else f"{card.get('set','')}"
                    st.caption(f"Set: {set_line}  •  No. {card.get('card_number','')}  •  {card.get('year','')}")
                    if isinstance(card.get('price_usd'), (int,float)) and card.get('price_usd'):
                        st.write(f"Market: ${float(card.get('price_usd')):.2f}")
                    if card.get('link'):
                        st.link_button("Open", card['link'])

                # Variants (checkbox + qty) directly below image/meta
                prices_src = card.get('prices_map') or {}
                fmap = {
                    'normal': ('Normal', prices_src.get('normal')),
                    'unlimited': ('Unlimited', prices_src.get('unlimited')),
                    'holo': ('Holo', prices_src.get('holofoil')),
                    'unlimited_holo': ('Unlimited Holo', prices_src.get('unlimitedHolofoil')),
                    'reverse_holo': ('Reverse Holo', prices_src.get('reverseHolofoil')),
                    '1st_edition_holo': ('1st Edition Holo', prices_src.get('1stEditionHolofoil')),
                    '1st_edition': ('1st Edition', prices_src.get('1stEdition'))
                }
                def _hasv(v):
                    try:
                        if not isinstance(v, dict):
                            return v is not None and float(v) > 0
                        return any(float(v.get(k) or 0) > 0 for k in ("market","mid","low"))
                    except Exception:
                        return False

                with st.form(f"pk_form_{i}"):
                    # Build rows for each available variant
                    checks = {}
                    qtys = {}
                    for key, (label, val) in fmap.items():
                        if _hasv(val):
                            c1, c2, c3 = st.columns([4,1,2])
                            with c1:
                                default_on = True if (key == 'normal') else False
                                if isinstance(val, dict):
                                    mkt = float(val.get('market') or 0)
                                    mid = float(val.get('mid') or 0)
                                    low = float(val.get('low') or 0)
                                    price_line = f"${mkt:.2f}"
                                    details = []
                                    if mid: details.append(f"mid ${mid:.2f}")
                                    if low: details.append(f"low ${low:.2f}")
                                    if details:
                                        price_line = f"{price_line} ({', '.join(details)})"
                                    checks[key] = st.checkbox(f"{label} — {price_line}", value=default_on, key=f"pk_{key}_ck_{i}")
                                else:
                                    checks[key] = st.checkbox(f"{label} — ${float(val):.2f}", value=default_on, key=f"pk_{key}_ck_{i}")
                            with c2:
                                st.markdown("QTY")
                            with c3:
                                qtys[key] = st.number_input(" ", min_value=1, max_value=999, value=1, key=f"pk_{key}_qty_{i}", label_visibility='collapsed')

                    # Extra / Notes (now also holds Custom Variant)
                    with st.expander("Extra / Notes", expanded=False):
                        # Custom variant
                        cv1, cv2 = st.columns([2,2])
                        with cv1:
                            custom_variant = st.text_input("Custom Variant", value="", key=f"pk_cust_var_{i}", placeholder="e.g., Promo")
                        with cv2:
                            try:
                                custom_price = st.number_input("Custom Price (market)", min_value=0.0, step=0.01, value=0.0, key=f"pk_cust_price_{i}")
                            except Exception:
                                custom_price = 0.0
                        # Notes / flags
                        s_col1, s_col2 = st.columns([2,3])
                        with s_col1: signed_on = st.checkbox("Signed", value=False, key=f"pk_{i}_signed")
                        with s_col2: signed_txt = st.text_input("Artist / note", value="", key=f"pk_{i}_signed_txt", placeholder="Artist or note")
                        a_col1, a_col2 = st.columns([2,3])
                        with a_col1: altered_on = st.checkbox("Altered", value=False, key=f"pk_{i}_altered")
                        with a_col2: altered_txt = st.text_input("Artist / note", value="", key=f"pk_{i}_altered_txt", placeholder="Artist or note")
                        n_col1, n_col2 = st.columns([2,3])
                        with n_col1: notes_on = st.checkbox("Notes", value=False, key=f"pk_{i}_notes")
                        with n_col2: notes_txt = st.text_input("Notes", value="", key=f"pk_{i}_notes_txt", placeholder="Any notes")
                        paid_input = st.number_input("Paid (total)", min_value=0.0, step=0.01, value=0.0, key=f"pk_{i}_paid")
                        target_price_input = st.number_input("Target Price (watchlist)", min_value=0.0, step=0.01, value=0.0, key=f"pk_{i}_target_price")

                    # Actions under Extra/Notes
                    ac1, ac2 = st.columns(2)
                    with ac1:
                        submitted_add = st.form_submit_button("Add to Collection", use_container_width=True)
                    with ac2:
                        submitted_wl = st.form_submit_button("Add to Watchlist", use_container_width=True)

                        def _to_float_safe(x):
                            try:
                                return float(x)
                            except Exception:
                                try:
                                    return float(str(x).replace('$','').replace(',',''))
                                except Exception:
                                    return 0.0

                        if submitted_add or submitted_wl:
                            # Build variant selections
                            picks = []
                            for key, (label, val) in fmap.items():
                                if _hasv(val) and checks.get(key):
                                    # prefer market for price when dict provided
                                    price_val = 0.0
                                    if isinstance(val, dict):
                                        price_val = _to_float_safe(val.get('market'))
                                    else:
                                        price_val = _to_float_safe(val)
                                    picks.append((key, price_val, int(qtys.get(key, 1))))
                            if (custom_variant or '').strip() and _to_float_safe(custom_price) > 0:
                                picks.append((custom_variant.strip(), _to_float_safe(custom_price), 1))

                            if not picks:
                                st.warning("Select at least one variant to add.")
                            else:
                                if submitted_add:
                                    collection = st.session_state.get(SESSION_KEYS["collection"], [])
                                    before = len(collection)
                                    for vname, vprice, vqty in picks:
                                        entry = card.copy()
                                        entry['game'] = 'Pokémon'
                                        entry['variant'] = vname
                                        entry['price_usd'] = vprice
                                        entry['quantity'] = vqty
                                        entry['date_added'] = datetime.now().isoformat()
                                        if signed_on: entry['signed'] = (signed_txt or '').strip()
                                        if altered_on: entry['altered'] = (altered_txt or '').strip()
                                        if notes_on and (notes_txt or '').strip(): entry['notes'] = (notes_txt or '').strip()
                                        try: entry['paid'] = float(paid_input or 0.0)
                                        except Exception: entry['paid'] = 0.0
                                        # Merge or append
                                        dup_strategy = st.session_state.get('duplicate_strategy', 'merge')
                                        merged = False
                                        if dup_strategy == 'merge':
                                            for existing in collection:
                                                if (
                                                    existing.get('game') == entry.get('game') and
                                                    existing.get('name') == entry.get('name') and
                                                    (existing.get('set_code') or existing.get('set')) == (entry.get('set_code') or entry.get('set')) and
                                                    str(existing.get('card_number','')) == str(entry.get('card_number','')) and
                                                    existing.get('variant','') == entry.get('variant','')
                                                ):
                                                    try:
                                                        existing['quantity'] = int(existing.get('quantity', 0) or 0) + int(entry.get('quantity', 0) or 0)
                                                        existing['paid'] = float(existing.get('paid', 0.0) or 0.0) + float(entry.get('paid', 0.0) or 0.0)
                                                    except Exception:
                                                        pass
                                                    merged = True
                                                    break
                                        if not merged or dup_strategy != 'merge':
                                            collection.append(entry)
                                    st.session_state[SESSION_KEYS['collection']] = collection
                                    # Persist Pokémon-only file
                                    pkmn_cards = [c for c in collection if c.get('game') == 'Pokémon']
                                    if pkmn_cards:
                                        save_collection_to_csv(pkmn_cards, 'pokemon_collection.csv')
                                    try:
                                        st.toast(f"Added {len(picks)} entr{'y' if len(picks)==1 else 'ies'} to collection", icon="✅")
                                    except Exception:
                                        st.success("Added to collection")
                                if submitted_wl:
                                    watchlist = st.session_state.get('watchlist', [])
                                    for vname, vprice, vqty in picks:
                                        wentry = card.copy()
                                        wentry['game'] = 'Pokémon'
                                        wentry['variant'] = vname
                                        wentry['price_usd'] = vprice
                                        wentry['quantity'] = vqty
                                        wentry['date_added'] = datetime.now().isoformat()
                                        if signed_on: wentry['signed'] = (signed_txt or '').strip()
                                        if altered_on: wentry['altered'] = (altered_txt or '').strip()
                                        if notes_on and (notes_txt or '').strip(): wentry['notes'] = (notes_txt or '').strip()
                                        tp = 0.0
                                        try: tp = float(target_price_input or 0.0)
                                        except Exception: tp = 0.0
                                        wentry['target_price'] = tp
                                        # Merge by same key
                                        wmerged = False
                                        for existing in watchlist:
                                            if (
                                                existing.get('game') == wentry.get('game') and
                                                existing.get('name') == wentry.get('name') and
                                                (existing.get('set_code') or existing.get('set')) == (wentry.get('set_code') or wentry.get('set')) and
                                                str(existing.get('card_number','')) == str(wentry.get('card_number','')) and
                                                existing.get('variant','') == wentry.get('variant','')
                                            ):
                                                try:
                                                    existing['quantity'] = int(existing.get('quantity', 0) or 0) + int(wentry.get('quantity', 0) or 0)
                                                    if tp > 0: existing['target_price'] = tp
                                                except Exception:
                                                    pass
                                                wmerged = True
                                                break
                                        if not wmerged:
                                            watchlist.append(wentry)
                                    st.session_state['watchlist'] = watchlist
                                    save_watchlist_to_csv(watchlist, 'watchlist.csv')
                                    try:
                                        st.toast(f"Added {len(picks)} entr{'y' if len(picks)==1 else 'ies'} to watchlist", icon="⭐")
                                    except Exception:
                                        st.success("Added to watchlist")

def render_mtg_search_results(cards: List[Dict]):
    """Render MTG search results with image, details, price, variant selectors, and actions."""
    if not cards:
        st.info("No results to display.")
        return
    # Keep these results visible on subsequent reruns (e.g., when submitting inner forms)
    try:
        st.session_state["mtg_last_results"] = cards
        st.session_state["mtg_results_visible"] = True
    except Exception:
        pass
    # NOTE: Keys must be stable across reruns for form_submit_button to register.
    # Avoid per-render counters; derive keys from stable card identity + fixed grid position.
    # Scoped CSS for compact, dark MTG card blocks
    st.markdown(
        """
        <style>
        .mtg-card { background-color:#2b2b2b; border:1px solid #3a3a3a; border-radius:8px; padding:10px; }
        .mtg-card .setline { font-size: 0.92rem; color: #d0d0d0; margin: 2px 0 8px; display:flex; align-items:center; gap:6px; }
        .mtg-card [data-testid="stNumberInput"] label { font-size: 0.85rem; color:#bbb; }
        .mtg-card [data-testid="stNumberInput"] input { height: 34px; padding: 2px 6px; }
        .mtg-card [data-testid="stTextInput"] input { height: 34px; padding: 2px 8px; font-size: 0.92rem; }
        .mtg-card [data-testid="stForm"] button { height: 36px; }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Inject lightweight CSS to darken card containers
    st.markdown(
        """
        <style>
        /* Dark background for bordered containers in MTG results grid */
        div[data-testid="stContainer"][data-baseweb="block"] > div {
            background-color: #2b2b2b11; /* subtle default for non-cards */
        }
        /* More specific: immediate bordered containers inside columns */
        div[data-testid="stHorizontalBlock"] > div > div[data-testid="stVerticalBlock"] > div[data-testid="stContainer"] {
            background-color: #2b2b2b;
            border-radius: 8px;
            padding: 12px;
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
    # Optional debug banner
    try:
        if st.session_state.get(SESSION_KEYS["debug_mode"], False):
            st.info(
                f"DEBUG • mtg_results_visible={st.session_state.get('mtg_results_visible')} • "
                f"last_add={st.session_state.get('debug_last_add_event')}"
            )
    except Exception:
        pass
    # Render in rows of 3 columns
    for row_start in range(0, len(cards), 3):
        row_cards = cards[row_start:row_start+3]
        row_cols = st.columns(3)
        for idx, (col, card) in enumerate(zip(row_cols, row_cards)):
            stable_id = f"{card.get('name','')}|{card.get('set','')}|{card.get('card_number','')}".lower().strip()
            key_prefix = f"mtg_{row_start}_{idx}_{hash(stable_id)}"
            with col:
                st.markdown("<div class='mtg-card'>", unsafe_allow_html=True)
                with st.container(border=False):
                    cols = st.columns([1, 1.8])
                    with cols[0]:
                        img_url = card.get('image_url') or "https://via.placeholder.com/300x420"
                        st.image(img_url, width=200)
                    with cols[1]:
                        st.subheader(card.get('name', 'Unknown'))
                        # Show Set line (icon + name + card # + year) directly under the card name
                        set_name_disp = card.get('set', '')
                        set_code = (card.get('set_code') or '').lower() if card.get('set_code') else ''
                        if not set_code and card.get('link') and 'scryfall.com' in str(card.get('link')):
                            try:
                                import re as _re
                                m = _re.search(r"/sets/([a-z0-9]+)/?", str(card.get('link')))
                                if m:
                                    set_code = m.group(1)
                            except Exception:
                                pass
                        cno = str(card.get('card_number') or '').strip()
                        year_txt = str(card.get('year') or '').strip()
                        meta_txt = f"# {cno}" if cno else "# —"
                        if year_txt:
                            meta_txt = f"{meta_txt} • {year_txt}"
                        if set_code:
                            icon_url = f"https://svgs.scryfall.io/sets/{set_code}.svg"
                            st.markdown(
                                f"<span style='display:flex;align-items:center;gap:6px;'>"
                                f"<img src='{icon_url}' style='height:18px;width:18px;'>"
                                f"<span>{set_name_disp} • {meta_txt}</span>"
                                f"</span>",
                                unsafe_allow_html=True
                            )
                        else:
                            st.markdown(f"<span class='setline'>{set_name_disp} • {meta_txt}</span>", unsafe_allow_html=True)

                        # No top-level value line; values are shown per-variant

                        # Group all interactive controls into a form to avoid reruns on each change
                        with st.form(f"{key_prefix}_form"):
                            # Variant selectors (non-collapsible)
                            v_nonfoil = card.get('price_usd')
                            v_foil = card.get('price_usd_foil')
                            # Only show lines that exist
                            def _has_value(x):
                                return x is not None and str(x).strip().lower() != 'none'
                            # Respect availability flags from Scryfall; fall back to price presence when flags missing
                            show_nonfoil = bool(card.get('has_nonfoil', False)) or (not ('has_nonfoil' in card) and _has_value(v_nonfoil))
                            show_foil = bool(card.get('has_foil', False)) or (not ('has_foil' in card) and _has_value(v_foil))
                            # Helper usable by both Add to Collection and Add to Watchlist handlers
                            def _to_float_safe(x):
                                try:
                                    return float(x)
                                except Exception:
                                    try:
                                        return float(str(x).replace('$','').replace(',',''))
                                    except Exception:
                                        return 0.0
                            nf_checked = False
                            f_checked = False
                            if show_nonfoil:
                                # Align QTY label to the left of the input on the same row
                                nf_c1, nf_c2, nf_c3 = st.columns([4, 1, 2])
                                with nf_c1:
                                    nf_price_txt = f"${float(v_nonfoil):.2f}" if isinstance(v_nonfoil, (int, float)) and v_nonfoil else "-"
                                    nf_checked = st.checkbox(f"Non Foil — {nf_price_txt}", value=True, key=f"{key_prefix}_nonfoil_ck")
                                with nf_c2:
                                    st.markdown("QTY")
                                with nf_c3:
                                    nf_qty = st.number_input(" ", min_value=1, max_value=999, value=1, key=f"{key_prefix}_nonfoil_qty", label_visibility='collapsed')
                            if show_foil:
                                f_c1, f_c2, f_c3 = st.columns([4, 1, 2])
                                with f_c1:
                                    foil_default = True if (show_foil and not show_nonfoil) else False
                                    f_price_txt = f"${float(v_foil):.2f}" if isinstance(v_foil, (int, float)) and v_foil else "-"
                                    f_checked = st.checkbox(f"Foil — {f_price_txt}", value=foil_default, key=f"{key_prefix}_foil_ck")
                                with f_c2:
                                    st.markdown("QTY")
                                with f_c3:
                                    f_qty = st.number_input("  ", min_value=1, max_value=999, value=1, key=f"{key_prefix}_foil_qty", label_visibility='collapsed')

                            # Extra / Notes (collapsible): Signed, Altered, Notes
                            artist = (card.get('artist') or '').strip()
                            # Defaults so submission works even if expander stays closed
                            signed_on = False
                            signed_txt = artist
                            altered_on = False
                            altered_txt = artist
                            notes_on = False
                            notes_txt = ""
                            with st.expander("Extra / Notes", expanded=False):
                                s_col1, s_col2 = st.columns([2, 3])
                                with s_col1:
                                    signed_on = st.checkbox("Signed", value=False, key=f"{key_prefix}_signed")
                                with s_col2:
                                    signed_txt = st.text_input("Artist / note", value=artist, key=f"{key_prefix}_signed_txt", placeholder="Artist or note")
                                a_col1, a_col2 = st.columns([2, 3])
                                with a_col1:
                                    altered_on = st.checkbox("Altered", value=False, key=f"{key_prefix}_altered")
                                with a_col2:
                                    altered_txt = st.text_input("Artist / note", value=artist, key=f"{key_prefix}_altered_txt", placeholder="Artist or note")
                                n_col1, n_col2 = st.columns([2, 3])
                                with n_col1:
                                    notes_on = st.checkbox("Notes", value=False, key=f"{key_prefix}_notes")
                                with n_col2:
                                    notes_txt = st.text_input("Notes", value="", key=f"{key_prefix}_notes_txt", placeholder="Any notes")
                                # Paid amount for this add (total)
                                paid_input = st.number_input("Paid (total)", min_value=0.0, step=0.01, value=0.0, key=f"{key_prefix}_paid")
                                # Target Price (for Watchlist)
                                target_price_input = st.number_input("Target Price (watchlist)", min_value=0.0, step=0.01, value=0.0, key=f"{key_prefix}_target_price")

                            # Actions (buttons within form)
                            ac1, ac2 = st.columns(2)
                            with ac1:
                                submitted_add = st.form_submit_button("Add to Collection", use_container_width=True)
                            with ac2:
                                submitted_wl = st.form_submit_button("Add to Watchlist", use_container_width=True)

                            if submitted_add:
                                # Ensure results remain visible after this submission
                                st.session_state["mtg_results_visible"] = True
                                # Mark debug event for visibility
                                try:
                                    st.session_state["debug_last_add_event"] = {
                                        "ts": datetime.now().isoformat(timespec='seconds'),
                                        "card": card.get('name', ''),
                                        "set": card.get('set', ''),
                                        "sel_nonfoil": bool(show_nonfoil and nf_checked),
                                        "sel_foil": bool(show_foil and f_checked)
                                    }
                                    st.session_state['mtg_add_ping'] = st.session_state["debug_last_add_event"]["ts"]
                                    print(f"🔔 mtg_add_ping @ {st.session_state['mtg_add_ping']}")
                                    st.write(
                                        f"🔧 DEBUG: submitted_add=True for {card.get('name','')} • "
                                        f"NF={bool(show_nonfoil and nf_checked)} • F={bool(show_foil and f_checked)}"
                                    )
                                except Exception:
                                    pass
                                collection = st.session_state.get(SESSION_KEYS["collection"], [])
                                to_add = []
                                def _to_float_safe(x):
                                    try:
                                        return float(x)
                                    except Exception:
                                        try:
                                            return float(str(x).replace('$','').replace(',',''))
                                        except Exception:
                                            return 0.0
                                if show_nonfoil and nf_checked:
                                    to_add.append(("nonfoil", _to_float_safe(v_nonfoil), int(nf_qty)))
                                if show_foil and f_checked:
                                    to_add.append(("foil", _to_float_safe(v_foil), int(f_qty)))
                                if not to_add:
                                    st.warning("Select at least one variant to add.")
                                else:
                                    try:
                                        before_count = len(collection)
                                        for vname, vprice, vqty in to_add:
                                            entry = card.copy()
                                            # Ensure required fields exist
                                            entry['game'] = entry.get('game') or 'Magic: The Gathering'
                                            entry['name'] = entry.get('name', '')
                                            entry['set'] = entry.get('set', '')
                                            entry['link'] = entry.get('link', '')
                                            entry['image_url'] = entry.get('image_url', '')
                                            entry['variant'] = vname
                                            entry['price_usd'] = vprice
                                            entry['quantity'] = vqty
                                            entry['date_added'] = datetime.now().isoformat()
                                            # signed/altered/notes
                                            if signed_on:
                                                entry['signed'] = (signed_txt or artist or '').strip()
                                            if altered_on:
                                                entry['altered'] = (altered_txt or artist or '').strip()
                                            if 'notes_on' in locals() and notes_on and (notes_txt or '').strip():
                                                entry['notes'] = (notes_txt or '').strip()
                                            # Paid total for this add action
                                            try:
                                                entry['paid'] = float(paid_input or 0.0)
                                            except Exception:
                                                entry['paid'] = 0.0
                                            # Duplicate handling according to settings
                                            dup_strategy = st.session_state.get('duplicate_strategy', 'merge')
                                            merged = False
                                            if dup_strategy == 'merge':
                                                for existing in collection:
                                                    if (
                                                        existing.get('game') == entry.get('game') and
                                                        existing.get('name') == entry.get('name') and
                                                        existing.get('set') == entry.get('set') and
                                                        str(existing.get('card_number','')) == str(entry.get('card_number','')) and
                                                        existing.get('variant','') == entry.get('variant','')
                                                    ):
                                                        try:
                                                            existing['quantity'] = int(existing.get('quantity', 0) or 0) + int(entry.get('quantity', 0) or 0)
                                                            # accumulate paid totals when merging
                                                            existing['paid'] = float(existing.get('paid', 0.0) or 0.0) + float(entry.get('paid', 0.0) or 0.0)
                                                        except Exception:
                                                            pass
                                                        merged = True
                                                        break
                                            if dup_strategy != 'merge' or not merged:
                                                collection.append(entry)
                                        after_count = len(collection)
                                        st.session_state[SESSION_KEYS["collection"]] = collection
                                        ok1 = save_collection_to_csv(collection, "unified_collection.csv")
                                        mtg_cards = [c for c in collection if c.get("game") == "Magic: The Gathering"]
                                        ok2 = True
                                        if mtg_cards:
                                            ok2 = save_collection_to_csv(mtg_cards, "mtg_collection.csv")
                                        added_count = len(to_add)
                                        try:
                                            print(f"🟢 AddToCollection: before={before_count}, added={added_count}, after={after_count}")
                                        except Exception:
                                            pass
                                        try:
                                            st.toast(f"Added {added_count} entr{'y' if added_count==1 else 'ies'} to collection", icon="✅")
                                        except Exception:
                                            st.success(f"Added {added_count} to collection")
                                        if not (ok1 and ok2):
                                            st.error("Saved to CSV failed. Check console for details.")
                                        else:
                                            try:
                                                coll_dir = get_collections_dir()
                                                unified_p = os.path.join(coll_dir, 'unified_collection.csv')
                                                mtg_p = os.path.join(coll_dir, 'mtg_collection.csv')
                                                # Read back counts for verification
                                                def _count_csv_rows(p):
                                                    try:
                                                        if os.path.exists(p):
                                                            with open(p, 'r', encoding='utf-8') as f:
                                                                return sum(1 for _ in f) - 1  # minus header
                                                    except Exception:
                                                        return -1
                                                    return 0
                                                u_rows = _count_csv_rows(unified_p)
                                                m_rows = _count_csv_rows(mtg_p)
                                                st.caption(f"Saved to: unified({u_rows} rows), mtg({m_rows} rows) • Session total: {len(collection)}")
                                                # Quick navigation to Collection view for this set
                                                nav_key = f"view_coll_{key_prefix}"
                                                if st.button("View in Collection", key=nav_key, use_container_width=True):
                                                    st.session_state[SESSION_KEYS["show_collection_view"]] = True
                                                    st.session_state[SESSION_KEYS["show_sets_view"]] = False
                                                    st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                                                    # Pre-filter to this set if possible
                                                    st.session_state['coll_set_filter'] = f"{entry.get('year','')} {entry.get('set','')}".strip()
                                                    st.rerun()
                                            except Exception:
                                                pass
                                    except Exception as e:
                                        st.error(f"Failed to add to collection: {e}")
                            if submitted_wl:
                                # Watchlist parity: add selected variants with qty and notes
                                watchlist = st.session_state.get('watchlist', [])
                                wl_to_add = []
                                if show_nonfoil and nf_checked:
                                    wl_to_add.append(("nonfoil", _to_float_safe(v_nonfoil), int(nf_qty)))
                                if show_foil and f_checked:
                                    wl_to_add.append(("foil", _to_float_safe(v_foil), int(f_qty)))
                                if not wl_to_add:
                                    st.warning("Select at least one variant to add to watchlist.")
                                else:
                                    try:
                                        for vname, vprice, vqty in wl_to_add:
                                            wentry = card.copy()
                                            wentry['game'] = wentry.get('game') or 'Magic: The Gathering'
                                            wentry['variant'] = vname
                                            wentry['price_usd'] = vprice
                                            wentry['quantity'] = vqty
                                            wentry['date_added'] = datetime.now().isoformat()
                                            if signed_on:
                                                wentry['signed'] = (signed_txt or artist or '').strip()
                                            if altered_on:
                                                wentry['altered'] = (altered_txt or artist or '').strip()
                                            if 'notes_on' in locals() and notes_on and (notes_txt or '').strip():
                                                wentry['notes'] = (notes_txt or '').strip()
                                            # Target price from input
                                            try:
                                                wentry['target_price'] = float(target_price_input or 0.0)
                                            except Exception:
                                                wentry['target_price'] = 0.0
                                            # Merge by same keys in watchlist too
                                            wmerged = False
                                            for existing in watchlist:
                                                if (
                                                    existing.get('game') == wentry.get('game') and
                                                    existing.get('name') == wentry.get('name') and
                                                    existing.get('set') == wentry.get('set') and
                                                    str(existing.get('card_number','')) == str(wentry.get('card_number','')) and
                                                    existing.get('variant','') == wentry.get('variant','')
                                                ):
                                                    try:
                                                        existing['quantity'] = int(existing.get('quantity', 0) or 0) + int(wentry.get('quantity', 0) or 0)
                                                        # if a positive target price is provided, update it
                                                        tp_new = float(wentry.get('target_price', 0.0) or 0.0)
                                                        if tp_new > 0:
                                                            existing['target_price'] = tp_new
                                                    except Exception:
                                                        pass
                                                    wmerged = True
                                                    break
                                            if not wmerged:
                                                watchlist.append(wentry)
                                        st.session_state['watchlist'] = watchlist
                                        okw = save_watchlist_to_csv(watchlist, 'watchlist.csv')
                                        try:
                                            st.toast(f"Added {len(wl_to_add)} entr{'y' if len(wl_to_add)==1 else 'ies'} to watchlist", icon="⭐")
                                        except Exception:
                                            st.success("Added to watchlist!")
                                        if not okw:
                                            st.error("Saving watchlist to CSV failed.")
                                    except Exception as e:
                                        st.error(f"Failed to add to watchlist: {e}")
                st.markdown("</div>", unsafe_allow_html=True)

def search_sportscard_database(player_name: str, year: str = "", set_name: str = "", card_number: str = "") -> Tuple[List[Dict], int, int, str]:
    """Search SportsCardDatabase.com for baseball cards"""
    try:
        print(f"🔍 Searching SportsCardDatabase for: {player_name}")
        print(f"📋 Filters - Year: '{year}', Set: '{set_name}', Card #: '{card_number}'")
        
        # For now, return mock data
        cards = create_mock_baseball_cards(player_name, year, "", set_name, card_number, "SportsCardDatabase.com")
        return cards, len(cards), len(cards), "SportsCardDatabase.com"
        
    except Exception as e:
        print(f"❌ SportsCardDatabase Error: {e}")
        return [], 0, 0, f"SportsCardDatabase Error: {str(e)}"

def render_clickable_image(img_url: str, width: int = CARD_IMAGE_WIDTH):
    """Render a clickable image"""
    if img_url:
        st.image(img_url, width=width)
    else:
        st.image("https://via.placeholder.com/200x280", width=width)

def render_collection_view():
    """Render the collection view with header selector and primary tabs"""
    # Header with inline collection selector
    head_l, head_r = st.columns([3, 2])
    with head_l:
        st.title("💳 My Collection")
        st.caption("Manage your personal card collection")
        try:
            _owner_badge = st.session_state.get('current_owner_label') or st.session_state.get('default_owner_label')
            if _owner_badge:
                st.caption(f"Owner: {_owner_badge}")
            _set_badge = _get_active_profile_for_owner_label(_owner_badge) if _owner_badge else 'default'
            if _set_badge and _set_badge != 'default':
                st.caption(f"Collection Set: {_set_badge}")
        except Exception:
            pass
    
    collection_all = st.session_state.get(SESSION_KEYS["collection"], [])
    if not collection_all:
        st.info("📝 This owner's collection is empty. You can add cards or switch owners from the selector.")
        st.button("🔍 Start Searching")
    
    with head_r:
        games = ["All", "Magic: The Gathering", "Pokémon", "Baseball Cards"]
        # Persist selected scope so reruns keep the same view (e.g., Magic)
        try:
            default_idx = games.index(st.session_state.get('collection_scope', 'All'))
        except Exception:
            default_idx = 0
        selected_scope = st.selectbox("Collection", games, index=default_idx, key='collection_scope', help="Choose which collection to view")
    
    # Scope filter
    if selected_scope == "All":
        collection = collection_all
    else:
        collection = [c for c in collection_all if c.get("game") == selected_scope]
    
    # Quick stats row
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_cards = sum(card.get("quantity", 1) for card in collection)
        st.metric("Total Cards", total_cards)
    with col2:
        unique_cards = len(collection)
        st.metric("Unique Cards", unique_cards)
    with col3:
        unique_sets = len(set(f"{card.get('year', '')} {card.get('set', '')}" for card in collection))
        st.metric("Unique Sets", unique_sets)
    with col4:
        total_value = sum(card.get("price_usd", 0) * card.get("quantity", 1) for card in collection)
        st.metric("Total Value", f"${total_value:.2f}")
    
    st.divider()
    
    # Primary tabs in order: Collection, Gallery View, Investment, Watchlist, Import/Export, Collection Management
    tab_coll, tab_gallery, tab_invest, tab_watch, tab_io, tab_manage = st.tabs(["🗂️ Collection", "🖼️ Gallery View", "📈 Investment", "⭐ Watchlist", "⬇️⬆️ Import / Export", "🧭 Collection Management"])
    
    with tab_coll:
        render_collection_tab(collection)
    with tab_gallery:
        render_gallery_view_tab(collection)
    with tab_invest:
        render_investment_tab(collection)
    with tab_watch:
        render_watchlist_tab()
    with tab_io:
        render_import_export_tab()
    with tab_manage:
        render_collection_management_tab()

def _sanitize_owner_id(name: str) -> str:
    import re as _re
    return _re.sub(r"[^a-z0-9]+", "-", (name or "").strip().lower()).strip("-")

def _owner_folder_label(name: str) -> str:
    base = (name or "").strip()
    if not base:
        return ""
    # Simple possessive label (e.g., John -> Johns Collection)
    return f"{base}" + ("'" if base.endswith("s") else "s") + " Collection"

def _owner_from_folder_label(label: str) -> str:
    """Derive owner name from folder label like 'Johns Collection' or "Chris' Collection"."""
    lab = (label or '').strip()
    if not lab or lab.lower() == 'default':
        return ''
    if lab.endswith(' Collection'):
        base = lab[:-len(' Collection')]
    else:
        base = lab
    if base.endswith("'s"):
        return base[:-2]
    if base.endswith('s'):
        return base[:-1]
    return base

def render_collection_management_tab():
    """Owner/secondary collection management. UI only; does not alter load/save behavior."""
    st.subheader("Manage Owners and Secondary Collections")
    st.caption("Create owner folders under collections/ to keep separate CSVs per owner. This does not change current save/load behavior yet.")

    coll_dir = get_collections_dir()
    # Existing owner folders: any subdirectories under collections/
    existing = []
    try:
        for entry in os.listdir(coll_dir):
            p = os.path.join(coll_dir, entry)
            if os.path.isdir(p):
                existing.append(entry)
    except Exception:
        pass

    # Default owner selection (must be an existing owner)
    if existing:
        try:
            def_owner = st.session_state.get('default_owner_label')
        except Exception:
            def_owner = None
        try:
            def_idx = existing.index(def_owner) if def_owner in existing else 0
        except Exception:
            def_idx = 0
        prev_default = st.session_state.get('_prev_default_owner')
        new_default = st.selectbox(
            "Default Owner",
            existing,
            index=def_idx,
            key='default_owner_label',
            help="Owner used by default on app load"
        )
        # Immediate feedback when default owner changes
        if new_default != prev_default:
            st.session_state['_prev_default_owner'] = new_default
            st.success(f"Default owner set to {new_default}")
        # Optional explicit save button for reassurance (no additional persistence layer yet)
        if st.button("Save Default Owner", key="btn_save_default_owner"):
            ok = save_owner_prefs({'default_owner_label': st.session_state.get('default_owner_label')})
            if ok:
                st.success(f"Default owner saved: {st.session_state.get('default_owner_label')}")
            else:
                st.error("Could not save default owner to disk.")
    else:
        st.info("Set a Default Owner after creating at least one owner.")

    if existing:
        st.write("Existing owner folders:")
        st.write("\n".join(f"- {e}" for e in sorted(existing)))
    else:
        st.info("No owner folders found yet.")

    st.divider()
    st.write("Add a new owner")
    col_a, col_b = st.columns([2,1])
    with col_a:
        owner_name = st.text_input("Owner name", placeholder="e.g., John", key="owner_new_name")
    with col_b:
        if st.button("➕ Add Owner", key="btn_add_owner"):
            name = (owner_name or "").strip()
            if not name:
                st.warning("Please enter an owner name.")
            else:
                folder_label = _owner_folder_label(name)
                folder_path = os.path.join(coll_dir, folder_label)
                try:
                    os.makedirs(folder_path, exist_ok=True)
                    st.success(f"Created folder: {folder_label}")
                except Exception as e:
                    st.error(f"Could not create folder: {e}")
                # Create blank CSV files for this owner (headers only)
                owner_id = _sanitize_owner_id(name)
                rel_mtg = os.path.join(folder_label, f"{owner_id}-mtg_collection.csv")
                rel_pkmn = os.path.join(folder_label, f"{owner_id}-pokemon_collection.csv")
                rel_uni = os.path.join(folder_label, f"{owner_id}-unified_collection.csv")
                rel_wl = os.path.join(folder_label, f"{owner_id}-watchlist.csv")
                try:
                    save_collection_to_csv([], rel_uni)
                    save_collection_to_csv([], rel_mtg)
                    save_collection_to_csv([], rel_pkmn)
                    save_watchlist_to_csv([], rel_wl)
                except Exception:
                    pass
                # Show created/expected file naming convention
                st.caption("Owner CSVs initialized (blank):")
                st.code("\n".join([
                    os.path.join(folder_path, f"{owner_id}-mtg_collection.csv"),
                    os.path.join(folder_path, f"{owner_id}-pokemon_collection.csv"),
                    os.path.join(folder_path, f"{owner_id}-unified_collection.csv"),
                    os.path.join(folder_path, f"{owner_id}-watchlist.csv"),
                ]))

    st.divider()
    # Manage collection sets (profiles) per owner
    st.subheader("Collection Sets (per owner)")
    if existing:
        manage_owner = st.selectbox("Owner to manage", existing, index=0, key="manage_owner_for_profiles")
        # Detect existing profiles by scanning unified files {oid}-*-unified_collection.csv
        coll_dir = get_collections_dir()
        raw_owner = _owner_from_folder_label(manage_owner)
        oid = _sanitize_owner_id(raw_owner)
        profiles = set()
        try:
            for fn in os.listdir(os.path.join(coll_dir, manage_owner)):
                if fn.startswith(f"{oid}-") and fn.endswith("-unified_collection.csv"):
                    middle = fn[len(oid)+1: -len("-unified_collection.csv")]
                    if middle:
                        profiles.add(middle)
                if fn == f"{oid}-unified_collection.csv":
                    profiles.add('default')
        except Exception:
            pass
        if not profiles:
            profiles = {'default'}
        current_profile = _get_active_profile_for_owner_label(manage_owner)
        try:
            prof_index = list(sorted(profiles)).index(current_profile) if current_profile in profiles else 0
        except Exception:
            prof_index = 0
        new_profile = st.text_input("New collection set name", placeholder="e.g., trades, sealed, extras", key="new_profile_name")
        c1, c2 = st.columns([1,1])
        with c1:
            if st.button("➕ Add Collection Set", key="btn_add_profile"):
                pname = _sanitize_profile_id(new_profile)
                if not pname or pname == 'default':
                    st.warning("Please provide a non-default set name.")
                else:
                    # Create blank CSVs for this profile
                    rel_mtg = os.path.join(manage_owner, f"{oid}-{pname}-mtg_collection.csv")
                    rel_pkmn = os.path.join(manage_owner, f"{oid}-{pname}-pokemon_collection.csv")
                    rel_uni = os.path.join(manage_owner, f"{oid}-{pname}-unified_collection.csv")
                    rel_wl = os.path.join(manage_owner, f"{oid}-{pname}-watchlist.csv")
                    try:
                        save_collection_to_csv([], rel_uni)
                        save_collection_to_csv([], rel_mtg)
                        save_collection_to_csv([], rel_pkmn)
                        save_watchlist_to_csv([], rel_wl)
                        st.success(f"Created collection set '{pname}' for {manage_owner}")
                    except Exception as e:
                        st.error(f"Failed to create set: {e}")
        with c2:
            sel_profile = st.selectbox("Active collection set", list(sorted(profiles)), index=prof_index, key="active_profile_select")
            if st.button("Set Active", key="btn_set_active_profile"):
                _set_active_profile_for_owner_label(manage_owner, _sanitize_profile_id(sel_profile))
                st.success(f"Active set for {manage_owner} is now '{_sanitize_profile_id(sel_profile)}'")
                # If current owner equals this manage_owner, reload and rerun
                if st.session_state.get('current_owner_label') == manage_owner:
                    st.session_state[SESSION_KEYS["collection"]] = load_csv_collections()
                    st.session_state["watchlist"] = load_watchlist_from_csv()
                    st.rerun()

    st.divider()
    # Migration tool: Copy from legacy default CSVs into a chosen owner
    with st.expander("Copy from legacy Default CSVs to an Owner"):
        if not existing:
            st.info("Create an owner first.")
        else:
            tgt_owner = st.selectbox("Target Owner", existing, key="migrate_target_owner")
            if st.button("Copy now", key="btn_copy_legacy"):
                msg = _copy_legacy_default_to_owner(tgt_owner)
                if msg.startswith("✅"):
                    st.success(msg)
                elif msg.startswith("ℹ️"):
                    st.info(msg)
                else:
                    st.error(msg)

def render_help_view():
    """Help hub with tabbed guidance for core app areas."""
    st.title("❓ Help")
    st.caption("Quick guides and tips for using Collectibles Manager")
    tabs = st.tabs([
        "📌 Overview",
        "👤 Owners & Sets",
        "⬇️⬆️ Import/Export",
        "🗂️ Collection",
        "⭐ Watchlist",
        "⚙️ Settings",
        "🧰 Troubleshooting"
    ])
    with tabs[0]:
        st.subheader("Overview")
        st.markdown("""
        - Use the sidebar to pick an `Owner` and a `Collection Set`. All actions read/write to that context.
        - Home lets you search and add cards to your active collection.
        - My Collection shows your data with filters, totals, and actions.
        - Import/Export supports CSV and a one-click ZIP export.
        - Collection Management: create owners, set default, migrate legacy, manage sets, delete owners.
        """)
    with tabs[1]:
        st.subheader("Owners & Collection Sets")
        st.markdown("""
        - `Owner` lives in the sidebar and applies globally.
        - Each owner can have multiple `Collection Sets` (e.g., default, trades, sealed).
        - Switch sets from the sidebar or manage them in `Collection Management`.
        - Files are saved as `{ownerid}-{[set-]}<type>.csv` under the owner's folder.
        """)
    with tabs[2]:
        st.subheader("Import / Export")
        st.markdown("""
        - Export: download MTG/Pokémon/Watchlist CSVs and a virtual Unified CSV (combined), or all as ZIP.
        - Import: upload CSV and choose `Target` (MTG, Pokémon, or Watchlist) and `Mode` (Replace/Append).
        - Duplicate handling per import: `Use Settings`, `Force Merge`, or `Force Separate`.
        - Merge keys:
          - Collection: (game, name, set_code-or-set, card_number, variant)
          - Watchlist: (game, name, set, variant)
        - On merge, `quantity` is summed. For collections, `paid` is summed.
        - Templates section provides empty CSV headers.
        """)
        st.markdown("**Required fields for import (recommended minimum):**")
        st.markdown("- Card Name\n- Set Code or Set Name\n- Quantity")
        st.divider()
        st.markdown("**Download import templates:**")
        import io as _io
        def _tmpl_bytes(headers):
            s = _io.StringIO()
            w = csv.DictWriter(s, fieldnames=headers)
            w.writeheader()
            return s.getvalue().encode('utf-8')
        # Targeted import templates only
        mtg_import_headers = ['name','set','set_code','card_number','quantity','foil','paid','signed','altered','notes']
        # Pokémon-specific template with variant flags and minimal required fields
        pkmn_import_headers = [
            'name','number','quantity',
            'normal','unlimited','holofoil','unlimited_holofoil','reverse_holofoil','first_edition','first_edition_holo',
            'notes'
        ]
        wl_import_headers = ['name','set','quantity','target_price','notes']
        c1, c2, c3 = st.columns(3)
        with c1:
            st.download_button("MTG Import Template", data=_tmpl_bytes(mtg_import_headers), file_name="mtg_import_template.csv", mime="text/csv")
        with c2:
            st.download_button("Pokémon Import Template", data=_tmpl_bytes(pkmn_import_headers), file_name="pokemon_import_template.csv", mime="text/csv")
        with c3:
            st.download_button("Watchlist Import Template", data=_tmpl_bytes(wl_import_headers), file_name="watchlist_import_template.csv", mime="text/csv")
        st.markdown("""
        **Template Guide**
        - **Quantity**: if blank or missing, defaults to 1.
        - **Pokémon variant flags** (normal, unlimited, holofoil, unlimited_holofoil, reverse_holofoil, first_edition, first_edition_holo):
          - Accepts any of: y, yes, true, 1 (case-insensitive) to mark a variant.
          - If none are set, the import defaults to Normal.
          - If multiple variants are set on the same row, multiple entries will be created (one per variant), each using the same quantity.
        - **Number field**: Pokémon accepts `number` as the card number column; MTG uses `card_number`/`collector_number`.
        - **Ambiguities**: If the same name+number exists in multiple sets, the row is queued for review after the import completes.
        """)
    with tabs[3]:
        st.subheader("Collection")
        st.markdown("""
        - Filter by game scope using the header selector.
        - Add cards from search (Home) using `Add to Collection`.
        - Edit notes, quantities, and see totals. Empty collections still allow switching owners/sets.
        """)
    with tabs[4]:
        st.subheader("Watchlist")
        st.markdown("""
        - Track cards of interest with optional `target_price`.
        - Import/Export watchlist just like collections. On merge, quantities add up.
        """)
    with tabs[5]:
        st.subheader("Settings")
        st.markdown("""
        - Configure data sources (eBay, Scryfall, Pokémon TCG, etc.).
        - Set `Duplicate Handling` (Merge or Separate) used by default on Append.
        """)
    with tabs[6]:
        st.subheader("Troubleshooting")
        st.markdown("""
        - If switching owner/set doesn't reflect, try switching again; the app auto-reloads relevant CSVs.
        - For import errors, verify CSV headers via the Templates and ensure UTF-8 encoding.
        - Default owner and active sets are stored under `collections/owner_settings.json`.
        - You can enable `🐛 Debug Mode` in the sidebar to see extra diagnostics.
        """)

def render_import_export_tab():
    """Import/Export data for the active owner (unified/mtg/pokemon/watchlist)."""
    # Import first
    owner_label = st.session_state.get('current_owner_label') or st.session_state.get('default_owner_label')
    st.caption(f"Active owner: {owner_label or '—'}")
    st.subheader("Import")
    st.caption("Upload a CSV to replace or append to the active owner's data")
    # Show last import summary after reruns
    if st.session_state.get('last_import_summary'):
        st.info(st.session_state.get('last_import_summary'))
    # Load persisted ambiguities for this owner if present and not already in session
    try:
        owner_id = _sanitize_owner_id(owner_label or '')
        amb_path = os.path.join(get_collections_dir(), f"{owner_id}-import-ambiguities.json")
        if not st.session_state.get('import_ambiguities') and os.path.exists(amb_path):
            with open(amb_path, 'r', encoding='utf-8') as f:
                st.session_state['import_ambiguities'] = json.load(f) or []
    except Exception:
        pass
    # Ambiguity Review panel (if present from a prior import)
    if st.session_state.get('import_ambiguities'):
        amb = st.session_state.get('import_ambiguities') or []
        st.warning(f"{len(amb)} ambiguous row(s) require your review.")
        st.subheader("Ambiguity Review")
        to_remove = []
        # Batch resolve button (top)
        if amb:
            if st.button("Resolve All Selected", key="amb_resolve_all"):
                committed = 0
                for idx in range(len(amb)):
                    try:
                        item = amb[idx]
                        cands = item.get('candidates') or []
                        if not cands:
                            continue
                        sel_idx = st.session_state.get(f"amb_sel_{idx}")
                        if sel_idx is None:
                            continue
                        qty = int(st.session_state.get(f"amb_qty_{idx}") or int(item.get('quantity') or 1))
                        variant = item.get('variant') or 'Normal'
                        sel = cands[sel_idx]
                        entry = {
                            'game': item.get('game',''),
                            'name': sel.get('name') or item.get('name',''),
                            'set': sel.get('set',''),
                            'set_code': sel.get('set_code',''),
                            'card_number': sel.get('card_number',''),
                            'year': sel.get('year',''),
                            'image_url': sel.get('image_url',''),
                            'link': sel.get('link',''),
                            'price_usd': sel.get('price_usd', 0.0),
                            'price_usd_foil': sel.get('price_usd_foil', 0.0),
                            'price_usd_etched': sel.get('price_usd_etched', 0.0),
                            'quantity': int(qty or 1),
                            'variant': variant or 'Normal',
                            'paid': 0.0,
                            'signed': '',
                            'altered': '',
                            'notes': item.get('notes',''),
                            'date_added': datetime.now().isoformat()
                        }
                        dest_file = 'mtg_collection.csv' if entry['game'] == 'Magic: The Gathering' else 'pokemon_collection.csv'
                        current = load_csv_collections()
                        # Merge behavior respects duplicate strategy: default merge quantities
                        def _k(c):
                            kset = c.get('set_code') or c.get('set','')
                            return (c.get('game',''), c.get('name',''), kset, str(c.get('card_number','')), c.get('variant',''))
                        game_only = [c for c in current if c.get('game') == entry['game']]
                        acc = {_k(c): dict(c) for c in game_only}
                        ek = _k(entry)
                        if ek in acc:
                            try:
                                acc[ek]['quantity'] = int(acc[ek].get('quantity',1) or 1) + int(entry.get('quantity',1) or 1)
                            except Exception:
                                pass
                            # propagate enriched fields if provided
                            for f in ['set','set_code','year','link','image_url','price_usd','price_usd_foil','price_usd_etched','date_added']:
                                if entry.get(f):
                                    acc[ek][f] = entry.get(f)
                            # sum paid (entry is 0.0 here, but keep logic consistent)
                            try:
                                acc[ek]['paid'] = float(acc[ek].get('paid',0.0) or 0.0) + float(entry.get('paid',0.0) or 0.0)
                            except Exception:
                                pass
                        else:
                            acc[ek] = dict(entry)
                        merged_game = list(acc.values())
                        save_collection_to_csv(merged_game, dest_file)
                        to_remove.append(idx)
                        committed += 1
                    except Exception:
                        continue
                # Remove processed and persist queue
                if to_remove:
                    new_amb = [x for i, x in enumerate(amb) if i not in to_remove]
                    st.session_state['import_ambiguities'] = new_amb
                    try:
                        with open(amb_path, 'w', encoding='utf-8') as f:
                            json.dump(new_amb, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                try:
                    # Refresh in-memory collections and notify
                    st.session_state[SESSION_KEYS['collection']] = load_csv_collections()
                except Exception:
                    pass
                try:
                    st.toast(f"Resolved {committed} item(s).", icon="✅")
                except Exception:
                    st.success(f"Resolved {committed} item(s).")
                st.rerun()
        for idx, item in enumerate(amb):
            with st.expander(f"{item.get('game','')} — {item.get('name','')} (No. {item.get('number','')})", expanded=False):
                cands = item.get('candidates') or []
                if not cands:
                    st.info("No candidates attached.")
                    continue
                # Grid with images and an exclusive selector under each image
                try:
                    selected_idx = int(st.session_state.get(f"amb_sel_{idx}") or 0)
                except Exception:
                    selected_idx = 0
                try:
                    ncols = max(1, min(6, len(cands)))
                    rows = (len(cands) + ncols - 1) // ncols
                    for r in range(rows):
                        try:
                            cols = st.columns(ncols, gap="small")
                        except Exception:
                            cols = st.columns(ncols)
                        for ci in range(ncols):
                            j = r * ncols + ci
                            if j >= len(cands):
                                continue
                            with cols[ci]:
                                cnd = cands[j]
                                img = cnd.get('image_url')
                                if img:
                                    st.image(img, width=220)
                                sc = (cnd.get('set_code') or '').upper()
                                name_line = cnd.get('name','') or item.get('name','')
                                meta = f"[{sc}] {cnd.get('set','')} • No. {cnd.get('card_number','')}"
                                row = st.columns([2,6])
                                with row[0]:
                                    # radio-like exclusive selector via button
                                    is_sel = (j == selected_idx)
                                    if is_sel:
                                        st.button("Selected", key=f"amb_pick_{idx}_{j}", disabled=True)
                                    else:
                                        if st.button("Select", key=f"amb_pick_{idx}_{j}"):
                                            st.session_state[f"amb_sel_{idx}"] = j
                                            st.rerun()
                                with row[1]:
                                    if j == selected_idx:
                                        st.markdown(f"**{name_line}**")
                                    else:
                                        st.markdown(name_line)
                                    st.markdown(f"<div style='font-size:0.85rem;color:#999;margin-top:2px'>{meta}</div>", unsafe_allow_html=True)
                                # exclusive behavior handled by button above
                except Exception:
                    pass
                # Resolve current choice from session
                try:
                    choice = int(st.session_state.get(f"amb_sel_{idx}") or 0)
                except Exception:
                    choice = 0
                vcol1, vcol2 = st.columns([1,3])
                with vcol1:
                    qty = st.number_input("Quantity", min_value=1, max_value=999, value=int(item.get('quantity') or 1), key=f"amb_qty_{idx}")
                with vcol2:
                    st.write("")
                act_l, act_r = st.columns([3,1])
                if act_l.button("Import Selected", key=f"amb_btn_{idx}"):
                    sel = cands[choice]
                    entry = {
                        'game': item.get('game',''),
                        'name': sel.get('name') or item.get('name',''),
                        'set': sel.get('set',''),
                        'set_code': sel.get('set_code',''),
                        'card_number': sel.get('card_number',''),
                        'year': sel.get('year',''),
                        'image_url': sel.get('image_url',''),
                        'link': sel.get('link',''),
                        'price_usd': sel.get('price_usd', 0.0),
                        'price_usd_foil': sel.get('price_usd_foil', 0.0),
                        'price_usd_etched': sel.get('price_usd_etched', 0.0),
                        'quantity': int(qty or 1),
                        'variant': item.get('variant') or 'Normal',
                        'paid': 0.0,
                        'signed': '',
                        'altered': '',
                        'notes': item.get('notes',''),
                        'date_added': datetime.now().isoformat()
                    }
                    # Append to collection CSV for the correct game
                    dest_file = 'mtg_collection.csv' if entry['game'] == 'Magic: The Gathering' else 'pokemon_collection.csv'
                    current = load_csv_collections()
                    def _k(c):
                        kset = c.get('set_code') or c.get('set','')
                        return (c.get('game',''), c.get('name',''), kset, str(c.get('card_number','')), c.get('variant',''))
                    game_only = [c for c in current if c.get('game') == entry['game']]
                    acc = {_k(c): dict(c) for c in game_only}
                    ek = _k(entry)
                    if ek in acc:
                        try:
                            acc[ek]['quantity'] = int(acc[ek].get('quantity',1) or 1) + int(entry.get('quantity',1) or 1)
                        except Exception:
                            pass
                        for f in ['set','set_code','year','link','image_url','price_usd','price_usd_foil','price_usd_etched','date_added']:
                            if entry.get(f):
                                acc[ek][f] = entry.get(f)
                        try:
                            acc[ek]['paid'] = float(acc[ek].get('paid',0.0) or 0.0) + float(entry.get('paid',0.0) or 0.0)
                        except Exception:
                            pass
                    else:
                        acc[ek] = dict(entry)
                    merged_game = list(acc.values())
                    save_collection_to_csv(merged_game, dest_file)
                    to_remove.append(idx)
                    try:
                        st.toast("Imported selection.", icon="✅")
                    except Exception:
                        st.success("Imported selection.")
                    try:
                        st.session_state[SESSION_KEYS['collection']] = load_csv_collections()
                    except Exception:
                        pass
                    # Immediately drop this ambiguity from queue and persist
                    try:
                        amb_now = st.session_state.get('import_ambiguities') or []
                        new_amb = [x for i, x in enumerate(amb_now) if i != idx]
                        st.session_state['import_ambiguities'] = new_amb
                        if new_amb:
                            with open(amb_path, 'w', encoding='utf-8') as f:
                                json.dump(new_amb, f, ensure_ascii=False, indent=2)
                        else:
                            if os.path.exists(amb_path):
                                os.remove(amb_path)
                    except Exception:
                        pass
                    st.rerun()
                # Disregard option to drop this ambiguous row without importing (right side)
                if act_r.button("Disregard", key=f"amb_disregard_{idx}"):
                    to_remove.append(idx)
                    # Persist and refresh immediately
                    new_amb = [x for i, x in enumerate(st.session_state.get('import_ambiguities') or []) if i != idx]
                    st.session_state['import_ambiguities'] = new_amb
                    try:
                        if new_amb:
                            with open(amb_path, 'w', encoding='utf-8') as f:
                                json.dump(new_amb, f, ensure_ascii=False, indent=2)
                        else:
                            if os.path.exists(amb_path):
                                os.remove(amb_path)
                    except Exception:
                        pass
                    st.rerun()
        if to_remove:
            # Remove processed items by index
            new_amb = [x for i, x in enumerate(amb) if i not in to_remove]
            st.session_state['import_ambiguities'] = new_amb
            # Persist updated queue to disk (or delete file if empty)
            try:
                if new_amb:
                    with open(amb_path, 'w', encoding='utf-8') as f:
                        json.dump(new_amb, f, ensure_ascii=False, indent=2)
                else:
                    if os.path.exists(amb_path):
                        os.remove(amb_path)
            except Exception:
                pass
            if not new_amb:
                try:
                    st.toast("All ambiguities resolved.", icon="🎉")
                except Exception:
                    st.success("All ambiguities resolved.")
    up = st.file_uploader("Choose a CSV file", type=["csv"], key="import_csv_top")
    # Persist uploaded file bytes to survive reruns triggered by button clicks
    if up is not None:
        try:
            st.session_state['import_csv_bytes'] = up.getvalue()
            st.session_state['import_csv_name'] = getattr(up, 'name', 'upload.csv')
        except Exception:
            try:
                up.seek(0)
                st.session_state['import_csv_bytes'] = up.read()
                st.session_state['import_csv_name'] = 'upload.csv'
            except Exception:
                st.session_state['import_csv_bytes'] = None
    target = st.selectbox("Target", ["MTG Collection","Pokémon Collection","Watchlist"], index=0, key="import_target_top")
    mode = st.radio("Mode", ["Replace","Append"], index=1, horizontal=True, key="import_mode_top")
    enrich_scry = st.checkbox("Get values and details from Scryfall (MTG only)", value=True, key="import_enrich_scryfall")
    dup_mode = st.radio(
        "Duplicate handling (this import only)",
        ["Use Settings","Force Merge","Force Separate"],
        index=0,
        horizontal=True,
        key="import_dup_mode_top"
    )
    btn_import = st.button("Import", key="btn_import_csv_top")
    if btn_import and not (up or st.session_state.get('import_csv_bytes')):
        st.warning("Please choose a CSV file before importing.")
    if btn_import and (up or st.session_state.get('import_csv_bytes')):
        try:
            try:
                st.toast("Starting import...", icon="📥")
            except Exception:
                pass
            with st.spinner("Importing CSV..."):
                raw = st.session_state.get('import_csv_bytes')
                if raw is None and up is not None:
                    try:
                        up.seek(0)
                        raw = up.read()
                    except Exception:
                        raw = None
                if not raw:
                    st.error("Could not read the uploaded file. Please try uploading again.")
                    return
                try:
                    content = raw.decode('utf-8')
                except Exception:
                    try:
                        content = raw.decode('latin-1')
                    except Exception:
                        content = raw.decode(errors='ignore')
            import io as _io
            # Debug print to terminal
            try:
                print(f"📥 Import clicked • target={target} mode={mode} bytes={len(content)}")
            except Exception:
                pass
            r = csv.DictReader(_io.StringIO(content))
            rows = [dict(x) for x in r]
            if not rows:
                st.warning("No rows detected in the uploaded CSV. Please check the file and try again.")
                return
            if st.session_state.get(SESSION_KEYS.get("debug_mode", "debug_mode"), False):
                st.info(f"Parsed {len(rows)} row(s) from CSV. Columns: {list(rows[0].keys()) if rows else []}")
            # Normalize helpers
            def nfloat(v, dv=0.0):
                try:
                    return float(v)
                except Exception:
                    try:
                        return float(str(v).replace('$','').replace(',',''))
                    except Exception:
                        return dv
            def nint(v, dv=0):
                try:
                    return int(v)
                except Exception:
                    return dv

            # Resolve effective merge behavior for this import
            settings_merge = (st.session_state.get('duplicate_strategy') == 'merge')
            do_merge = (dup_mode == "Force Merge") or (dup_mode == "Use Settings" and settings_merge)

            if target in ("MTG Collection","Pokémon Collection"):
                coll = [] if mode == "Replace" else load_csv_collections()
                incoming = []
                target_game = 'Magic: The Gathering' if target == 'MTG Collection' else 'Pokémon'
                def _truthy(v: Any) -> bool:
                    try:
                        s = str(v or '').strip().lower()
                        return s in ('y','yes','true','1')
                    except Exception:
                        return False
                for row in rows:
                    # Force game to selected target to ensure correct filtering
                    row_game = target_game
                    # Common fields
                    base = {
                        'game': row_game,
                        'name': row.get('name',''),
                        'set': row.get('set','') or row.get('set_code',''),
                        'set_code': (row.get('set_code','') or '').lower(),
                        'year': row.get('year',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': nfloat(row.get('price_usd',0)),
                        'price_usd_foil': nfloat(row.get('price_usd_foil',0)),
                        'price_usd_etched': nfloat(row.get('price_usd_etched',0)),
                        'paid': nfloat(row.get('paid',0.0)),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    }
                    qty = nint(row.get('quantity',1),1) or 1
                    if row_game == 'Pokémon':
                        # Support 'number' as alias for card number
                        card_no = row.get('card_number','') or row.get('number','')
                        # Build entries from variant flags; default to Normal if none selected
                        variants_map = {
                            'normal': _truthy(row.get('normal')),
                            'unlimited': _truthy(row.get('unlimited')),
                            'holofoil': _truthy(row.get('holofoil') or row.get('holo')),
                            'unlimited_holofoil': _truthy(row.get('unlimited_holofoil') or row.get('unlimited_holo')),
                            'reverse_holofoil': _truthy(row.get('reverse_holofoil') or row.get('reverse_holo')),
                            'first_edition': _truthy(row.get('first_edition') or row.get('1stEdition')),
                            'first_edition_holo': _truthy(row.get('first_edition_holo') or row.get('1stEditionHolofoil')),
                        }
                        selected = [k for k,v in variants_map.items() if v]
                        if not selected:
                            selected = ['normal']
                        for vname in selected:
                            entry = dict(base)
                            entry.update({
                                'set': base.get('set',''),
                                'set_code': base.get('set_code',''),
                                'card_number': card_no,
                                'quantity': qty,
                                'variant': vname.replace('_', ' ').title() if vname != 'holofoil' else 'Holo',
                            })
                            incoming.append(entry)
                    else:
                        # MTG unchanged; accept provided card_number/collector_number and variant/foil
                        entry = dict(base)
                        entry.update({
                            'set': base.get('set',''),
                            'set_code': base.get('set_code',''),
                            'card_number': row.get('card_number','') or row.get('collector_number',''),
                            'quantity': qty,
                            'variant': row.get('variant',''),
                        })
                        incoming.append(entry)

                # Resolve rows by provider to auto-import or queue ambiguous
                resolved: List[Dict] = []
                ambiguities: List[Dict] = []
                not_found = 0
                prog2 = st.progress(0, text="Resolving rows…")
                for idx_r, r in enumerate(incoming):
                    g = r.get('game')
                    nm = (r.get('name') or '').strip()
                    num = str(r.get('card_number') or '').strip()
                    set_hint = (r.get('set') or '').strip()
                    if not nm:
                        continue
                    try:
                        cand_cards: List[Dict] = []
                        if g == 'Pokémon':
                            cards, shown, total, _ = search_pokemon_tcg(nm, set_hint=set_hint, number=num)
                            cand_cards = cards or []
                        elif g == 'Magic: The Gathering':
                            cards, shown, total, _ = search_mtg_scryfall(nm, set_hint=set_hint, collector_number=num)
                            cand_cards = cards or []
                        # Filter by exact or prefix number match
                        if num:
                            if g == 'Pokémon':
                                cand_cards = [c for c in cand_cards if str(c.get('card_number','')).startswith(num)]
                            else:
                                cand_cards = [c for c in cand_cards if str(c.get('card_number','')).strip() == num]
                        # Unique -> resolve
                        if len(cand_cards) == 1:
                            c = cand_cards[0]
                            ent = dict(r)
                            ent['set'] = c.get('set') or ent.get('set')
                            ent['set_code'] = (c.get('set_code') or ent.get('set_code') or '').lower()
                            ent['year'] = c.get('year') or ent.get('year')
                            ent['image_url'] = c.get('image_url') or ent.get('image_url')
                            ent['link'] = c.get('link') or ent.get('link')
                            # Prefer market price if present
                            ent['price_usd'] = c.get('price_usd', ent.get('price_usd', 0.0))
                            # Normalize variant default
                            if not ent.get('variant'):
                                ent['variant'] = 'Normal'
                            resolved.append(ent)
                        elif len(cand_cards) > 1:
                            # Build minimal candidate list
                            cands = []
                            for c in cand_cards:
                                cands.append({
                                    'game': g,
                                    'name': c.get('name',''),
                                    'set': c.get('set',''),
                                    'set_code': (c.get('set_code') or '').lower(),
                                    'card_number': c.get('card_number',''),
                                    'year': c.get('year',''),
                                    'image_url': c.get('image_url',''),
                                    'link': c.get('link',''),
                                    'price_usd': c.get('price_usd', 0.0),
                                    'price_usd_foil': c.get('price_usd_foil', 0.0),
                                    'price_usd_etched': c.get('price_usd_etched', 0.0),
                                })
                            ambiguities.append({
                                'game': g,
                                'name': nm,
                                'number': num,
                                'quantity': r.get('quantity', 1),
                                'variant': r.get('variant') or 'Normal',
                                'notes': r.get('notes',''),
                                'candidates': cands,
                            })
                        else:
                            not_found += 1
                    except Exception:
                        not_found += 1
                    finally:
                        try:
                            prog2.progress(min((idx_r+1)/max(1,len(incoming)), 1.0))
                        except Exception:
                            pass
                prog2.empty()
                # Use resolved entries only; ambiguities are queued for review
                incoming_final = resolved
                # Merge behavior on Append
                if mode == "Append" and do_merge:
                    # key: (game, name, set_or_code, card_number, variant)
                    def _k(c):
                        kset = c.get('set_code') or c.get('set','')
                        return (c.get('game',''), c.get('name',''), kset, c.get('card_number',''), c.get('variant',''))
                    acc = {}
                    # seed with existing
                    for c in coll:
                        acc[_k(c)] = dict(c)
                    # fold incoming
                    for c in incoming_final:
                        k = _k(c)
                        if k in acc:
                            # sum quantities
                            try:
                                acc[k]['quantity'] = int(acc[k].get('quantity',1) or 1) + int(c.get('quantity',1) or 1)
                            except Exception:
                                pass
                            # paid handling (sum)
                            try:
                                acc[k]['paid'] = float(acc[k].get('paid',0.0) or 0.0) + float(c.get('paid',0.0) or 0.0)
                            except Exception:
                                pass
                            # propagate enriched fields (prefer incoming if provided)
                            overwrite_fields = ['set','set_code','year','link','image_url']
                            for f in overwrite_fields:
                                if c.get(f):
                                    acc[k][f] = c.get(f)
                            # for numeric prices: prefer incoming if > 0
                            for f in ['price_usd','price_usd_foil','price_usd_etched']:
                                try:
                                    if float(c.get(f) or 0) > 0:
                                        acc[k][f] = c.get(f)
                                except Exception:
                                    pass
                            # update date_added to latest
                            if c.get('date_added'):
                                acc[k]['date_added'] = c.get('date_added')
                        else:
                            acc[k] = dict(c)
                    merged = list(acc.values())
                else:
                    merged = coll + incoming_final if mode == "Append" else incoming_final
                # Filter to specific game based on target
                if target == "MTG Collection":
                    merged = [c for c in merged if c.get('game') == 'Magic: The Gathering']
                    before = len([c for c in coll if c.get('game') == 'Magic: The Gathering']) if mode == "Append" else 0
                    try:
                        print(f"📦 Import->MTG: before={before} incoming={len(incoming)} merged={len(merged)} mode={mode} do_merge={do_merge}")
                    except Exception:
                        pass
                    save_collection_to_csv(merged, 'mtg_collection.csv')
                    try:
                        st.toast(f"Imported {len(incoming)} row(s) into MTG. New size: {len(merged)} (was {before}).", icon="✅")
                    except Exception:
                        pass
                    st.session_state['last_import_summary'] = f"✅ MTG import: {len(incoming_final)} resolved • {len(ambiguities)} ambiguous • {not_found} not found. New size {len(merged)} (was {before})."
                elif target == "Pokémon Collection":
                    merged = [c for c in merged if c.get('game') == 'Pokémon']
                    before = len([c for c in coll if c.get('game') == 'Pokémon']) if mode == "Append" else 0
                    try:
                        print(f"📦 Import->Pokemon: before={before} incoming={len(incoming)} merged={len(merged)} mode={mode} do_merge={do_merge}")
                    except Exception:
                        pass
                    save_collection_to_csv(merged, 'pokemon_collection.csv')
                    try:
                        st.toast(f"Imported {len(incoming)} row(s) into Pokémon. New size: {len(merged)} (was {before}).", icon="✅")
                    except Exception:
                        pass
                    st.session_state['last_import_summary'] = f"✅ Pokémon import: {len(incoming_final)} resolved • {len(ambiguities)} ambiguous • {not_found} not found. New size {len(merged)} (was {before})."
                # Store ambiguities for review panel
                if ambiguities:
                    st.session_state['import_ambiguities'] = ambiguities
                    # Persist ambiguities for this owner
                    try:
                        owner_id = _sanitize_owner_id(owner_label or '')
                        amb_path = os.path.join(get_collections_dir(), f"{owner_id}-import-ambiguities.json")
                        with open(amb_path, 'w', encoding='utf-8') as f:
                            json.dump(ambiguities, f, ensure_ascii=False, indent=2)
                    except Exception:
                        pass
                # Update session
                st.session_state[SESSION_KEYS['collection']] = load_csv_collections()
                st.rerun()
            else:
                # Watchlist
                wl = [] if mode == "Replace" else load_watchlist_from_csv()
                incoming = []
                for row in rows:
                    incoming.append({
                        'game': row.get('game',''),
                        'name': row.get('name',''),
                        'set': row.get('set','') or row.get('set_code',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': nfloat(row.get('price_usd',0)),
                        'price_usd_foil': nfloat(row.get('price_usd_foil',0)),
                        'price_usd_etched': nfloat(row.get('price_usd_etched',0)),
                        'quantity': nint(row.get('quantity',1),1),
                        'variant': row.get('variant',''),
                        'target_price': nfloat(row.get('target_price',0.0)),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    })
                if mode == "Append" and do_merge:
                    def _k(c):
                        kset = c.get('set_code') or c.get('set','')
                        return (c.get('game',''), c.get('name',''), kset, c.get('variant',''))
                    acc = {}
                    for c in wl:
                        acc[_k(c)] = dict(c)
                    for c in incoming:
                        k = _k(c)
                        if k in acc:
                            # For watchlist, sum quantity only; keep target_price as-is unless incoming provides one
                            try:
                                acc[k]['quantity'] = int(acc[k].get('quantity',1) or 1) + int(c.get('quantity',1) or 1)
                            except Exception:
                                pass
                            if c.get('target_price'):
                                acc[k]['target_price'] = c.get('target_price')
                            for f in ['price_usd','price_usd_foil','price_usd_etched','link','image_url','date_added']:
                                if not acc[k].get(f) and c.get(f):
                                    acc[k][f] = c.get(f)
                        else:
                            acc[k] = dict(c)
                    merged = list(acc.values())
                else:
                    merged = wl + incoming if mode == "Append" else incoming
                save_watchlist_to_csv(merged, 'watchlist.csv')
                st.session_state['watchlist'] = load_watchlist_from_csv()
                try:
                    st.toast(f"Imported {len(incoming)} watchlist row(s). New size: {len(merged)}.", icon="✅")
                except Exception:
                    pass
                st.session_state['last_import_summary'] = f"✅ Watchlist import complete: {len(incoming)} row(s). New size {len(merged)}."
                st.rerun()
        except Exception as e:
            st.error(f"Import failed: {e}")

    st.divider()
    st.subheader("Export")

    # Prepare current data
    try:
        coll_all = load_csv_collections()  # owner-aware
    except Exception:
        coll_all = []
    try:
        wl_all = load_watchlist_from_csv()
    except Exception:
        wl_all = []

    # Split by game
    mtg_only = [c for c in coll_all if c.get('game') == 'Magic: The Gathering']
    pkmn_only = [c for c in coll_all if c.get('game') == 'Pokémon']

    def _csv_bytes_for_collection(rows: List[Dict]) -> bytes:
        import io as _io
        buf = _io.StringIO()
        headers = [
            'game', 'name', 'set', 'set_code', 'card_number', 'year', 'link', 'image_url',
            'price_low', 'price_mid', 'price_market',
            'price_usd', 'price_usd_foil', 'price_usd_etched',
            'quantity', 'variant', 'total_value', 'paid', 'signed', 'altered', 'notes', 'timestamp'
        ]
        w = csv.DictWriter(buf, fieldnames=headers)
        w.writeheader()
        for c in rows:
            try:
                mv = c.get('price_market') if c.get('price_market') is not None else c.get('price_usd', 0)
            except Exception:
                mv = c.get('price_usd', 0)
            try:
                qty = int(c.get('quantity', 1) or 1)
            except Exception:
                qty = 1
            row = {
                'game': c.get('game',''), 'name': c.get('name',''), 'set': c.get('set',''),
                'set_code': c.get('set_code',''),
                'card_number': c.get('card_number',''), 'year': c.get('year',''),
                'link': c.get('link',''), 'image_url': c.get('image_url',''),
                'price_low': '', 'price_mid': '', 'price_market': '',
                'price_usd': c.get('price_usd',0), 'price_usd_foil': c.get('price_usd_foil',0), 'price_usd_etched': c.get('price_usd_etched',0),
                'quantity': qty, 'variant': c.get('variant',''),
                'total_value': (mv or 0) * qty,
                'paid': c.get('paid',0.0), 'signed': c.get('signed',''), 'altered': c.get('altered',''), 'notes': c.get('notes',''),
                'timestamp': c.get('date_added','')
            }
            w.writerow(row)
        return buf.getvalue().encode('utf-8')

    def _csv_bytes_for_watchlist(rows: List[Dict]) -> bytes:
        import io as _io
        buf = _io.StringIO()
        headers = [
            'game','name','set','link','image_url','price_low','price_mid','price_market',
            'price_usd','price_usd_foil','price_usd_etched','quantity','variant','target_price','signed','altered','notes','timestamp'
        ]
        w = csv.DictWriter(buf, fieldnames=headers)
        w.writeheader()
        for c in rows:
            row = {
                'game': c.get('game',''), 'name': c.get('name',''), 'set': c.get('set',''),
                'link': c.get('link',''), 'image_url': c.get('image_url',''),
                'price_low': '', 'price_mid': '', 'price_market': '',
                'price_usd': c.get('price_usd',0), 'price_usd_foil': c.get('price_usd_foil',0), 'price_usd_etched': c.get('price_usd_etched',0),
                'quantity': c.get('quantity',1), 'variant': c.get('variant',''),
                'target_price': c.get('target_price',0.0), 'signed': c.get('signed',''), 'altered': c.get('altered',''), 'notes': c.get('notes',''),
                'timestamp': c.get('date_added','')
            }
            w.writerow(row)
        return buf.getvalue().encode('utf-8')

    c_unified = _csv_bytes_for_collection(coll_all)
    c_mtg = _csv_bytes_for_collection(mtg_only)
    c_pkmn = _csv_bytes_for_collection(pkmn_only)
    c_wl = _csv_bytes_for_watchlist(wl_all)

    colA, colB, colC, colD = st.columns(4)
    with colA:
        st.download_button("Download unified_collection.csv", data=c_unified, file_name="unified_collection.csv", mime="text/csv")
    with colB:
        st.download_button("Download mtg_collection.csv", data=c_mtg, file_name="mtg_collection.csv", mime="text/csv")
    with colC:
        st.download_button("Download pokemon_collection.csv", data=c_pkmn, file_name="pokemon_collection.csv", mime="text/csv")
    with colD:
        st.download_button("Download watchlist.csv", data=c_wl, file_name="watchlist.csv", mime="text/csv")

    # ZIP export (includes a virtual unified CSV built from current data)
    import io as _io
    zip_buf = _io.BytesIO()
    with zipfile.ZipFile(zip_buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr('unified_collection.csv', c_unified)
        zf.writestr('mtg_collection.csv', c_mtg)
        zf.writestr('pokemon_collection.csv', c_pkmn)
        zf.writestr('watchlist.csv', c_wl)
    zip_buf.seek(0)
    st.download_button("Download all as ZIP", data=zip_buf.getvalue(), file_name="export_all.zip", mime="application/zip")

    st.divider()
    st.subheader("Templates")
    st.caption("Download import templates")
    import io as _io
    def _tmpl_bytes(headers):
        s = _io.StringIO()
        w = csv.DictWriter(s, fieldnames=headers)
        w.writeheader()
        return s.getvalue().encode('utf-8')
    # Dedicated MTG import template (requested headers)
    mtg_import_headers = ['name','set','set_code','card_number','quantity','foil','paid','signed','altered','notes']
    # Dedicated Pokémon import template (minimal headers)
    pkmn_import_headers = ['name','set','card_number','quantity','paid','signed','altered','notes']
    # Dedicated Watchlist import template (minimal headers)
    wl_import_headers = ['name','set','quantity','target_price','notes']
    cI1, cI2, cI3 = st.columns(3)
    with cI1:
        st.download_button("Template: mtg_import_template.csv", data=_tmpl_bytes(mtg_import_headers), file_name="mtg_import_template.csv", mime="text/csv")
    with cI2:
        st.download_button("Template: pokemon_import_template.csv", data=_tmpl_bytes(pkmn_import_headers), file_name="pokemon_import_template.csv", mime="text/csv")
    with cI3:
        st.download_button("Template: watchlist_import_template.csv", data=_tmpl_bytes(wl_import_headers), file_name="watchlist_import_template.csv", mime="text/csv")

    st.divider()
    # Delete owner with fail-safe options
    try:
        existing = list_owner_folders()
    except Exception:
        existing = []
    with st.expander("Delete an owner (with fail-safe options)"):
        if not existing:
            st.info("No owners to delete. Create one first.")
        else:
            del_owner = st.selectbox("Owner to delete", existing, key="owner_to_delete")
            action = st.radio(
                "When deleting, what should we do with their data?",
                [
                    "Merge into another owner",
                    "Download ZIP (do not delete)",
                    "Permanently delete data"
                ],
                key="owner_delete_action"
            )
            # Additional inputs depending on action
            target_owner = None
            if action == "Merge into another owner":
                merge_targets = [o for o in existing if o != del_owner]
                if not merge_targets:
                    st.warning("No other owners to merge into.")
                else:
                    target_owner = st.selectbox("Merge into", merge_targets, key="owner_merge_target")

            # Confirmation
            confirm = st.checkbox("I understand this action is irreversible.", key="owner_delete_confirm")
            if st.button("Proceed", key="btn_owner_delete"):
                if not confirm:
                    st.warning("Please confirm before proceeding.")
                else:
                    if action == "Download ZIP (do not delete)":
                        buf = _zip_owner_folder_to_memory(del_owner)
                        if buf:
                            st.download_button(
                                label=f"Download {del_owner}.zip",
                                data=buf.getvalue(),
                                file_name=f"{del_owner}.zip",
                                mime="application/zip",
                                key="btn_download_owner_zip"
                            )
                            st.info("Downloaded archive is prepared below. No deletion has occurred.")
                        else:
                            st.error("Failed to create ZIP archive.")
                    elif action == "Merge into another owner":
                        if not target_owner:
                            st.error("Please choose a target owner to merge into.")
                        else:
                            msg = _merge_owner_into(del_owner, target_owner)
                            if msg.startswith("✅"):
                                # After successful merge, delete source owner folder
                                _delete_owner_folder(del_owner)
                                st.success(msg + f" Source '{del_owner}' deleted.")
                                st.rerun()
                            else:
                                st.error(msg)
                    elif action == "Permanently delete data":
                        ok = _delete_owner_folder(del_owner)
                        if ok:
                            st.success(f"Deleted owner '{del_owner}' and all associated files.")
                            st.rerun()
                        else:
                            st.error("Failed to delete owner folder.")

def _owner_folder_path(label: str) -> str:
    return os.path.join(get_collections_dir(), label)

def _zip_owner_folder_to_memory(owner_label: str) -> io.BytesIO:
    try:
        folder = _owner_folder_path(owner_label)
        if not os.path.isdir(folder):
            return None
        buf = io.BytesIO()
        with zipfile.ZipFile(buf, 'w', compression=zipfile.ZIP_DEFLATED) as zf:
            for root, _, files in os.walk(folder):
                for fn in files:
                    full = os.path.join(root, fn)
                    arc = os.path.relpath(full, start=os.path.dirname(folder))
                    zf.write(full, arc)
        buf.seek(0)
        return buf
    except Exception:
        return None

def _delete_owner_folder(owner_label: str) -> bool:
    try:
        # Don't allow deleting if set as default owner
        if st.session_state.get('default_owner_label') == owner_label:
            return False
        p = _owner_folder_path(owner_label)
        if os.path.isdir(p):
            shutil.rmtree(p)
        return True
    except Exception:
        return False

def _merge_owner_into(src_owner_label: str, dst_owner_label: str) -> str:
    try:
        # Load source owner files
        coll_dir = get_collections_dir()
        def _read_owner_file(owner_label: str, base: str) -> List[Dict]:
            rel = owner_relative_filename(_owner_from_folder_label(owner_label), base)
            path = os.path.join(coll_dir, rel)
            rows: List[Dict] = []
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            rows.append(dict(r))
            except Exception:
                pass
            return rows

        uni = _read_owner_file(src_owner_label, 'unified_collection.csv')
        mtg = _read_owner_file(src_owner_label, 'mtg_collection.csv')
        pkmn = _read_owner_file(src_owner_label, 'pokemon_collection.csv')
        wl = _read_owner_file(src_owner_label, 'watchlist.csv')

        # Normalize rows to in-memory schema
        def _norm_collection(rows: List[Dict]) -> List[Dict]:
            out: List[Dict] = []
            for row in rows:
                try:
                    out.append({
                        'game': row.get('game',''),
                        'name': row.get('name',''),
                        'set': row.get('set',''),
                        'card_number': row.get('card_number','') or row.get('collector_number',''),
                        'year': row.get('year',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': float(row.get('price_usd',0) or 0),
                        'price_usd_foil': float(row.get('price_usd_foil',0) or 0),
                        'price_usd_etched': float(row.get('price_usd_etched',0) or 0),
                        'quantity': int(row.get('quantity',1) or 1),
                        'variant': row.get('variant',''),
                        'paid': float(row.get('paid',0) or 0),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    })
                except Exception:
                    continue
            return out

        def _norm_watchlist(rows: List[Dict]) -> List[Dict]:
            out: List[Dict] = []
            for row in rows:
                try:
                    out.append({
                        'game': row.get('game',''),
                        'name': row.get('name',''),
                        'set': row.get('set',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': float(row.get('price_usd',0) or 0),
                        'price_usd_foil': float(row.get('price_usd_foil',0) or 0),
                        'price_usd_etched': float(row.get('price_usd_etched',0) or 0),
                        'quantity': int(row.get('quantity',1) or 1),
                        'variant': row.get('variant',''),
                        'target_price': float(row.get('target_price',0) or 0),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    })
                except Exception:
                    continue
            return out

        # Switch save context to destination owner
        prev = st.session_state.get('current_owner_label')
        st.session_state['current_owner_label'] = dst_owner_label

        # Load existing destination data to append to
        dst_coll = load_csv_collections()
        dst_wl = load_watchlist_from_csv()

        # Merge: append items and persist
        merged_uni = (dst_coll or []) + _norm_collection(uni)
        save_collection_to_csv(merged_uni, 'unified_collection.csv')

        merged_mtg = [c for c in merged_uni if c.get('game') == 'Magic: The Gathering']
        merged_pkmn = [c for c in merged_uni if c.get('game') == 'Pokémon']
        if merged_mtg:
            save_collection_to_csv(merged_mtg, 'mtg_collection.csv')
        if merged_pkmn:
            save_collection_to_csv(merged_pkmn, 'pokemon_collection.csv')

        merged_wl = (dst_wl or []) + _norm_watchlist(wl)
        save_watchlist_to_csv(merged_wl, 'watchlist.csv')

        # restore owner context
        if prev is not None:
            st.session_state['current_owner_label'] = prev
        return f"✅ Merged '{src_owner_label}' into '{dst_owner_label}'"
    except Exception as e:
        return f"❌ Merge failed: {e}"
def _copy_legacy_default_to_owner(owner_label: str) -> str:
    """Copy data from legacy root CSVs into the specified owner. Returns a status message."""
    try:
        coll_dir = get_collections_dir()
        # Legacy files (root under collections)
        f_mtg = os.path.join(coll_dir, 'mtg_collection.csv')
        f_pkmn = os.path.join(coll_dir, 'pokemon_collection.csv')
        f_uni = os.path.join(coll_dir, 'unified_collection.csv')
        f_wl = os.path.join(coll_dir, 'watchlist.csv')

        any_found = any(os.path.exists(p) for p in [f_mtg, f_pkmn, f_uni, f_wl])
        if not any_found:
            return "ℹ️ No legacy Default CSVs found to copy."

        # Parse legacy into memory (tolerant minimal parser)
        def _read_csv_rows(path: str) -> List[Dict]:
            rows: List[Dict] = []
            try:
                if os.path.exists(path):
                    with open(path, 'r', encoding='utf-8') as f:
                        reader = csv.DictReader(f)
                        for r in reader:
                            rows.append(dict(r))
            except Exception:
                pass
            return rows

        uni_rows = _read_csv_rows(f_uni)
        mtg_rows = _read_csv_rows(f_mtg)
        pkmn_rows = _read_csv_rows(f_pkmn)
        wl_rows = _read_csv_rows(f_wl)

        # Switch save context to target owner for save_* helpers
        prev = st.session_state.get('current_owner_label')
        st.session_state['current_owner_label'] = owner_label

        # Convert rows to our in-memory schema for collections (best-effort)
        def _norm_collection(rows: List[Dict]) -> List[Dict]:
            out: List[Dict] = []
            for row in rows:
                try:
                    out.append({
                        'game': row.get('game',''),
                        'name': row.get('name',''),
                        'set': row.get('set',''),
                        'card_number': row.get('card_number','') or row.get('collector_number',''),
                        'year': row.get('year',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': float(row.get('price_usd',0) or 0),
                        'price_usd_foil': float(row.get('price_usd_foil',0) or 0),
                        'price_usd_etched': float(row.get('price_usd_etched',0) or 0),
                        'quantity': int(row.get('quantity',1) or 1),
                        'variant': row.get('variant',''),
                        'paid': float(row.get('paid',0) or 0),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    })
                except Exception:
                    continue
            return out

        def _norm_watchlist(rows: List[Dict]) -> List[Dict]:
            out: List[Dict] = []
            for row in rows:
                try:
                    out.append({
                        'game': row.get('game',''),
                        'name': row.get('name',''),
                        'set': row.get('set',''),
                        'link': row.get('link',''),
                        'image_url': row.get('image_url',''),
                        'price_usd': float(row.get('price_usd',0) or 0),
                        'price_usd_foil': float(row.get('price_usd_foil',0) or 0),
                        'price_usd_etched': float(row.get('price_usd_etched',0) or 0),
                        'quantity': int(row.get('quantity',1) or 1),
                        'variant': row.get('variant',''),
                        'target_price': float(row.get('target_price',0) or 0),
                        'signed': row.get('signed',''),
                        'altered': row.get('altered',''),
                        'notes': row.get('notes',''),
                        'date_added': row.get('timestamp','') or row.get('date_added','')
                    })
                except Exception:
                    continue
            return out

        # Save under target owner
        if uni_rows:
            save_collection_to_csv(_norm_collection(uni_rows), 'unified_collection.csv')
        if mtg_rows:
            save_collection_to_csv(_norm_collection(mtg_rows), 'mtg_collection.csv')
        if pkmn_rows:
            save_collection_to_csv(_norm_collection(pkmn_rows), 'pokemon_collection.csv')
        if wl_rows:
            save_watchlist_to_csv(_norm_watchlist(wl_rows), 'watchlist.csv')

        # restore
        if prev is not None:
            st.session_state['current_owner_label'] = prev
        return f"✅ Copied legacy CSVs to {owner_label}"
    except Exception as e:
        return f"❌ Copy failed: {e}"

def render_all_cards_view(collection: List[Dict]):
    """Render all cards in collection with filtering and sorting (collection already scoped by header selector)"""
    st.subheader("🗂️ All Cards")
    
    # Filter and sort controls (no game filter here; header selector controls scope)
    col1, col2, col3 = st.columns([2, 2, 1])
    
    with col1:
        # Set filter based on the provided scoped collection
        sets = ["All"] + sorted(list(set(f"{card.get('year', '')} {card.get('set', '')}" for card in collection)))
        selected_set = st.selectbox("Filter by Set", sets)
    
    with col2:
        # Sort options
        sort_options = ["Name", "Set", "Year", "Price", "Quantity", "Date Added"]
        sort_by = st.selectbox("Sort By", sort_options)
    
    with col3:
        # View mode
        view_mode = st.radio("View", ["Grid", "List"], horizontal=True)
    
    # Filter collection (only by set; game scoping handled at header)
    filtered_collection = collection.copy()
    if selected_set != "All":
        filtered_collection = [card for card in filtered_collection if f"{card.get('year', '')} {card.get('set', '')}" == selected_set]
    
    # Sort collection
    if sort_by == "Name":
        filtered_collection.sort(key=lambda x: x.get("name", ""))
    elif sort_by == "Set":
        filtered_collection.sort(key=lambda x: f"{x.get('year', '')} {x.get('set', '')}")
    elif sort_by == "Year":
        filtered_collection.sort(key=lambda x: x.get("year", ""), reverse=True)
    elif sort_by == "Price":
        filtered_collection.sort(key=lambda x: x.get("price_usd", 0), reverse=True)
    elif sort_by == "Quantity":
        filtered_collection.sort(key=lambda x: x.get("quantity", 0), reverse=True)
    elif sort_by == "Date Added":
        filtered_collection.sort(key=lambda x: x.get("date_added", ""), reverse=True)
    
    st.write(f"**Showing {len(filtered_collection)} cards**")
    
    if filtered_collection:
        if view_mode == "Grid":
            # Grid view
            cards_per_row = st.slider("Cards per Row", 1, 6, 3)
            render_collection_grid(filtered_collection, cards_per_row)
        else:
            # List view
            render_collection_list(filtered_collection)
    else:
        st.warning("No cards match your filters.")

def render_collection_tab(collection: List[Dict]):
    """Collection tab: grid/list with filters (wrapper around existing logic)"""
    # Build a data grid with requested columns
    if not collection:
        st.info("No cards in this scope.")
        return

    # Load set-year mapping (cached)
    year_map_mtg, year_map_pkmn = load_set_year_map()

    def _norm(s: str) -> str:
        import re as _re
        return _re.sub(r"[^a-z0-9]+", "", (s or '').strip().lower())

    def _find_year(m: dict, name: str, fb: str) -> str:
        n = _norm(name)
        # 1) exact normalized match
        if n in m:
            return str(m[n])
        # 2) loose contains match
        for k, v in m.items():
            if n and (n in k or k in n):
                return str(v)
        # 3) try to extract a 4-digit year from the set name itself
        import re as _re
        m_year = _re.search(r"(19\d{2}|20\d{2})", name or "")
        if m_year:
            return m_year.group(1)
        return str(fb or '')

    def lookup_year(game: str, set_name: str, fallback_year: str) -> str:
        if game == 'Magic: The Gathering':
            return _find_year(year_map_mtg, set_name, fallback_year)
        if game == 'Pokémon':
            return _find_year(year_map_pkmn, set_name, fallback_year)
        return str(fallback_year or '')

    rows = []
    for c in collection:
        qty = int(c.get('quantity', 1) or 1)
        mv = c.get('price_market') if c.get('price_market') is not None else c.get('price_usd', 0)
        rows.append({
            'Collection': c.get('game', ''),
            'Card Name': c.get('name', ''),
            'Set Name': c.get('set', ''),
            'Quantity': qty,
            'Year': lookup_year(c.get('game',''), c.get('set',''), c.get('year','')),
            'Low value': c.get('price_low'),
            'Mid value': c.get('price_mid'),
            'Market value': mv,
            'Total value': (mv or 0) * qty,
            'Paid': c.get('paid', 0.0),
            'Version': c.get('variant', ''),
        })

    df = pd.DataFrame(rows)
    # Numeric coercion for display
    for col in ['Quantity', 'Low value', 'Mid value', 'Market value', 'Total value', 'Paid']:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors='coerce')

    # Simple filters: Set and text search
    colf1, colf2 = st.columns([2, 2])
    with colf1:
        sets = ['All'] + sorted([s for s in df['Set Name'].dropna().unique().tolist()])
        sel_set = st.selectbox('Filter by Set', sets, key='coll_set_filter')
    with colf2:
        search = st.text_input('Search Card Name', key='coll_name_search')

    df_view = df.copy()
    if sel_set != 'All':
        df_view = df_view[df_view['Set Name'] == sel_set]
    if search:
        s = search.strip().lower()
        df_view = df_view[df_view['Card Name'].str.lower().str.contains(s, na=False)]

    # Portfolio total metric (filtered view)
    try:
        portfolio_total = float(pd.to_numeric(df_view.get('Total value'), errors='coerce').fillna(0).sum())
    except Exception:
        portfolio_total = 0.0
    st.metric("Portfolio Total (filtered)", f"${portfolio_total:,.2f}")

    # Use editable grid for inline editing of Quantity, Paid, Version
    col_cfg = {
        'Quantity': st.column_config.NumberColumn(min_value=0, step=1),
        'Paid': st.column_config.NumberColumn(min_value=0.0, format='$%.2f'),
        'Low value': st.column_config.NumberColumn(format='$%.2f'),
        'Mid value': st.column_config.NumberColumn(format='$%.2f'),
        'Market value': st.column_config.NumberColumn(format='$%.2f'),
        'Total value': st.column_config.NumberColumn(format='$%.2f'),
        'Version': st.column_config.TextColumn(),
    }
    # Add a Delete checkbox column for row-wise deletion
    df_view['Delete'] = False
    df_edited = st.data_editor(
        df_view,
        width='stretch',
        disabled=[col for col in df_view.columns if col not in ['Quantity', 'Paid', 'Version', 'Delete']],
        column_config=col_cfg,
        key='collection_editor'
    )
    
    if st.button('💾 Save Changes', key='save_collection_changes'):
        # Update underlying session_state collection based on edited rows
        updated = 0
        sess_collection = st.session_state.get(SESSION_KEYS["collection"], [])
        for _, row in df_edited.iterrows():
            key_tuple = (
                row.get('Collection', ''),
                row.get('Card Name', ''),
                row.get('Set Name', ''),
                row.get('Version', ''),
            )
            # find match in session collection
            for card in sess_collection:
                cand = (
                    card.get('game', ''),
                    card.get('name', ''),
                    card.get('set', ''),
                    card.get('variant', ''),
                )
                if cand == key_tuple:
                    # apply edits
                    try:
                        card['quantity'] = int(row.get('Quantity', card.get('quantity', 1)) or 0)
                    except Exception:
                        pass
                    try:
                        paid_val = float(row.get('Paid', card.get('paid', 0.0)) or 0.0)
                        card['paid'] = paid_val
                    except Exception:
                        pass
                    card['variant'] = str(row.get('Version', card.get('variant', '')) or '')
                    updated += 1
                    break
        # Persist
        st.session_state[SESSION_KEYS["collection"]] = sess_collection
        save_collection_to_csv(sess_collection, "unified_collection.csv")
        mtg_cards = [c for c in sess_collection if c.get("game") == "Magic: The Gathering"]
        pokemon_cards = [c for c in sess_collection if c.get("game") == "Pokémon"]
        if mtg_cards:
            save_collection_to_csv(mtg_cards, "mtg_collection.csv")
        if pokemon_cards:
            save_collection_to_csv(pokemon_cards, "pokemon_collection.csv")
        st.success(f"Saved changes to {updated} item(s).")
        st.rerun()

    # Handle deletions
    if st.button('🗑️ Delete Selected', key='delete_selected_collection'):
        to_delete_keys = []
        for _, row in df_edited.iterrows():
            try:
                if bool(row.get('Delete', False)):
                    key_tuple = (
                        row.get('Collection', ''),
                        row.get('Card Name', ''),
                        row.get('Set Name', ''),
                        row.get('Version', ''),
                    )
                    to_delete_keys.append(key_tuple)
            except Exception:
                continue
        if not to_delete_keys:
            st.info('No rows selected for deletion.')
        else:
            sess_collection = st.session_state.get(SESSION_KEYS["collection"], [])
            before = len(sess_collection)
            kept = []
            for card in sess_collection:
                cand = (
                    card.get('game', ''),
                    card.get('name', ''),
                    card.get('set', ''),
                    card.get('variant', ''),
                )
                if cand not in to_delete_keys:
                    kept.append(card)
            st.session_state[SESSION_KEYS['collection']] = kept
            # Persist updates
            save_collection_to_csv(kept, 'unified_collection.csv')
            mtg_cards = [c for c in kept if c.get('game') == 'Magic: The Gathering']
            pokemon_cards = [c for c in kept if c.get('game') == 'Pokémon']
            if mtg_cards:
                save_collection_to_csv(mtg_cards, 'mtg_collection.csv')
            if pokemon_cards:
                save_collection_to_csv(pokemon_cards, 'pokemon_collection.csv')
            removed = before - len(kept)
            st.success(f"Deleted {removed} item(s) from collection.")
            st.rerun()

def render_watchlist_tab():
    """Render the Watchlist tab: view and delete watchlist items."""
    watchlist = st.session_state.get('watchlist', [])
    st.subheader('⭐ Watchlist')
    st.caption(f"Items: {len(watchlist)}")
    if not watchlist:
        st.info('Your watchlist is empty.')
        return
    # Build DataFrame for display
    rows = []
    for w in watchlist:
        rows.append({
            'Collection': w.get('game', ''),
            'Card Name': w.get('name', ''),
            'Set Name': w.get('set', ''),
            'Variant': w.get('variant', ''),
            'Quantity': int(w.get('quantity', 1) or 1),
            'Price (USD)': w.get('price_usd', 0),
            'Target Price': w.get('target_price', 0.0),
            'Date Added': w.get('date_added', ''),
            'Delete': False,
        })
    dfw = pd.DataFrame(rows)
    # Column formatting and which are editable
    wl_cfg = {
        'Quantity': st.column_config.NumberColumn(min_value=0, step=1),
        'Price (USD)': st.column_config.NumberColumn(format='$%.2f'),
        'Target Price': st.column_config.NumberColumn(min_value=0.0, format='$%.2f'),
    }
    dfw_edited = st.data_editor(
        dfw,
        width='stretch',
        disabled=[c for c in dfw.columns if c not in ['Quantity', 'Target Price', 'Delete']],
        column_config=wl_cfg,
        key='watchlist_editor'
    )
    if st.button('💾 Save Watchlist Changes', key='save_watchlist_changes'):
        wl = st.session_state.get('watchlist', [])
        updated = 0
        for _, row in dfw_edited.iterrows():
            key_tuple = (
                row.get('Collection', ''),
                row.get('Card Name', ''),
                row.get('Set Name', ''),
                row.get('Variant', ''),
            )
            for item in wl:
                cand = (
                    item.get('game', ''),
                    item.get('name', ''),
                    item.get('set', ''),
                    item.get('variant', ''),
                )
                if cand == key_tuple:
                    try:
                        item['quantity'] = int(row.get('Quantity', item.get('quantity', 1)) or 0)
                    except Exception:
                        pass
                    try:
                        item['target_price'] = float(row.get('Target Price', item.get('target_price', 0.0)) or 0.0)
                    except Exception:
                        pass
                    updated += 1
                    break
        st.session_state['watchlist'] = wl
        save_watchlist_to_csv(wl, 'watchlist.csv')
        st.success(f"Saved changes to {updated} watchlist item(s).")
        st.rerun()
    if st.button('🗑️ Delete Selected from Watchlist', key='delete_selected_watchlist'):
        to_delete = []
        for _, row in dfw_edited.iterrows():
            try:
                if bool(row.get('Delete', False)):
                    key_tuple = (
                        row.get('Collection', ''),
                        row.get('Card Name', ''),
                        row.get('Set Name', ''),
                        row.get('Variant', ''),
                    )
                    to_delete.append(key_tuple)
            except Exception:
                continue
        if not to_delete:
            st.info('No watchlist rows selected for deletion.')
        else:
            kept = []
            for w in watchlist:
                cand = (
                    w.get('game', ''),
                    w.get('name', ''),
                    w.get('set', ''),
                    w.get('variant', ''),
                )
                if cand not in to_delete:
                    kept.append(w)
            st.session_state['watchlist'] = kept
            save_watchlist_to_csv(kept, 'watchlist.csv')
            st.success(f"Deleted {len(watchlist) - len(kept)} item(s) from watchlist.")
            st.rerun()

@st.cache_data(show_spinner=False)
def load_set_year_map() -> tuple[dict, dict]:
    """Load mapping from set name -> year for MTG and Pokémon from fallback_data CSVs."""
    base_dir = os.path.dirname(__file__)
    mtg_path = os.path.join(base_dir, 'fallback_data', 'MTG', 'mtgsets.csv')
    pkmn_path = os.path.join(base_dir, 'fallback_data', 'Pokemon', 'pokemonsets.csv')
    mtg_map: dict[str, str] = {}
    pkmn_map: dict[str, str] = {}

    def normalize(name: str) -> str:
        import re
        return re.sub(r"[^a-z0-9]+", "", (name or '').strip().lower())

    # Load MTG
    try:
        if os.path.exists(mtg_path):
            with open(mtg_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    set_name = row.get('set') or row.get('name') or row.get('Name') or row.get('set_name') or row.get('Set Name') or ''
                    year = (
                        row.get('year') or row.get('released') or row.get('releaseDate') or row.get('release_date') or row.get('released_at') or 
                        row.get('printed') or row.get('printedAt') or row.get('printed_at') or ''
                    )
                    if set_name:
                        # store 4-digit year when possible
                        import re as _re
                        y = str(year)
                        m4 = _re.search(r"(19\d{2}|20\d{2})", y)
                        if m4:
                            y_val = m4.group(1)
                        else:
                            # Try to parse two-digit year formats like MM/DD/YY
                            m2 = _re.search(r"(?:^|[^0-9])(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?:[^0-9]|$)", y)
                            if m2:
                                yy = int(m2.group(3))
                                y_val = str(1900 + yy) if yy >= 90 else str(2000 + yy)
                            else:
                                # If the entire string (trimmed) is two digits, expand it
                                y_trim = y.strip()
                                if _re.fullmatch(r"\d{2}", y_trim):
                                    yy = int(y_trim)
                                    y_val = str(1900 + yy) if yy >= 90 else str(2000 + yy)
                                else:
                                    y_val = y_trim
                        mtg_map[normalize(set_name)] = y_val
    except Exception:
        pass

    # Load Pokémon
    try:
        if os.path.exists(pkmn_path):
            with open(pkmn_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    set_name = row.get('set') or row.get('name') or row.get('Name') or row.get('set_name') or row.get('Set Name') or ''
                    year = (
                        row.get('year') or row.get('released') or row.get('releaseDate') or row.get('release_date') or row.get('released_at') or 
                        row.get('printed') or row.get('printedAt') or row.get('printed_at') or ''
                    )
                    if set_name:
                        import re as _re
                        y = str(year)
                        m4 = _re.search(r"(19\d{2}|20\d{2})", y)
                        if m4:
                            y_val = m4.group(1)
                        else:
                            m2 = _re.search(r"(?:^|[^0-9])(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?:[^0-9]|$)", y)
                            if m2:
                                yy = int(m2.group(3))
                                y_val = str(1900 + yy) if yy >= 90 else str(2000 + yy)
                            else:
                                y_trim = y.strip()
                                if _re.fullmatch(r"\d{2}", y_trim):
                                    yy = int(y_trim)
                                    y_val = str(1900 + yy) if yy >= 90 else str(2000 + yy)
                                else:
                                    y_val = y_trim
                        pkmn_map[normalize(set_name)] = y_val
    except Exception:
        pass

    return mtg_map, pkmn_map

def render_gallery_view_tab(collection: List[Dict]):
    """Gallery view: image-first grid with filters (scoped by header selector)"""
    # Filters (no game filter here; header selector controls scope)
    col1, _ = st.columns(2)
    with col1:
        sets = ["All"] + sorted(list(set(f"{card.get('year', '')} {card.get('set', '')}" for card in collection)))
        sel_set = st.selectbox("Set", sets, key="gallery_set")
    
    # Apply filters
    filtered = collection
    if sel_set != "All":
        filtered = [c for c in filtered if f"{c.get('year', '')} {c.get('set', '')}" == sel_set]
    
    st.write(f"Showing {len(filtered)} cards")
    
    # Gallery options
    cols = st.columns(3)
    with cols[0]:
        per_row = st.slider("Cards/Row", 2, 8, 5, key="gallery_per_row")
    with cols[1]:
        img_w = st.slider("Image Width", 120, 320, 200, key="gallery_img_w")
    with cols[2]:
        show_labels = st.toggle("Show Labels", value=True, key="gallery_labels")
    
    # Render gallery grid
    for i in range(0, len(filtered), per_row):
        row_cols = st.columns(per_row)
        for j in range(per_row):
            idx = i + j
            if idx >= len(filtered):
                break
            card = filtered[idx]
            with row_cols[j]:
                img_url = card.get('image_url') or "https://via.placeholder.com/200x280"
                st.image(img_url, width=img_w)
                if show_labels:
                    st.caption(f"{card.get('name','')} — {card.get('year','')} {card.get('set','')}")

def render_investment_tab(collection: List[Dict]):
    """Investment tab: charts and graphs about values"""
    if not collection:
        st.info("No data to analyze yet.")
        return
    
    # Aggregate by game
    df = pd.DataFrame(collection)
    # coerce numeric fields
    df['price_usd'] = pd.to_numeric(df.get('price_usd', 0), errors='coerce').fillna(0.0)
    df['quantity'] = pd.to_numeric(df.get('quantity', 1), errors='coerce').fillna(1).astype(int)
    df['total_value'] = df['price_usd'] * df['quantity']
    by_game = df.groupby('game', dropna=False)['total_value'].sum().reset_index().sort_values('total_value', ascending=False)
    by_set = df.groupby(df['year'].astype(str) + ' ' + df['set'].astype(str), dropna=False)['total_value'].sum().reset_index().rename(columns={'year set':'Set'}).sort_values('total_value', ascending=False).head(15)
    
    st.subheader("Value by Game")
    st.bar_chart(by_game.set_index('game'))
    
    st.subheader("Top Sets by Value")
    # Rename columns for chart
    by_set.columns = ['Set', 'total_value']
    st.bar_chart(by_set.set_index('Set'))
    
    # Recent additions over time (if timestamps exist)
    if 'date_added' in df.columns and df['date_added'].notna().any():
        try:
            df_time = df.copy()
            df_time['date'] = pd.to_datetime(df_time['date_added'], errors='coerce').dt.date
            timeline = df_time.groupby('date')['total_value'].sum().reset_index().dropna()
            if not timeline.empty:
                st.subheader("Collection Value Over Time (by Date Added)")
                st.line_chart(timeline.set_index('date'))
        except Exception:
            pass

def render_by_game_view(collection: List[Dict]):
    """Render collection grouped by game"""
    st.subheader("🎮 Collection by Game")
    
    # Group cards by game
    games = {}
    for card in collection:
        game = card.get("game", "Unknown")
        if game not in games:
            games[game] = []
        games[game].append(card)
    
    for game, cards in games.items():
        with st.expander(f"🎮 {game} ({len(cards)} cards)"):
            # Game stats
            col1, col2, col3 = st.columns(3)
            with col1:
                total_cards = sum(card.get("quantity", 1) for card in cards)
                st.metric("Total Cards", total_cards)
            with col2:
                unique_sets = len(set(f"{card.get('year', '')} {card.get('set', '')}" for card in cards))
                st.metric("Unique Sets", unique_sets)
            with col3:
                total_value = sum(card.get("price_usd", 0) * card.get("quantity", 1) for card in cards)
                st.metric("Total Value", f"${total_value:.2f}")
            
            # Render cards in compact grid
            render_collection_grid(cards, 4, compact=True)

def render_by_set_view(collection: List[Dict]):
    """Render collection grouped by set"""
    st.subheader("📚 Collection by Set")
    
    # Group cards by set
    sets = {}
    for card in collection:
        set_key = f"{card.get('year', '')} {card.get('set', '')}"
        if set_key not in sets:
            sets[set_key] = []
        sets[set_key].append(card)
    
    # Sort sets by year
    sorted_sets = sorted(sets.keys(), key=lambda x: x.split()[0] if x.split() else "", reverse=True)
    
    for set_name in sorted_sets:
        cards = sets[set_name]
        with st.expander(f"📚 {set_name} ({len(cards)} cards)"):
            # Set stats
            col1, col2, col3 = st.columns(3)
            with col1:
                total_cards = sum(card.get("quantity", 1) for card in cards)
                st.metric("Total Cards", total_cards)
            with col2:
                game = cards[0].get("game", "Unknown") if cards else "Unknown"
                st.metric("Game", game)
            with col3:
                total_value = sum(card.get("price_usd", 0) * card.get("quantity", 1) for card in cards)
                st.metric("Total Value", f"${total_value:.2f}")
            
            # Render cards in compact grid
            render_collection_grid(cards, 4, compact=True)

def load_sets_catalog() -> List[Dict]:
    """Load MTG and Pokémon set catalogs from fallback_data CSVs with normalized fields."""
    base_dir = os.path.dirname(__file__)
    mtg_path = os.path.join(base_dir, 'fallback_data', 'MTG', 'mtgsets.csv')
    pkmn_path = os.path.join(base_dir, 'fallback_data', 'Pokemon', 'pokemonsets.csv')

    def normalize_year(value: str) -> str:
        import re as _re
        y = str(value or '').strip()
        m4 = _re.search(r"(19\d{2}|20\d{2})", y)
        if m4:
            return m4.group(1)
        m2 = _re.search(r"(?:^|[^0-9])(\d{1,2})[/-](\d{1,2})[/-](\d{2})(?:[^0-9]|$)", y)
        if m2:
            yy = int(m2.group(3))
            return str(1900 + yy) if yy >= 90 else str(2000 + yy)
        if _re.fullmatch(r"\d{2}", y):
            yy = int(y)
            return str(1900 + yy) if yy >= 90 else str(2000 + yy)
        return y

    sets: List[Dict] = []

    # MTG
    try:
        if os.path.exists(mtg_path):
            with open(mtg_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    rl = { (k or '').lower(): v for k, v in row.items() }
                    set_name = rl.get('set') or rl.get('name') or rl.get('set_name') or rl.get('set name') or ''
                    set_code = rl.get('code') or rl.get('set_code') or rl.get('id') or ''
                    total_cards = (
                        rl.get('printed_size') or rl.get('printedsize') or rl.get('card_count') or rl.get('card count') or rl.get('total') or ''
                    )
                    released = (
                        rl.get('year') or rl.get('released') or rl.get('releasedate') or rl.get('release_date') or rl.get('released_at') or 
                        rl.get('printed') or rl.get('printedat') or rl.get('printed_at') or ''
                    )
                    set_type = (rl.get('set_type') or rl.get('type') or rl.get('settype') or '').strip().lower()
                    digital = str(rl.get('digital') or rl.get('is_digital') or '').strip().lower() in ('1','true','yes')
                    if set_name:
                        sets.append({
                            'game': 'Magic: The Gathering',
                            'set_name': set_name,
                            'released': str(released or ''),
                            'year': normalize_year(released),
                            'set_code': str(set_code or '').strip(),
                            'cards_in_set': str(total_cards or '').strip(),
                            'set_type': set_type,
                            'digital': digital,
                        })
    except Exception:
        pass

    # Pokémon
    try:
        if os.path.exists(pkmn_path):
            with open(pkmn_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    # Case-insensitive row access
                    rl = { (k or '').lower(): v for k, v in row.items() }
                    set_name = rl.get('set') or rl.get('name') or rl.get('set_name') or rl.get('set name') or ''
                    set_code = rl.get('id') or rl.get('code') or rl.get('set_code') or rl.get('set code') or rl.get('ptcgocode') or ''
                    total_cards = rl.get('printedtotal') or rl.get('total') or rl.get('cards') or ''
                    released = (
                        rl.get('year') or rl.get('released') or rl.get('releasedate') or rl.get('release_date') or rl.get('released_at') or 
                        rl.get('printed') or rl.get('printedat') or rl.get('printed_at') or ''
                    )
                    if set_name:
                        sets.append({
                            'game': 'Pokémon',
                            'set_name': set_name,
                            'released': str(released or ''),
                            'year': normalize_year(released),
                            'set_code': str(set_code or '').strip(),
                            'cards_in_set': str(total_cards or '').strip(),
                        })
    except Exception:
        pass

    return sets

def render_card_sets_view():
    """Render the Card Sets page with filters and owned counts."""
    st.title("📚 Card Sets")
    st.caption("Browse available card sets and see how many you own")

    sets = load_sets_catalog()
    if not sets:
        st.info("No sets found in fallback data.")
        return

    # Normalizer used for mapping keys
    def _norm(s: str) -> str:
        import re as _re
        return _re.sub(r"[^a-z0-9]+", "", (s or '').strip().lower())

    # Build cached-card counts per (game, set) and per (game, set_code) from fallback CSVs
    cached_counts: Dict[tuple, int] = {}
    cached_counts_code: Dict[tuple, int] = {}
    try:
        base_dir = os.path.dirname(__file__)
        mtg_cards_path = os.path.join(base_dir, 'fallback_data', 'MTG', 'mtgcards.csv')
        pkmn_cards_path = os.path.join(base_dir, 'fallback_data', 'Pokemon', 'pokemoncards.csv')
        pkmn_sets_path = os.path.join(base_dir, 'fallback_data', 'Pokemon', 'pokemonsets.csv')

        # Build a lookup map for Pokémon set codes -> set names (to recover names if card rows lack them)
        pkmn_setcode_to_name: Dict[str, str] = {}
        try:
            if os.path.exists(pkmn_sets_path):
                with open(pkmn_sets_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        # Case-insensitive access
                        rl = { (k or '').lower(): v for k, v in row.items() }
                        code = (
                            (rl.get('code') or rl.get('set_code') or rl.get('set code') or rl.get('ptcgocode') or rl.get('id') or '').strip()
                        )
                        name = (
                            rl.get('set') or rl.get('name') or rl.get('set_name') or rl.get('set name') or ''
                        )
                        if code and name:
                            pkmn_setcode_to_name[_norm(code)] = name
        except Exception:
            pass

        def _bump(game_label: str, set_name: str):
            if not set_name:
                return
            k = (_norm(game_label), _norm(set_name))
            cached_counts[k] = cached_counts.get(k, 0) + 1

        def _bump_code(game_label: str, set_code: str):
            if not set_code:
                return
            k = (_norm(game_label), _norm(set_code))
            cached_counts_code[k] = cached_counts_code.get(k, 0) + 1

        # MTG
        try:
            if os.path.exists(mtg_cards_path):
                with open(mtg_cards_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        set_name = (
                            row.get('set') or row.get('set_name') or row.get('Set Name') or row.get('name') or ''
                        )
                        set_code = row.get('set_code') or row.get('Set Code') or row.get('code') or ''
                        _bump('Magic: The Gathering', set_name)
                        _bump_code('Magic: The Gathering', set_code)
        except Exception:
            pass

        # Pokémon
        try:
            if os.path.exists(pkmn_cards_path):
                with open(pkmn_cards_path, 'r', encoding='utf-8') as f:
                    reader = csv.DictReader(f)
                    for row in reader:
                        rl = { (k or '').lower(): v for k, v in row.items() }
                        set_name = (
                            rl.get('set') or rl.get('set_name') or rl.get('set name') or rl.get('name') or ''
                        )
                        # Prefer explicit set_code, else derive from id (e.g., base2-58 -> base2)
                        explicit_code = (
                            rl.get('set_code') or rl.get('set code') or rl.get('code') or rl.get('ptcgocode') or ''
                        )
                        id_code = ''
                        raw_id = (rl.get('id') or '').strip()
                        if raw_id and '-' in raw_id:
                            id_code = raw_id.split('-', 1)[0].strip()
                        code_for_row = explicit_code or id_code
                        if not set_name and code_for_row:
                            set_name = pkmn_setcode_to_name.get(_norm(code_for_row), '')
                        # Bump counts
                        _bump('Pokémon', set_name)
                        if code_for_row:
                            _bump_code('Pokémon', code_for_row)
        except Exception:
            pass
    except Exception:
        pass

    # Build owned counts from current collection
    collection = st.session_state.get(SESSION_KEYS["collection"], [])
    owned_unique: Dict[tuple, int] = {}
    owned_qty: Dict[tuple, int] = {}
    for card in collection:
        key = (_norm(card.get('game', '')), _norm(card.get('set', '')))
        owned_unique[key] = owned_unique.get(key, 0) + 1
        owned_qty[key] = owned_qty.get(key, 0) + int(card.get('quantity', 1) or 1)

    # Prepare DataFrame
    df = pd.DataFrame(sets)
    # Add cached card counts per set (prefer matching by set_code if present, else by set_name)
    def _cached_for_row(r: pd.Series) -> int:
        g = _norm(r.get('game', ''))
        sc = _norm(str(r.get('set_code', '') or ''))
        sn = _norm(str(r.get('set_name', '') or ''))
        if sc:
            return cached_counts_code.get((g, sc), 0)
        return cached_counts.get((g, sn), 0)

    df['Cached Cards'] = df.apply(_cached_for_row, axis=1)
    # Derive numeric Cards in Set if present from catalog
    def _to_int(v: str) -> int:
        try:
            s = str(v or '').strip()
            return int(s) if s.isdigit() else 0
        except Exception:
            return 0
    if 'cards_in_set' in df.columns:
        df['Cards in Set'] = df['cards_in_set'].apply(_to_int)
    else:
        df['Cards in Set'] = 0
    df['Owned Unique'] = df.apply(lambda r: owned_unique.get((_norm(r['game']), _norm(r['set_name'])), 0), axis=1)
    df['Owned Qty'] = df.apply(lambda r: owned_qty.get((_norm(r['game']), _norm(r['set_name'])), 0), axis=1)

    # Reorder columns to place 'Cards in Set' before 'Cached Cards' and keep 'Cached Cards' last
    try:
        cols = list(df.columns)
        if 'Cached Cards' in cols:
            cols.remove('Cached Cards')
        # Ensure Cards in Set exists and near the end, just before Cached Cards
        if 'Cards in Set' in cols:
            cols.remove('Cards in Set')
            cols.append('Cards in Set')
        cols.append('Cached Cards')
        # De-duplicate and apply
        seen = set()
        ordered = []
        for c in cols:
            if c in df.columns and c not in seen:
                seen.add(c)
                ordered.append(c)
        df = df[ordered]
    except Exception:
        pass

    # Filters (shared across tabs)
    filt_col1, filt_col2 = st.columns([2, 1])
    with filt_col1:
        search = st.text_input("Search Set Name", key="sets_search")
    with filt_col2:
        owned_only = st.toggle("Owned only", value=False, key="sets_owned_only")

    def render_sets_table(view_df: pd.DataFrame) -> pd.DataFrame:
        local = view_df.copy()
        if owned_only:
            local = local[local['Owned Qty'] > 0]
        if search:
            s = search.strip().lower()
            local = local[local['set_name'].str.lower().str.contains(s, na=False)]
        with st.container():
            try:
                local['_year_num'] = pd.to_numeric(local['year'], errors='coerce')
                local = local.sort_values(by=['_year_num', 'set_name'], ascending=[False, True])
                local = local.drop(columns=['_year_num'])
            except Exception:
                pass
        st.dataframe(
            local.rename(columns={'game': 'Game', 'set_name': 'Set Name', 'released': 'Release Date', 'year': 'Year'}),
            width='stretch',
        )
        return local

    # Helper: fetch and cache a full set by game + code
    def _fetch_and_cache_set(game_label: str, set_code: str) -> bool:
        ok = True
        try:
            if not set_code:
                st.warning("Missing set code for this set; cannot fetch.")
                return False
            # Use already-imported storage helpers from fallback_manager
            # Pokémon
            if game_label == 'Pokémon':
                if not st.session_state.get('pokemontcg_enabled', True):
                    st.warning("Pokémon TCG API is disabled in settings.")
                    return False
                headers = {}
                api_key = os.getenv('POKEMONTCG_API_KEY') or st.session_state.get('pokemontcg_api_key')
                if api_key:
                    headers['X-Api-Key'] = api_key
                base_url = "https://api.pokemontcg.io/v2/cards"
                q = f"set.id:{set_code}"
                page = 1
                pageSize = 250
                total_saved = 0
                pbar = st.progress(0.0, text=f"Fetching Pokémon set {set_code}…")
                while True:
                    resp = requests.get(base_url, params={"q": q, "page": page, "pageSize": pageSize}, headers=headers, timeout=30)
                    resp.raise_for_status()
                    data = resp.json() or {}
                    cards = data.get('data', []) or []
                    if not cards:
                        break
                    for c in cards:
                        try:
                            store_pokemon_card(c)
                            total_saved += 1
                        except Exception:
                            continue
                    total_count = int(data.get('totalCount', 0) or 0)
                    if total_count:
                        pbar.progress(min(1.0, total_saved / total_count), text=f"Saved {total_saved}/{total_count}…")
                    if len(cards) < pageSize:
                        break
                    page += 1
                pbar.empty()
                st.success(f"Saved {total_saved} Pokémon cards for set {set_code} to cache.")
            # MTG
            elif game_label == 'Magic: The Gathering':
                if not st.session_state.get('scryfall_enabled', True):
                    st.warning("Scryfall API is disabled in settings.")
                    return False
                url = "https://api.scryfall.com/cards/search"
                params = {"q": f"e:{set_code}", "unique": "prints"}
                total_saved = 0
                pbar = st.progress(0.0, text=f"Fetching MTG set {set_code}…")
                next_url = url
                next_params = params
                while next_url:
                    resp = requests.get(next_url, params=next_params, timeout=30)
                    resp.raise_for_status()
                    data = resp.json() or {}
                    items = data.get('data', []) or []
                    for c in items:
                        try:
                            store_mtg_card(c)
                            total_saved += 1
                        except Exception:
                            continue
                    if data.get('has_more') and data.get('next_page'):
                        next_url = data.get('next_page')
                        next_params = None
                    else:
                        next_url = None
                    est = max(total_saved, int(data.get('total_cards') or 0))
                    if est:
                        pbar.progress(min(1.0, total_saved / est), text=f"Saved {total_saved}…")
                pbar.empty()
                st.success(f"Saved {total_saved} MTG cards for set {set_code} to cache.")
        except Exception as e:
            st.error(f"Failed to fetch set {set_code}: {e}")
            ok = False
        return ok
    tab_all, tab_mtg, tab_pkmn = st.tabs(["All Sets", "Magic: The Gathering", "Pokémon"])
    with tab_all:
        view_all = render_sets_table(df)
        with st.expander("Actions", expanded=False):
            opts = (view_all[['game','set_name','set_code']].copy().reset_index(drop=True) if not view_all.empty else pd.DataFrame(columns=['game','set_name','set_code']))
            if not opts.empty:
                sel_idx = st.selectbox(
                    "Select a set",
                    options=list(range(len(opts))),
                    format_func=lambda i: f"{opts.iloc[i]['game']} — {opts.iloc[i]['set_name']} ({opts.iloc[i]['set_code'] or 'no code'})"
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("View in Collection", key="btn_view_in_collection_all"):
                        sel = opts.iloc[sel_idx]['set_name']
                        st.session_state[SESSION_KEYS["show_collection_view"]] = True
                        st.session_state[SESSION_KEYS["show_sets_view"]] = False
                        st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                        st.session_state['coll_set_filter'] = sel
                        st.rerun()
                with col_b:
                    if st.button("Download Full Set to Cache", key="btn_download_set_all"):
                        _fetch_and_cache_set(str(opts.iloc[sel_idx]['game']), str(opts.iloc[sel_idx]['set_code'] or ''))
            # Bulk download all visible sets
            stop_on_error_all = st.toggle("Stop on first error", value=False, key="bulk_stop_on_error_all")
            retry_failed_all = st.toggle("Retry failed sets", value=True, key="bulk_retry_failed_all")
            if not opts.empty and st.button("Download ALL Visible Sets to Cache", key="btn_download_all_sets_all"):
                # Filter out rows without a set_code
                rows = opts.copy()
                rows = rows[rows['set_code'].astype(str).str.strip().astype(bool)].reset_index(drop=True)
                total = len(rows)
                if total == 0:
                    st.warning("No sets with codes available to download.")
                else:
                    pbar = st.progress(0.0, text=f"Downloading 0/{total} sets…")
                    processed = 0
                    results: List[Dict[str, Any]] = []
                    for i in range(total):
                        game_label = str(rows.iloc[i]['game'])
                        set_code = str(rows.iloc[i]['set_code'])
                        success = _fetch_and_cache_set(game_label, set_code)
                        if not success and retry_failed_all:
                            time.sleep(1.0)
                            success_retry = _fetch_and_cache_set(game_label, set_code)
                            success = success_retry
                            results.append({"game": game_label, "set_code": set_code, "status": "retried_ok" if success_retry else "failed"})
                        else:
                            results.append({"game": game_label, "set_code": set_code, "status": "ok" if success else "failed"})
                        processed += 1
                        if not success and stop_on_error_all:
                            pbar.progress((i+1)/total, text=f"Stopped on error at {i+1}/{total} sets…")
                            break
                        pbar.progress((i+1)/total, text=f"Downloading {i+1}/{total} sets…")
                    pbar.empty()
                    st.success(f"Finished downloading {processed} set(s) to cache.")
                    # Summary table
                    if results:
                        df_res = pd.DataFrame(results)
                        # Order columns nicely
                        cols = [c for c in ["game", "set_code", "status"] if c in df_res.columns]
                        st.dataframe(df_res[cols], use_container_width=True)
    with tab_mtg:
        # MTG-specific filters
        mtg_df = df[df['game'] == 'Magic: The Gathering'].copy()
        st.subheader("MTG Filters")
        fcol1, fcol2, fcol3, fcol4, fcol5 = st.columns(5)
        with fcol1:
            show_main = st.toggle("Main", value=True, key="mtg_show_main")
            show_commander = st.toggle("Commander", value=True, key="mtg_show_commander")
        with fcol2:
            show_planechase = st.toggle("Planechase", value=True, key="mtg_show_planechase")
            show_prebuilt = st.toggle("Pre-Built", value=True, key="mtg_show_prebuilt")
        with fcol3:
            show_vanguard = st.toggle("Vanguard", value=True, key="mtg_show_vanguard")
            show_other = st.toggle("Other", value=True, key="mtg_show_other")
        with fcol4:
            include_digital = st.toggle("Digital", value=False, key="mtg_include_digital")
        with fcol5:
            hide_token = st.toggle("Hide Token", value=True, key="mtg_hide_token")
            hide_promo = st.toggle("Hide Promo", value=True, key="mtg_hide_promo")
            hide_art = st.toggle("Hide Art Series", value=True, key="mtg_hide_art")

        def _mtg_group(row: pd.Series) -> str:
            stype = str(row.get('set_type', '') or '').lower()
            if 'commander' in stype:
                return 'Commander'
            if 'planechase' in stype:
                return 'Planechase'
            if 'vanguard' in stype:
                return 'Vanguard'
            if any(x in stype for x in ['starter', 'intro', 'theme', 'duel', 'deck', 'precon', 'box']):
                return 'Pre-Built'
            return 'Main'

        try:
            mtg_df['mtg_group'] = mtg_df.apply(_mtg_group, axis=1)
        except Exception:
            mtg_df['mtg_group'] = 'Main'

        # Apply visibility filters
        allowed_groups = set()
        if show_main: allowed_groups.add('Main')
        if show_commander: allowed_groups.add('Commander')
        if show_planechase: allowed_groups.add('Planechase')
        if show_prebuilt: allowed_groups.add('Pre-Built')
        if show_vanguard: allowed_groups.add('Vanguard')
        if show_other: allowed_groups.add('Other')  # reserve in case mapping assigns 'Other' later

        def _keep_row(row: pd.Series) -> bool:
            stype = str(row.get('set_type', '') or '').lower()
            if hide_token and 'token' in stype:
                return False
            if hide_promo and 'promo' in stype:
                return False
            if hide_art and (('memorabilia' in stype) or ('art' in stype)):
                return False
            # digital filter (exclude unless explicitly included)
            if bool(row.get('digital', False)) and not include_digital:
                return False
            grp = row.get('mtg_group') or 'Main'
            if grp not in allowed_groups:
                # allow "Other" bucket for anything unmapped
                return 'Other' in allowed_groups
            return True

        try:
            mtg_df = mtg_df[mtg_df.apply(_keep_row, axis=1)]
        except Exception:
            pass

        view_mtg = render_sets_table(mtg_df)
        with st.expander("Actions", expanded=False):
            opts = (view_mtg[['set_name','set_code']].copy().reset_index(drop=True) if not view_mtg.empty else pd.DataFrame(columns=['set_name','set_code']))
            if not opts.empty:
                sel_idx = st.selectbox(
                    "Select MTG set",
                    options=list(range(len(opts))),
                    format_func=lambda i: f"{opts.iloc[i]['set_name']} ({opts.iloc[i]['set_code'] or 'no code'})"
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("View in Collection", key="btn_view_in_collection_mtg"):
                        sel = opts.iloc[sel_idx]['set_name']
                        st.session_state[SESSION_KEYS["show_collection_view"]] = True
                        st.session_state[SESSION_KEYS["show_sets_view"]] = False
                        st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                        st.session_state['coll_set_filter'] = sel
                        st.rerun()
                with col_b:
                    if st.button("Download Full Set to Cache", key="btn_download_set_mtg"):
                        _fetch_and_cache_set('Magic: The Gathering', str(opts.iloc[sel_idx]['set_code'] or ''))
        # Bulk download for MTG visible sets
        if not view_mtg.empty:
            _mtg_opts = (view_mtg[['set_code']].copy().reset_index(drop=True))
            stop_on_error_mtg = st.toggle("Stop on first error (MTG)", value=False, key="bulk_stop_on_error_mtg")
            retry_failed_mtg = st.toggle("Retry failed sets (MTG)", value=True, key="bulk_retry_failed_mtg")
            if not _mtg_opts.empty and st.button("Download ALL Visible MTG Sets to Cache", key="btn_download_all_sets_mtg"):
                rows = _mtg_opts[_mtg_opts['set_code'].astype(str).str.strip().astype(bool)].reset_index(drop=True)
                total = len(rows)
                if total == 0:
                    st.warning("No MTG sets with codes available to download.")
                else:
                    pbar = st.progress(0.0, text=f"Downloading 0/{total} MTG sets…")
                    processed = 0
                    results: List[Dict[str, Any]] = []
                    for i in range(total):
                        set_code = str(rows.iloc[i]['set_code'])
                        success = _fetch_and_cache_set('Magic: The Gathering', set_code)
                        if not success and retry_failed_mtg:
                            time.sleep(1.0)
                            success_retry = _fetch_and_cache_set('Magic: The Gathering', set_code)
                            success = success_retry
                            results.append({"game": "Magic: The Gathering", "set_code": set_code, "status": "retried_ok" if success_retry else "failed"})
                        else:
                            results.append({"game": "Magic: The Gathering", "set_code": set_code, "status": "ok" if success else "failed"})
                        processed += 1
                        if not success and stop_on_error_mtg:
                            pbar.progress((i+1)/total, text=f"Stopped on error at {i+1}/{total} MTG sets…")
                            break
                        pbar.progress((i+1)/total, text=f"Downloading {i+1}/{total} MTG sets…")
                    pbar.empty()
                    st.success(f"Finished downloading {processed} MTG set(s) to cache.")
                    # Summary table
                    if results:
                        df_res = pd.DataFrame(results)
                        st.dataframe(df_res[["game", "set_code", "status"]], use_container_width=True)
    with tab_pkmn:
        view_pkmn = render_sets_table(df[df['game'] == 'Pokémon'])
        with st.expander("Actions", expanded=False):
            opts = (view_pkmn[['set_name','set_code']].copy().reset_index(drop=True) if not view_pkmn.empty else pd.DataFrame(columns=['set_name','set_code']))
            if not opts.empty:
                sel_idx = st.selectbox(
                    "Select Pokémon set",
                    options=list(range(len(opts))),
                    format_func=lambda i: f"{opts.iloc[i]['set_name']} ({opts.iloc[i]['set_code'] or 'no code'})"
                )
                col_a, col_b = st.columns(2)
                with col_a:
                    if st.button("View in Collection", key="btn_view_in_collection_pkmn"):
                        sel = opts.iloc[sel_idx]['set_name']
                        st.session_state[SESSION_KEYS["show_collection_view"]] = True
                        st.session_state[SESSION_KEYS["show_sets_view"]] = False
                        st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                        st.session_state['coll_set_filter'] = sel
                        st.rerun()
                with col_b:
                    if st.button("Download Full Set to Cache", key="btn_download_set_pkmn"):
                        _fetch_and_cache_set('Pokémon', str(opts.iloc[sel_idx]['set_code'] or ''))
        # Bulk download for Pokémon visible sets
        if not view_pkmn.empty:
            _pk_opts = (view_pkmn[['set_code']].copy().reset_index(drop=True))
            stop_on_error_pkmn = st.toggle("Stop on first error (Pokémon)", value=False, key="bulk_stop_on_error_pkmn")
            retry_failed_pkmn = st.toggle("Retry failed sets (Pokémon)", value=True, key="bulk_retry_failed_pkmn")
            if not _pk_opts.empty and st.button("Download ALL Visible Pokémon Sets to Cache", key="btn_download_all_sets_pkmn"):
                rows = _pk_opts[_pk_opts['set_code'].astype(str).str.strip().astype(bool)].reset_index(drop=True)
                total = len(rows)
                if total == 0:
                    st.warning("No Pokémon sets with codes available to download.")
                else:
                    pbar = st.progress(0.0, text=f"Downloading 0/{total} Pokémon sets…")
                    processed = 0
                    results: List[Dict[str, Any]] = []
                    for i in range(total):
                        set_code = str(rows.iloc[i]['set_code'])
                        success = _fetch_and_cache_set('Pokémon', set_code)
                        if not success and retry_failed_pkmn:
                            time.sleep(1.0)
                            success_retry = _fetch_and_cache_set('Pokémon', set_code)
                            success = success_retry
                            results.append({"game": "Pokémon", "set_code": set_code, "status": "retried_ok" if success_retry else "failed"})
                        else:
                            results.append({"game": "Pokémon", "set_code": set_code, "status": "ok" if success else "failed"})
                        processed += 1
                        if not success and stop_on_error_pkmn:
                            pbar.progress((i+1)/total, text=f"Stopped on error at {i+1}/{total} Pokémon sets…")
                            break
                        pbar.progress((i+1)/total, text=f"Downloading {i+1}/{total} Pokémon sets…")
                    pbar.empty()
                    st.success(f"Finished downloading {processed} Pokémon set(s) to cache.")
                    # Summary table
                    if results:
                        df_res = pd.DataFrame(results)
                        st.dataframe(df_res[["game", "set_code", "status"]], use_container_width=True)

def render_settings_view():
    """Render Settings page for app behavior preferences."""
    st.title("⚙️ Settings")
    st.caption("Configure how adding duplicates behaves and other preferences")

    st.subheader("Duplicate Handling")
    dup_map = {
        "Merge quantities (recommended)": "merge",
        "Keep separate entries (track each purchase)": "separate",
    }
    current = st.session_state.get("duplicate_strategy", "merge")
    choice = st.radio(
        "When adding a card that already exists (same game, name, set, card number, variant):",
        options=list(dup_map.keys()),
        index=0 if current == "merge" else 1,
        help=(
            "Merge: increases Quantity on the existing row and adds the new Paid amount to the existing Paid total.\n"
            "Separate: creates a new row so you can record a distinct Paid amount for each purchase."
        ),
    )
    st.session_state["duplicate_strategy"] = dup_map[choice]
    st.success(f"Duplicate handling set to: {dup_map[choice]}")
    # Additional inline guidance for Paid behavior
    st.caption("• Merge quantities: Paid is accumulated (sum of all adds).")
    st.caption("• Keep separate entries: each row keeps its own Paid value per add.")

def render_statistics_view(collection: List[Dict]):
    """Render detailed collection statistics"""
    st.subheader("📈 Collection Statistics")
    
    # Basic stats
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        total_cards = sum(card.get("quantity", 1) for card in collection)
        st.metric("Total Cards", total_cards)
    with col2:
        unique_cards = len(collection)
        st.metric("Unique Cards", unique_cards)
    with col3:
        total_value = sum(card.get("price_usd", 0) * card.get("quantity", 1) for card in collection)
        st.metric("Total Value", f"${total_value:.2f}")
    with col4:
        avg_value = total_value / total_cards if total_cards > 0 else 0
        st.metric("Avg Value/Card", f"${avg_value:.2f}")
    
    st.divider()
    
    # Game breakdown
    st.subheader("🎮 Game Breakdown")
    games = {}
    for card in collection:
        game = card.get("game", "Unknown")
        if game not in games:
            games[game] = {"count": 0, "value": 0, "cards": []}
        games[game]["count"] += card.get("quantity", 1)
        games[game]["value"] += card.get("price_usd", 0) * card.get("quantity", 1)
        games[game]["cards"].append(card)
    
    # Create game stats table
    game_data = []
    for game, stats in games.items():
        game_data.append({
            "Game": game,
            "Cards": stats["count"],
            "Value": f"${stats['value']:.2f}",
            "Avg Value": f"${stats['value']/stats['count']:.2f}" if stats['count'] > 0 else "$0.00"
        })
    
    if game_data:
        df_games = pd.DataFrame(game_data)
        st.dataframe(df_games, width='stretch')
    
    st.divider()
    
    # Top valuable cards
    st.subheader("💰 Most Valuable Cards")
    sorted_by_value = sorted(collection, key=lambda x: x.get("price_usd", 0), reverse=True)[:10]
    
    if sorted_by_value:
        top_cards_data = []
        for i, card in enumerate(sorted_by_value, 1):
            top_cards_data.append({
                "Rank": i,
                "Name": card.get("name", "Unknown"),
                "Set": f"{card.get('year', '')} {card.get('set', '')}",
                "Price": f"${card.get('price_usd', 0):.2f}",
                "Quantity": card.get("quantity", 1)
            })
        
        df_top = pd.DataFrame(top_cards_data)
        st.dataframe(df_top, width='stretch')
    
    st.divider()
    
    # Collection timeline (recent additions)
    st.subheader("📅 Recent Additions")
    cards_with_date = [card for card in collection if card.get("date_added")]
    recent_cards = sorted(cards_with_date, key=lambda x: x.get("date_added", ""), reverse=True)[:5]
    
    if recent_cards:
        for card in recent_cards:
            date_str = card.get("date_added", "")[:10] if card.get("date_added") else "Unknown"
            st.write(f"**{date_str}** - Added {card.get('quantity', 1)}x {card.get('name', 'Unknown')} ({card.get('year', '')} {card.get('set', '')})")

def render_collection_grid(cards: List[Dict], per_row: int = 3, compact: bool = False):
    """Render collection cards in a grid
    Generates a stable key prefix from the cards to avoid duplicate Streamlit keys across views.
    """
    # Add a per-render counter to guarantee uniqueness across multiple calls on the same page
    counter = st.session_state.get("_grid_render_counter", 0)
    st.session_state["_grid_render_counter"] = counter + 1
    try:
        prefix_seed = tuple((
            c.get('game', ''), c.get('set', ''), c.get('name', ''), c.get('card_number', ''), c.get('variant', '')
        ) for c in cards[:25])
        key_prefix = f"grid_{counter}_{abs(hash(prefix_seed))}"
    except Exception:
        key_prefix = f"grid_{counter}_default"
    for i in range(0, len(cards), per_row):
        cols = st.columns(per_row)
        for j in range(per_row):
            idx = i + j
            if idx >= len(cards):
                break
            
            card = cards[idx]
            with cols[j]:
                # Card header
                if compact:
                    st.write(f"**{card.get('name', 'Unknown')}**")
                    st.caption(f"{card.get('year', '')} {card.get('set', '')} #{card.get('card_number', '')}")
                    st.caption(f"Qty: {card.get('quantity', 1)} | ${card.get('price_usd', 0):.2f}")
                else:
                    st.markdown(f"**{card.get('name', 'Unknown')}**")
                    st.caption(f"{card.get('year', '')} {card.get('set', '')} #{card.get('card_number', '')}")
                    st.caption(f"Team: {card.get('team', '')}")
                    st.caption(f"Variety: {card.get('variety', '')}")
                    st.caption(f"Quantity: {card.get('quantity', 1)}")
                    st.caption(f"Price: ${card.get('price_usd', 0):.2f}")
                    
                    # Image
                    img_url = card.get('image_url', '')
                    if img_url:
                        st.image(img_url, width=150)
                    else:
                        st.image("https://via.placeholder.com/150x210", width=150)
                
                # Actions
                col1, col2 = st.columns(2)
                with col1:
                    if st.button("✏️ Edit", key=f"{key_prefix}_edit_{idx}", width='stretch'):
                        st.info("Edit functionality coming soon!")
                with col2:
                    if st.button("🗑️ Remove", key=f"{key_prefix}_remove_{idx}", width='stretch'):
                        collection = st.session_state.get(SESSION_KEYS["collection"], [])
                        if card in collection:
                            collection.remove(card)
                            st.session_state[SESSION_KEYS["collection"]] = collection
                            
                            # Save to CSV files
                            save_collection_to_csv(collection, "unified_collection.csv")
                            
                            # Also save to game-specific CSV files
                            mtg_cards = [c for c in collection if c.get("game") == "Magic: The Gathering"]
                            pokemon_cards = [c for c in collection if c.get("game") == "Pokémon"]
                            
                            if mtg_cards:
                                save_collection_to_csv(mtg_cards, "mtg_collection.csv")
                            if pokemon_cards:
                                save_collection_to_csv(pokemon_cards, "pokemon_collection.csv")
                            
                            st.success("Card removed from collection!")
                            st.rerun()
                
                if not compact:
                    st.divider()

def render_collection_list(cards: List[Dict]):
    """Render collection cards in a detailed list
    Generates a stable key prefix from the cards to avoid duplicate Streamlit keys across views.
    """
    counter = st.session_state.get("_list_render_counter", 0)
    st.session_state["_list_render_counter"] = counter + 1
    try:
        prefix_seed = tuple((
            c.get('game', ''), c.get('set', ''), c.get('name', ''), c.get('card_number', ''), c.get('variant', '')
        ) for c in cards[:25])
        key_prefix = f"list_{counter}_{abs(hash(prefix_seed))}"
    except Exception:
        key_prefix = f"list_{counter}_default"
    for i, card in enumerate(cards):
        with st.expander(f"{card.get('name', 'Unknown')} - {card.get('year', '')} {card.get('set', '')} #{card.get('card_number', '')} (Qty: {card.get('quantity', 1)})"):
            col1, col2 = st.columns([1, 3])
            
            with col1:
                # Image
                img_url = card.get('image_url', '')
                if img_url:
                    st.image(img_url, width=200)
                else:
                    st.image("https://via.placeholder.com/200x280", width=200)
            
            with col2:
                # Card details
                st.write(f"**Name:** {card.get('name', 'Unknown')}")
                st.write(f"**Game:** {card.get('game', 'Unknown')}")
                # Show Set with tooltip for set_code
                try:
                    _set_name = f"{card.get('year', '')} {card.get('set', '')}".strip()
                    _set_code = card.get('set_code', '').strip()
                    if _set_code:
                        st.markdown(f"**Set:** {_set_name} <span title='Set code: {_set_code}'>🛈</span>", unsafe_allow_html=True)
                    else:
                        st.write(f"**Set:** {_set_name}")
                except Exception:
                    st.write(f"**Set:** {card.get('year', '')} {card.get('set', '')}")
                st.write(f"**Card #:** {card.get('card_number', '')}")
                st.write(f"**Team:** {card.get('team', '')}")
                st.write(f"**Position:** {card.get('position', '')}")
                st.write(f"**Variety:** {card.get('variety', '')}")
                st.write(f"**Quantity:** {card.get('quantity', 1)}")
                st.write(f"**Price:** ${card.get('price_usd', 0):.2f}")
                st.write(f"**Total Value:** ${card.get('price_usd', 0) * card.get('quantity', 1):.2f}")
                st.write(f"**Source:** {card.get('source', 'Unknown')}")
                st.write(f"**Date Added:** {card.get('date_added', 'Unknown')[:10] if card.get('date_added') else 'Unknown'}")
                
                # Actions
                col1, col2, col3 = st.columns(3)
                with col1:
                    if st.button("✏️ Edit Card", key=f"{key_prefix}_edit_{i}"):
                        st.info("Edit functionality coming soon!")
                with col2:
                    if st.button("📋 Duplicate", key=f"{key_prefix}_dup_{i}"):
                        st.info("Duplicate functionality coming soon!")
                with col3:
                    if st.button("🗑️ Remove", key=f"{key_prefix}_remove_{i}"):
                        collection = st.session_state.get(SESSION_KEYS["collection"], [])
                        if card in collection:
                            collection.remove(card)
                            st.session_state[SESSION_KEYS["collection"]] = collection
                            st.success("Card removed from collection!")
                            st.rerun()

def render_baseball_card_grid(cards: List[Dict], per_row: int = 3, image_width: int = CARD_IMAGE_WIDTH):
    """Render baseball cards in a grid layout"""
    for i in range(0, len(cards), per_row):
        cols = st.columns(per_row)
        for j in range(per_row):
            idx = i + j
            if idx >= len(cards):
                break
            
            c = cards[idx]
            with cols[j]:
                st.markdown(f"**{c.get('name', 'Unknown Card')}**")
                st.caption(f"{c.get('year', '')} {c.get('set', '')} #{c.get('card_number', '')}")
                st.caption(f"Team: {c.get('team', '')}")
                st.caption(f"Variety: {c.get('variety', '')}")
                st.caption(f"Price: ${c.get('price_usd', 0):.2f}")
                
                # Image
                img_url = c.get('image_url', '')
                if img_url:
                    render_clickable_image(img_url, image_width)
                else:
                    render_clickable_image("https://via.placeholder.com/200x280", image_width)
                
                # Source
                st.caption(f"📡 Source: {c.get('source', 'Unknown')}")
                
                # Actions
                col1, col2 = st.columns(2)
                with col1:
                    render_add_to_collection_button(c, f"add_{idx}", f"qty_{idx}")
                with col2:
                    render_add_to_watchlist_button(c, f"wl_{idx}")
                
                st.divider()

def main():
    """Main application function"""
    # Set page configuration
    st.set_page_config(
        page_title="Collectibles Manager",
        page_icon="🃏",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    
    # Sidebar
    with st.sidebar:
        st.title("🃏 Collectibles Manager")
        st.markdown("---")
        # Global Owner selector (persists across all pages)
        owners = list_owner_folders()
        if owners:
            try:
                pref = st.session_state.get('current_owner_label') or st.session_state.get('default_owner_label')
            except Exception:
                pref = None
            try:
                idx = owners.index(pref) if pref in owners else 0
            except Exception:
                idx = 0
            prev_owner = st.session_state.get('_prev_current_owner_label')
            sel_owner = st.selectbox("Owner", owners, index=idx, key='current_owner_label')
            if sel_owner != prev_owner:
                st.session_state['_prev_current_owner_label'] = sel_owner
                try:
                    st.success(f"Owner switched to {sel_owner}")
                except Exception:
                    pass
                # Reload data for selected owner and rerun
                try:
                    st.session_state[SESSION_KEYS["collection"]] = load_csv_collections()
                except Exception:
                    pass
                try:
                    st.session_state["watchlist"] = load_watchlist_from_csv()
                except Exception:
                    pass
                st.rerun()
            # Active collection set (profile) selector for this owner
            try:
                active_profile = _get_active_profile_for_owner_label(sel_owner)
            except Exception:
                active_profile = 'default'
            # Discover existing profiles for this owner by scanning the folder
            try:
                coll_dir = get_collections_dir()
                raw_owner = _owner_from_folder_label(sel_owner)
                oid = _sanitize_owner_id(raw_owner)
                profiles = set()
                for fn in os.listdir(os.path.join(coll_dir, sel_owner)):
                    if fn.startswith(f"{oid}-") and fn.endswith("-unified_collection.csv"):
                        middle = fn[len(oid)+1: -len("-unified_collection.csv")]
                        if middle:
                            profiles.add(middle)
                    if fn == f"{oid}-unified_collection.csv":
                        profiles.add('default')
                if not profiles:
                    profiles = {'default'}
            except Exception:
                profiles = {'default'}
            try:
                pidx = list(sorted(profiles)).index(active_profile) if active_profile in profiles else 0
            except Exception:
                pidx = 0
            sel_profile = st.selectbox("Collection Set", list(sorted(profiles)), index=pidx, key='current_owner_profile_label')
            if sel_profile != active_profile:
                _set_active_profile_for_owner_label(sel_owner, _sanitize_profile_id(sel_profile))
                try:
                    st.success(f"Active set switched to {sel_profile}")
                except Exception:
                    pass
                try:
                    st.session_state[SESSION_KEYS["collection"]] = load_csv_collections()
                except Exception:
                    pass
                try:
                    st.session_state["watchlist"] = load_watchlist_from_csv()
                except Exception:
                    pass
                st.rerun()
        else:
            st.info("No owners yet. Create one in Collection Management.")
        
        # Navigation buttons
        st.subheader("📍 Navigation")
        if st.button("🏠 Home", width='stretch'):
            # Reset to home view
            for key in [SESSION_KEYS["show_collection_view"], SESSION_KEYS["show_sets_view"], SESSION_KEYS["show_mtg_sets_view"]]:
                st.session_state[key] = False
            st.session_state["show_settings_view"] = False
            st.session_state["show_help_view"] = False
            st.rerun()
        
        if st.button("💳 My Collection", width='stretch'):
            # Show collection view
            st.session_state[SESSION_KEYS["show_collection_view"]] = True
            st.session_state[SESSION_KEYS["show_sets_view"]] = False
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = False
            st.session_state["show_help_view"] = False
            st.rerun()
        
        if st.button("📚 Card Sets", width='stretch'):
            # Show sets view
            st.session_state[SESSION_KEYS["show_collection_view"]] = False
            st.session_state[SESSION_KEYS["show_sets_view"]] = True
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = False
            st.session_state["show_help_view"] = False
            st.rerun()
        
        if st.button("⚙️ Settings", width='stretch'):
            # Show settings view
            st.session_state[SESSION_KEYS["show_collection_view"]] = False
            st.session_state[SESSION_KEYS["show_sets_view"]] = False
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = True
            st.session_state["show_help_view"] = False
            st.rerun()
        if st.button("❓ Help", width='stretch'):
            # Show help view
            st.session_state[SESSION_KEYS["show_collection_view"]] = False
            st.session_state[SESSION_KEYS["show_sets_view"]] = False
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = False
            st.session_state["show_help_view"] = True
            st.rerun()
        
        st.markdown("---")
        
        # API Sources expander
        with st.expander("API Sources", expanded=False):
            # Pokemon sources
            st.subheader("🎮 Pokémon")
            st.write("**Pokémon TCG API** (Requires API Key)")
            pokemon_enabled = st.toggle("Enable Pokémon TCG", value=st.session_state.get("pokemontcg_enabled", False), key="pokemontcg_enabled")
            if pokemon_enabled:
                api_key = get_secret("POKEMONTCG_API_KEY")
                if api_key:
                    st.success("✅ Pokémon API key configured")
                else:
                    st.error("❌ Pokémon API key missing")
                    st.code("POKEMONTCG_API_KEY = 'your_key_here'")
            st.caption("Official Pokémon TCG database with pricing")
            
            st.write("**JustTCG API** (Requires API Key)")
            justtcg_enabled = st.toggle("Enable JustTCG", value=st.session_state.get("justtcg_enabled", False), key="justtcg_enabled")
            if justtcg_enabled:
                api_key = get_secret("JUSTTCG_API_KEY")
                if api_key:
                    st.success("✅ JustTCG API key configured")
                else:
                    st.error("❌ JustTCG API key missing")
                    st.code("JUSTTCG_API_KEY = 'your_key_here'")
            st.caption("Multi-TCG pricing database - supports Pokémon, MTG, and more")
            
            # MTG sources
            st.subheader("🧙 Magic: The Gathering")
            st.write("**Scryfall API** (Free)")
            scryfall_enabled = st.toggle("Enable Scryfall", value=st.session_state.get("scryfall_enabled", True), key="scryfall_enabled")
            st.caption("Free Magic card database with images and pricing")
            
            # Baseball sources
            st.subheader("⚾ Baseball Cards")
            st.write("🗃️ **SportsCardDatabase.com** (Free)")
            sportscarddatabase_enabled = st.toggle("Enable SportsCardDatabase", value=st.session_state.get("sportscarddatabase_enabled", True), key="sportscarddatabase_enabled")
            st.caption("Free baseball card database with comprehensive collection")
            
            st.write("📊 **SportCardsPro.com** (Free - Temporarily Disabled)")
            sportscardspro_enabled = st.toggle("Enable SportCardsPro", value=False, key="sportscardspro_enabled", disabled=True)
            st.caption("⚠️ Temporarily disabled - site is blocking automated requests")
            
            st.write("🛒 **eBay** (Requires API Key)")
            ebay_enabled = st.toggle("Enable eBay", value=st.session_state.get("ebay_enabled", True), key="ebay_enabled")
            if ebay_enabled:
                # Production vs Sandbox selection
                prod_key = get_secret("EBAY_APP_ID")
                sandbox_key = get_secret("EBAY_APP_ID_SBX")
                
                if prod_key and sandbox_key:
                    st.write("**eBay Environment:**")
                    ebay_env = st.radio(
                        "Choose eBay Environment",
                        ["Production", "Sandbox"],
                        index=1 if "SBX" in str(st.session_state.get("last_ebay_env", "Sandbox")) else 0,
                        horizontal=True,
                        key="ebay_environment",
                        help="Production uses real eBay data, Sandbox uses test data"
                    )
                    st.session_state["last_ebay_env"] = ebay_env
                    
                    if ebay_env == "Production":
                        st.success("✅ Production API configured")
                        st.caption("🚀 Using real eBay marketplace data")
                    else:
                        st.info("🧪 Sandbox API configured")
                        st.caption("🧪 Using eBay test environment (mock data)")
                        
                elif prod_key:
                    st.success("✅ Production API key configured")
                    st.caption("🚀 Using real eBay marketplace data")
                    st.session_state["last_ebay_env"] = "Production"
                elif sandbox_key:
                    st.info("🧪 Sandbox API key configured")
                    st.caption("🧪 Using eBay test environment (mock data)")
                    st.session_state["last_ebay_env"] = "Sandbox"
                else:
                    st.error("❌ eBay API key missing in .streamlit/secrets.toml")
                    st.code("EBAY_APP_ID = 'your_production_key_here'")
                    st.code("EBAY_APP_ID_SBX = 'your_sandbox_key_here'")
            st.caption("eBay marketplace for baseball cards with real listings")
            
            # Debug information
            if st.session_state.get("debug_mode", False):
                st.divider()
                st.write("**🔍 Debug - Current Toggle Values:**")
                st.write(f"- Pokémon TCG API: {st.session_state.get('pokemontcg_enabled', 'NOT SET')}")
                st.write(f"- JustTCG API: {st.session_state.get('justtcg_enabled', 'NOT SET')}")
                st.write(f"- Scryfall API: {st.session_state.get('scryfall_enabled', 'NOT SET')}")
                st.write(f"- SportsCardDatabase: {st.session_state.get('sportscarddatabase_enabled', 'NOT SET')}")
                st.write(f"- eBay: {st.session_state.get('ebay_enabled', 'NOT SET')}")
                st.write(f"- eBay Environment: {st.session_state.get('last_ebay_env', 'NOT SET')}")
        
        # Debug Options
        with st.expander("Debug Options", expanded=False):
            debug_mode = st.toggle("🐛 Debug Mode", value=False, key=SESSION_KEYS["debug_mode"], help="Enable debug output for troubleshooting")
            st.caption("Show detailed search process and API call information")
    
    # Main content area
    # Handle different views
    if st.session_state.get(SESSION_KEYS["show_collection_view"]):
        render_collection_view()
    elif st.session_state.get(SESSION_KEYS["show_sets_view"]):
        render_card_sets_view()
    elif st.session_state.get(SESSION_KEYS["show_mtg_sets_view"]):
        st.title("📚 MTG Sets")
        st.caption("Browse Magic: The Gathering sets")
        st.info("🚧 MTG Sets view coming soon!")
    elif st.session_state.get("show_settings_view", False):
        render_settings_view()
    elif st.session_state.get("show_help_view", False):
        render_help_view()
    else:
        # Home view
        st.title("🃏 Collectibles Manager")
        st.caption("Search Magic: The Gathering, Pokémon, and Baseball card prices")
        try:
            _owner_badge = st.session_state.get('current_owner_label') or st.session_state.get('default_owner_label')
            if _owner_badge:
                st.caption(f"Owner: {_owner_badge}")
            _set_badge = _get_active_profile_for_owner_label(_owner_badge) if _owner_badge else 'default'
            if _set_badge and _set_badge != 'default':
                st.caption(f"Collection Set: {_set_badge}")
        except Exception:
            pass
        # Global banner + probe only when debug mode is enabled
        if st.session_state.get(SESSION_KEYS["debug_mode"], False):
            try:
                last_evt = st.session_state.get('debug_last_add_event')
                if last_evt:
                    st.info(f"Add Submit processed • {last_evt}")
            except Exception:
                pass
            # Probe: simple form to confirm submit handlers fire in this environment
            with st.form("probe_form_top"):
                probe_col1, probe_col2 = st.columns([3, 1])
                with probe_col1:
                    st.text_input("Probe Text (optional)", key="probe_text", placeholder="Type anything")
                with probe_col2:
                    probe_submit = st.form_submit_button("Probe Submit", use_container_width=True)
                if probe_submit:
                    ts = datetime.now().isoformat(timespec='seconds')
                    st.session_state['probe_ts'] = ts
                    try:
                        st.toast(f"Probe OK @ {ts}", icon="🧪")
                    except Exception:
                        st.success(f"Probe OK @ {ts}")
                    st.info(f"Probe submit fired @ {ts}")
        
        # Game selection at top of home page
        games_list = list(GAMES.values())
        try:
            default_index = games_list.index(st.session_state.get("last_game", games_list[0]))
        except Exception:
            default_index = 0
        game = st.selectbox(
            "Select Game Type",
            options=games_list,
            index=default_index,
            key="game_selection_main"
        )
        st.session_state["last_game"] = game

        # Search form
        with st.form("search_form"):
            col1, col2 = st.columns([3, 1])
            
            with col1:
                if game == "Baseball Cards":
                    player_name = st.text_input("Player Name", placeholder="e.g., Ken Griffey Jr")
                    year = st.text_input("Year", placeholder="e.g., 1989")
                    set_name = st.text_input("Set Name", placeholder="e.g., Topps")
                    card_number = st.text_input("Card Number", placeholder="e.g., 1")
                else:
                    if game == "Magic: The Gathering":
                        mtg_name = st.text_input("Card Name", placeholder="e.g., Black Lotus or 'Black Lotus 233'")
                        left, right = st.columns([1, 2])
                        with left:
                            mtg_number = st.text_input("Set Number (optional)", placeholder="e.g., 233")
                        with right:
                            mtg_set = st.text_input("Set (optional)", placeholder="e.g., Limited Edition Alpha")
                    elif game == "Pokémon":
                        pkmn_name = st.text_input("Card Name", placeholder="e.g., Pikachu")
                        left, right = st.columns([1, 2])
                        with left:
                            pkmn_number = st.text_input("Card Number (optional)", placeholder="e.g., 58")
                        with right:
                            pkmn_set = st.text_input("Set (optional)", placeholder="e.g., Base Set or BASE")
                    else:
                        search_term = st.text_input("Search Term", placeholder="Card search coming soon for other games")
            
            with col2:
                st.write("")  # Spacer
                st.write("")  # Spacer
                submitted = st.form_submit_button("🔍 Search", width='stretch')
        
        # Process search
        if submitted and game == "Baseball Cards":
            if player_name:
                # Check which sources are enabled
                sportscarddatabase_enabled = st.session_state.get("sportscarddatabase_enabled", True)
                sportscardspro_enabled = False  # Temporarily disabled due to 403 errors
                ebay_enabled = st.session_state.get("ebay_enabled", True)
                
                cards_all = []
                source_used = "No Source"
                
                # Try SportsCardDatabase.com first if enabled
                if sportscarddatabase_enabled and not cards_all:
                    with st.spinner(f"🔍 Searching SportsCardDatabase.com for {player_name.strip()}..."):
                        cards, total, api_count, source = search_sportscard_database(
                            player_name.strip(),
                            year=year,
                            set_name=set_name,
                            card_number=card_number
                        )
                        if cards:
                            cards_all = cards
                            source_used = source
                            st.success(f"✅ Found {len(cards)} cards from SportsCardDatabase!")
                
                # Try eBay if enabled and no results yet
                if ebay_enabled and not cards_all:
                    with st.spinner(f"🔍 Searching eBay for {player_name.strip()}..."):
                        cards, total, api_count, source = baseball_search_ebay(
                            player_name.strip(),
                            year=year,
                            team="",  # Could add team field later
                            set_name=set_name,
                            card_number=card_number
                        )
                        if cards:
                            cards_all = cards
                            source_used = source
                            st.success(f"✅ Found {len(cards)} cards from eBay!")
                
                # Display results or no results message
                if cards_all:
                    st.success(f"🎉 Total: Found {len(cards_all)} cards from {source_used}")
                    
                    # View options
                    col1, col2, col3 = st.columns(3)
                    with col1:
                        cards_per_row = st.slider("Cards per Row", 1, 6, st.session_state.get("cards_per_row", 3))
                    with col2:
                        image_width = st.slider("Image Width", 100, 400, st.session_state.get("image_width", CARD_IMAGE_WIDTH))
                    with col3:
                        view_mode = st.selectbox("View Mode", ["Grid", "List"], index=0)
                    
                    # Render cards
                    if view_mode == "Grid":
                        render_baseball_card_grid(cards_all, per_row=cards_per_row, image_width=image_width)
                    else:
                        # List view (simplified)
                        for i, card in enumerate(cards_all):
                            with st.expander(f"{card['name']} - {card['year']} {card['set']} #{card['card_number']}"):
                                col1, col2 = st.columns([1, 2])
                                with col1:
                                    if card.get('image_url'):
                                        st.image(card['image_url'], width=200)
                                with col2:
                                    st.write(f"**Player:** {card['name']}")
                                    st.write(f"**Set:** {card['year']} {card['set']}")
                                    st.write(f"**Card #:** {card['card_number']}")
                                    st.write(f"**Team:** {card['team']}")
                                    st.write(f"**Variety:** {card['variety']}")
                                    st.write(f"**Price:** ${card['price_usd']:.2f}")
                                    st.write(f"**Source:** {card['source']}")
                                    
                                    # Actions
                                    render_add_to_collection_button(card, f"list_add_{i}", f"list_qty_{i}")
                                    render_add_to_watchlist_button(card, f"list_wl_{i}")
                else:
                    st.warning("❌ No baseball card sources enabled or no results found")
                    st.info("💡 Please enable at least one baseball card source in API Sources settings")
            else:
                st.error("❌ Please enter a player name to search")
        elif submitted and game == "Magic: The Gathering":
            # MTG search: fallback-first from local CSV, with option to refresh via Scryfall
            if 'mtg_name' in locals() and str(mtg_name).strip():
                query_name = mtg_name.strip()
                query_set = mtg_set.strip() if 'mtg_set' in locals() and mtg_set else ""
                # Determine collector number: prefer explicit field, else parse trailing integer from name
                collector_number = ""
                if 'mtg_number' in locals() and str(mtg_number).strip():
                    collector_number = str(mtg_number).strip()
                else:
                    try:
                        import re as _re
                        m = _re.search(r"\b(\d+[a-zA-Z]?)\b$", query_name)
                        if m:
                            collector_number = m.group(1)
                            query_name = query_name[: m.start()].strip()
                    except Exception:
                        pass

                # Try local fallback first
                local_cards = find_mtg_cards_local(query_name, set_hint=query_set, collector_number=collector_number)
                force_api = False
                if local_cards:
                    try:
                        last_upd = local_cards[0].get('updated_at') or 'unknown'
                        st.toast(f"Using local data — Last updated {last_upd}", icon="💾")
                    except Exception:
                        pass
                    cols = st.columns([1,3])
                    with cols[0]:
                        force_api = st.button("Refresh from API", key="mtg_refresh_api")
                    if not force_api:
                        st.session_state["mtg_last_results"] = local_cards
                        st.session_state["mtg_results_visible"] = True
                        render_mtg_search_results(local_cards)
                        return

                with st.spinner(f"🔍 Searching Scryfall for {query_name}..."):
                    cards, total, _, source = search_mtg_scryfall(query_name, set_hint=query_set, collector_number=collector_number)
                st.write(f"Found {total} cards from {source}")
                if cards:
                    # Persist results so they remain visible after other form submissions
                    st.session_state["mtg_last_results"] = cards
                    st.session_state["mtg_results_visible"] = True
                    render_mtg_search_results(cards)
                else:
                    st.info("No results found.")
            else:
                st.error("❌ Please enter a card name to search")
        # Support a refresh-triggered Pokémon API search even when the form isn't re-submitted
        if st.session_state.get("pk_force_refresh"):
            try:
                rq = st.session_state.pop("pk_force_refresh") or {}
                qn = rq.get("name", "").strip()
                qs = rq.get("set", "").strip()
                qnum = rq.get("number", "").strip()
                if qn:
                    with st.spinner(f"🔄 Refreshing from Pokémon TCG for {qn}..."):
                        cards, total, _, source = search_pokemon_tcg(qn, set_hint=qs, number=qnum)
                    st.write(f"Found {total} cards from {source}")
                    if cards:
                        st.session_state["pkmn_last_results"] = cards
                        st.session_state["pkmn_results_visible"] = True
                        render_pokemon_search_results(cards)
                    else:
                        st.info("No results found from API.")
            except Exception as _e:
                st.error(f"Refresh failed: {_e}")
        elif submitted and game == "Pokémon":
            # Pokémon search: fallback-first from local CSV, with option to refresh via API
            if 'pkmn_name' in locals() and str(pkmn_name).strip():
                query_name = pkmn_name.strip()
                query_set = pkmn_set.strip() if 'pkmn_set' in locals() and pkmn_set else ""
                query_number = pkmn_number.strip() if 'pkmn_number' in locals() and pkmn_number else ""

                # Try local fallback first
                local_cards_raw = find_pokemon_cards_local(query_name, set_hint=query_set, number=query_number)
                force_api = False
                if local_cards_raw:
                    # Normalize local raw cards into UI cards (mirroring API normalization)
                    norm_cards = []
                    for c in local_cards_raw:
                        try:
                            set_obj = c.get("set", {}) or {}
                            set_name = set_obj.get("name", "")
                            set_code = (set_obj.get("id") or "").upper()
                            released = set_obj.get("releaseDate", "")
                            year = (str(released)[:4] if released else "")
                            imgs = (c.get("images") or {})
                            img_url = imgs.get("small") or imgs.get("large") or ""
                            link = ( (c.get("tcgplayer") or {}).get("url")
                                     or (c.get("cardmarket") or {}).get("url")
                                     or f"https://pokemontcg.io/card/{c.get('id','')}")
                            prices = ((c.get("tcgplayer") or {}).get("prices") or {})
                            def _g(pr, k):
                                try:
                                    return float((pr or {}).get(k) or 0)
                                except Exception:
                                    return 0.0
                            market_price = 0.0
                            prices_map = {}
                            for k in [
                                "normal",
                                "holofoil",
                                "reverseHolofoil",
                                "1stEditionHolofoil",
                                "1stEdition",
                                "unlimited",
                                "unlimitedHolofoil",
                            ]:
                                p = prices.get(k) or {}
                                low_v = _g(p, 'low'); mid_v = _g(p, 'mid'); mkt_v = _g(p, 'market')
                                if any([low_v, mid_v, mkt_v]):
                                    prices_map[k] = {"low": low_v, "mid": mid_v, "market": mkt_v}
                                    market_price = mkt_v or market_price
                            card = {
                                "game": "Pokémon",
                                "name": c.get("name", ""),
                                "set": set_name,
                                "set_code": set_code,
                                "year": year,
                                "card_number": c.get("number", ""),
                                "image_url": img_url,
                                "link": link,
                                "price_usd": market_price,
                                "quantity": 1,
                                "variety": "",
                                "prices_map": prices_map,
                                "source": "Local Fallback"
                            }
                            norm_cards.append(card)
                        except Exception:
                            continue
                    # Toast with last updated date from set.updatedAt if available
                    try:
                        last_upd = (local_cards_raw[0].get('set') or {}).get('updatedAt') or 'unknown'
                        st.toast(f"Using local data — Last updated {last_upd}", icon="💾")
                    except Exception:
                        pass
                    # Provide a refresh button to force API update
                    cols = st.columns([1,3])
                    with cols[0]:
                        force_api = st.button("Refresh from API", key="pk_refresh_api")
                    if not force_api and norm_cards:
                        st.session_state["pkmn_last_results"] = norm_cards
                        st.session_state["pkmn_results_visible"] = True
                        render_pokemon_search_results(norm_cards)
                        # Short-circuit normal API call
                        return
                    elif force_api:
                        # Trigger a refresh-run with the same query using session state, then rerun
                        st.session_state["pk_force_refresh"] = {"name": query_name, "set": query_set, "number": query_number}
                        st.rerun()

                # Either no local results or user requested refresh -> call API
                with st.spinner(f"🔍 Searching Pokémon TCG for {query_name}..."):
                    cards, total, _, source = search_pokemon_tcg(query_name, set_hint=query_set, number=query_number)
                st.write(f"Found {total} cards from {source}")
                if cards:
                    st.session_state["pkmn_last_results"] = cards
                    st.session_state["pkmn_results_visible"] = True
                    render_pokemon_search_results(cards)
                else:
                    st.info("No results found.")
            else:
                st.error("❌ Please enter a card name to search")
        elif submitted and (game not in ["Baseball Cards", "Magic: The Gathering", "Pokémon"]):
            st.info(f"🚧 {game} search is coming soon! Please use Baseball Cards, Magic: The Gathering, or Pokémon for now.")
        
        # When not actively submitting search, keep showing last MTG results if available
        if not submitted and st.session_state.get("mtg_results_visible") and st.session_state.get("mtg_last_results"):
            render_mtg_search_results(st.session_state.get("mtg_last_results", []))
        if not submitted and st.session_state.get("pkmn_results_visible") and st.session_state.get("pkmn_last_results"):
            render_pokemon_search_results(st.session_state.get("pkmn_last_results", []))
        elif not submitted:
            # Welcome message when no search and no results to show
            collection = st.session_state.get(SESSION_KEYS["collection"], [])
            if collection:
                st.info("👋 Welcome back! You have cards in your collection. Use the sidebar to view them or search for more cards.")
                
                # Show recent collection stats
                col1, col2, col3 = st.columns(3)
                with col1:
                    st.metric("Collection Size", len(collection))
                with col2:
                    games = set(card.get("game", "Unknown") for card in collection)
                    st.metric("Games", len(games))
                with col3:
                    total_value = sum(card.get("price_usd", 0) for card in collection)
                    st.metric("Total Value", f"${total_value:.2f}")
            else:
                st.info("👋 Welcome to the Collectibles Manager! Use the search form above to find cards and build your collection.")

if __name__ == "__main__":
    main()
