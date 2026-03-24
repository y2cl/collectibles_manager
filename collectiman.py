import os
import io
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

# Initialize session state defaults
def load_csv_collections():
    """Load collections from CSV files in the collections folder"""
    collections = []
    coll_dir = get_collections_dir()
    
    # Load MTG collection
    try:
        mtg_file = os.path.join(coll_dir, "mtg_collection.csv")
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
        pokemon_file = os.path.join(coll_dir, "pokemon_collection.csv")
        unified_file = os.path.join(coll_dir, "unified_collection.csv")
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
    
    # Optionally merge unified collection (without duplicating existing by game)
    try:
        if os.path.exists(unified_file):
            with open(unified_file, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    if row.get('name'):
                        card = {
                            "game": row.get('game', ''),
                            "name": row.get('name', ''),
                            "set": row.get('set', ''),
                            "link": row.get('link', ''),
                            "image_url": row.get('image_url', ''),
                            "price_usd": float(row.get('price_usd', 0)) if row.get('price_usd') else 0,
                            "price_usd_foil": float(row.get('price_usd_foil', 0)) if row.get('price_usd_foil') else 0,
                            "price_usd_etched": float(row.get('price_usd_etched', 0)) if row.get('price_usd_etched') else 0,
                            "quantity": int(row.get('quantity', 1)) if row.get('quantity') else 1,
                            "variant": row.get('variant', ''),
                            "date_added": row.get('timestamp', ''),
                            "card_number": row.get('card_number', ''),
                            "year": row.get('year', ''),
                            "paid": float(str(row.get('paid','')).replace('$','').replace(',','')) if str(row.get('paid','')).strip() else 0.0,
                            "source": "CSV Collection"
                        }
                        # Normalize fields
                        card.setdefault("team", "")
                        card.setdefault("position", "")
                        # Avoid duplicate exact records
                        key = (card["game"], card["name"], card["set"], card["variant"], card.get("card_number", ""))
                        existing_keys = set(
                            (c.get("game"), c.get("name"), c.get("set"), c.get("variant"), c.get("card_number", ""))
                            for c in collections
                        )
                        if key not in existing_keys:
                            collections.append(card)
            print(f"✅ Merged unified collection CSV")
    except Exception as e:
        print(f"❌ Error merging unified collection: {e}")

    return collections

def load_watchlist_from_csv(filename: str = "watchlist.csv") -> List[Dict]:
    """Load watchlist items from collections/watchlist.csv."""
    items: List[Dict] = []
    try:
        coll_dir = get_collections_dir()
        filepath = os.path.join(coll_dir, filename)
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
        filepath = os.path.join(coll_dir, filename)
        # Define CSV headers
        headers = [
            'game', 'name', 'set', 'card_number', 'year', 'link', 'image_url', 'price_low', 'price_mid', 'price_market',
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
        filepath = os.path.join(coll_dir, filename)
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
                    if (existing.get("name") == card_copy.get("name") and 
                        existing.get("set") == card_copy.get("set") and
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
                
                # Save to CSV files
                save_collection_to_csv(collection, "unified_collection.csv")
                
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
        if prices.get("low") is not None:
            variants.append("normal")
            selected_prices["normal"] = prices["low"]
        if prices.get("holo") is not None:
            variants.append("holo")
            selected_prices["holo"] = prices["holo"]
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
            except Exception:
                continue
        return cards, len(cards), len(items), "Scryfall"
    except Exception as e:
        return [], 0, 0, f"Scryfall Error: {str(e)}"

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
    
    collection_all = st.session_state.get(SESSION_KEYS["collection"], [])
    if not collection_all:
        st.info("📝 Your collection is empty. Start searching for cards to add them to your collection!")
        if st.button("🔍 Start Searching"):
            for key in [SESSION_KEYS["show_collection_view"], SESSION_KEYS["show_sets_view"], SESSION_KEYS["show_mtg_sets_view"]]:
                st.session_state[key] = False
            st.rerun()
        return
    
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
    
    # Primary tabs in order: Collection, Gallery View, Investment, Watchlist
    tab_coll, tab_gallery, tab_invest, tab_watch = st.tabs(["🗂️ Collection", "🖼️ Gallery View", "📈 Investment", "⭐ Watchlist"])
    
    with tab_coll:
        render_collection_tab(collection)
    with tab_gallery:
        render_gallery_view_tab(collection)
    with tab_invest:
        render_investment_tab(collection)
    with tab_watch:
        render_watchlist_tab()

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
                    set_name = row.get('set') or row.get('name') or row.get('Name') or row.get('set_name') or row.get('Set Name') or ''
                    released = (
                        row.get('year') or row.get('released') or row.get('releaseDate') or row.get('release_date') or row.get('released_at') or 
                        row.get('printed') or row.get('printedAt') or row.get('printed_at') or ''
                    )
                    if set_name:
                        sets.append({
                            'game': 'Magic: The Gathering',
                            'set_name': set_name,
                            'released': str(released or ''),
                            'year': normalize_year(released),
                        })
    except Exception:
        pass

    # Pokémon
    try:
        if os.path.exists(pkmn_path):
            with open(pkmn_path, 'r', encoding='utf-8') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    set_name = row.get('set') or row.get('name') or row.get('Name') or row.get('set_name') or row.get('Set Name') or ''
                    released = (
                        row.get('year') or row.get('released') or row.get('releaseDate') or row.get('release_date') or row.get('released_at') or 
                        row.get('printed') or row.get('printedAt') or row.get('printed_at') or ''
                    )
                    if set_name:
                        sets.append({
                            'game': 'Pokémon',
                            'set_name': set_name,
                            'released': str(released or ''),
                            'year': normalize_year(released),
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

    # Build owned counts from current collection
    collection = st.session_state.get(SESSION_KEYS["collection"], [])
    def _norm(s: str) -> str:
        import re as _re
        return _re.sub(r"[^a-z0-9]+", "", (s or '').strip().lower())

    owned_unique: Dict[tuple, int] = {}
    owned_qty: Dict[tuple, int] = {}
    for card in collection:
        key = (_norm(card.get('game', '')), _norm(card.get('set', '')))
        owned_unique[key] = owned_unique.get(key, 0) + 1
        owned_qty[key] = owned_qty.get(key, 0) + int(card.get('quantity', 1) or 1)

    # Prepare DataFrame
    df = pd.DataFrame(sets)
    df['Owned Unique'] = df.apply(lambda r: owned_unique.get((_norm(r['game']), _norm(r['set_name'])), 0), axis=1)
    df['Owned Qty'] = df.apply(lambda r: owned_qty.get((_norm(r['game']), _norm(r['set_name'])), 0), axis=1)

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

    tab_all, tab_mtg, tab_pkmn = st.tabs(["All Sets", "Magic: The Gathering", "Pokémon"])
    with tab_all:
        view_all = render_sets_table(df)
        with st.expander("Actions", expanded=False):
            opts = sorted(view_all['set_name'].dropna().unique().tolist()) if not view_all.empty else []
            sel = st.selectbox("Select a set to view in Collection", options=opts, key="sets_action_all") if opts else None
            if opts and st.button("View in Collection", key="btn_view_in_collection_all"):
                st.session_state[SESSION_KEYS["show_collection_view"]] = True
                st.session_state[SESSION_KEYS["show_sets_view"]] = False
                st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                st.session_state['coll_set_filter'] = sel
                st.rerun()
    with tab_mtg:
        view_mtg = render_sets_table(df[df['game'] == 'Magic: The Gathering'])
        with st.expander("Actions", expanded=False):
            opts = sorted(view_mtg['set_name'].dropna().unique().tolist()) if not view_mtg.empty else []
            sel = st.selectbox("Select a set to view in Collection", options=opts, key="sets_action_mtg") if opts else None
            if opts and st.button("View in Collection", key="btn_view_in_collection_mtg"):
                st.session_state[SESSION_KEYS["show_collection_view"]] = True
                st.session_state[SESSION_KEYS["show_sets_view"]] = False
                st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                st.session_state['coll_set_filter'] = sel
                st.rerun()
    with tab_pkmn:
        view_pkmn = render_sets_table(df[df['game'] == 'Pokémon'])
        with st.expander("Actions", expanded=False):
            opts = sorted(view_pkmn['set_name'].dropna().unique().tolist()) if not view_pkmn.empty else []
            sel = st.selectbox("Select a set to view in Collection", options=opts, key="sets_action_pkmn") if opts else None
            if opts and st.button("View in Collection", key="btn_view_in_collection_pkmn"):
                st.session_state[SESSION_KEYS["show_collection_view"]] = True
                st.session_state[SESSION_KEYS["show_sets_view"]] = False
                st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
                st.session_state['coll_set_filter'] = sel
                st.rerun()

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
        page_title="TCG Price Tracker",
        page_icon="🃏",
        layout="wide",
        initial_sidebar_state="expanded"
    )
    
    # Initialize session state
    initialize_session_state()
    # Ensure debug visuals are off unless explicitly enabled
    try:
        st.session_state[SESSION_KEYS["debug_mode"]] = False
    except Exception:
        pass
    
    # Sidebar
    with st.sidebar:
        st.title("🃏 TCG Price Tracker")
        st.markdown("---")
        
        # Navigation buttons
        st.subheader("📍 Navigation")
        if st.button("🏠 Home", width='stretch'):
            # Reset to home view
            for key in [SESSION_KEYS["show_collection_view"], SESSION_KEYS["show_sets_view"], SESSION_KEYS["show_mtg_sets_view"]]:
                st.session_state[key] = False
            st.session_state["show_settings_view"] = False
            st.rerun()
        
        if st.button("💳 My Collection", width='stretch'):
            # Show collection view
            st.session_state[SESSION_KEYS["show_collection_view"]] = True
            st.session_state[SESSION_KEYS["show_sets_view"]] = False
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = False
            st.rerun()
        
        if st.button("📚 Card Sets", width='stretch'):
            # Show sets view
            st.session_state[SESSION_KEYS["show_collection_view"]] = False
            st.session_state[SESSION_KEYS["show_sets_view"]] = True
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = False
            st.rerun()
        
        if st.button("⚙️ Settings", width='stretch'):
            # Show settings view
            st.session_state[SESSION_KEYS["show_collection_view"]] = False
            st.session_state[SESSION_KEYS["show_sets_view"]] = False
            st.session_state[SESSION_KEYS["show_mtg_sets_view"]] = False
            st.session_state["show_settings_view"] = True
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
    else:
        # Home view
        st.title("🃏 TCG Price Tracker")
        st.caption("Search Magic: The Gathering, Pokémon, and Baseball card prices")
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
            # MTG search using Scryfall
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
                            # remove trailing number from search name to avoid confusing Scryfall
                            query_name = query_name[: m.start()].strip()
                    except Exception:
                        pass
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
        elif submitted and (game not in ["Baseball Cards", "Magic: The Gathering"]):
            st.info(f"🚧 {game} search is coming soon! Please use Baseball Cards or Magic: The Gathering for now.")
        
        # When not actively submitting search, keep showing last MTG results if available
        if not submitted and st.session_state.get("mtg_results_visible") and st.session_state.get("mtg_last_results"):
            render_mtg_search_results(st.session_state.get("mtg_last_results", []))
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
                st.info("👋 Welcome to the TCG Price Tracker! Use the search form above to find cards and build your collection.")

if __name__ == "__main__":
    main()
