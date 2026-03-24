"""
Fallback Data Manager
Handles building and managing local fallback data for offline functionality.
"""

import os
import csv
import json
import requests
from typing import Dict, List, Optional, Any
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

# Get the script directory for absolute paths
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
FALLBACK_BASE_DIR = os.path.join(SCRIPT_DIR, "fallback_data")

# Fallback data paths (using absolute paths)
POKEMON_DIR = os.path.join(FALLBACK_BASE_DIR, "Pokemon")
MTG_DIR = os.path.join(FALLBACK_BASE_DIR, "MTG")

# CSV file paths
POKEMON_SETS_CSV = os.path.join(POKEMON_DIR, "pokemonsets.csv")
POKEMON_CARDS_CSV = os.path.join(POKEMON_DIR, "pokemoncards.csv")
MTG_SETS_CSV = os.path.join(MTG_DIR, "mtgsets.csv")
MTG_CARDS_CSV = os.path.join(MTG_DIR, "mtgcards.csv")

# Image directories
POKEMON_CARD_IMAGES = os.path.join(POKEMON_DIR, "CardImages")
POKEMON_SET_IMAGES = os.path.join(POKEMON_DIR, "SetImages")
MTG_CARD_IMAGES = os.path.join(MTG_DIR, "CardImages")
MTG_SET_IMAGES = os.path.join(MTG_DIR, "SetImages")

def ensure_directories():
    """Create fallback data directories if they don't exist."""
    dirs = [
        POKEMON_DIR, MTG_DIR,
        POKEMON_CARD_IMAGES, POKEMON_SET_IMAGES,
        MTG_CARD_IMAGES, MTG_SET_IMAGES
    ]
    for dir_path in dirs:
        os.makedirs(dir_path, exist_ok=True)

def download_image(url: str, save_path: str) -> bool:
    """Download an image from URL to save_path. Skips download if file already exists."""
    try:
        # Check if file already exists
        if os.path.exists(save_path):
            size = os.path.getsize(save_path)
            logger.debug(f"Image already exists, skipping download: {save_path} ({size} bytes)")
            return True
        
        # Get absolute path for debugging
        abs_path = os.path.abspath(save_path)
        logger.debug(f"Downloading image from {url} to {abs_path}")
        
        # Ensure directory exists
        dir_path = os.path.dirname(save_path)
        if not os.path.exists(dir_path):
            logger.debug(f"Creating directory: {dir_path}")
            os.makedirs(dir_path, exist_ok=True)
        
        response = requests.get(url, timeout=10)
        response.raise_for_status()
        
        with open(save_path, 'wb') as f:
            f.write(response.content)
        
        # Verify file was created
        if os.path.exists(save_path):
            size = os.path.getsize(save_path)
            logger.debug(f"Successfully downloaded image. Size: {size} bytes")
            return True
        else:
            logger.error(f"File not created after download: {save_path}")
            return False
    except Exception as e:
        logger.warning(f"Failed to download image from {url}: {e}")
        return False

def get_image_filename(url: str, card_id: str) -> str:
    """Generate a safe filename from URL and card ID."""
    # Extract file extension from URL
    ext = url.split('.')[-1] if '.' in url else 'png'
    # Remove any query parameters
    ext = ext.split('?')[0]
    return f"{card_id}.{ext}"

def append_to_csv(csv_path: str, data: Dict[str, Any], fieldnames: List[str]):
    """Append data to CSV file."""
    try:
        # Get absolute path for debugging
        abs_path = os.path.abspath(csv_path)
        logger.debug(f"Appending to CSV at absolute path: {abs_path}")
        
        file_exists = os.path.exists(csv_path)
        logger.debug(f"CSV file exists before write: {file_exists}")
        
        with open(csv_path, 'a', newline='', encoding='utf-8') as csvfile:
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames, 
                                  quoting=csv.QUOTE_ALL, 
                                  escapechar='\\',
                                  doublequote=True)
            if not file_exists:
                writer.writeheader()
            writer.writerow(data)
        
        # Verify file was written
        logger.debug(f"CSV file exists after write: {os.path.exists(csv_path)}")
        if os.path.exists(csv_path):
            size = os.path.getsize(csv_path)
            logger.debug(f"CSV file size after write: {size} bytes")
    except Exception as e:
        logger.error(f"Failed to append to {csv_path}: {e}")
        raise

def store_pokemon_set(set_data: Dict[str, Any]) -> bool:
    """Store Pokemon set data to fallback storage."""
    try:
        fieldnames = ["id", "name", "series", "printedTotal", "total", "legalities", 
                     "ptcgoCode", "releaseDate", "updatedAt", "images", "tcgplayer"]
        
        # Flatten nested objects for CSV storage
        flat_data = {
            "id": set_data.get("id", ""),
            "name": set_data.get("name", ""),
            "series": set_data.get("series", ""),
            "printedTotal": set_data.get("printedTotal", 0),
            "total": set_data.get("total", 0),
            "legalities": json.dumps(set_data.get("legalities", {})),
            "ptcgoCode": set_data.get("ptcgoCode", ""),
            "releaseDate": set_data.get("releaseDate", ""),
            "updatedAt": set_data.get("updatedAt", ""),
            "images": json.dumps(set_data.get("images", {})),
            "tcgplayer": json.dumps(set_data.get("tcgplayer", {}))
        }
        
        append_to_csv(POKEMON_SETS_CSV, flat_data, fieldnames)
        
        # Download set image if available
        images = set_data.get("images", {})
        if images.get("logo"):
            filename = f"{set_data.get('id', 'unknown')}_logo.png"
            save_path = os.path.join(POKEMON_SET_IMAGES, filename)
            download_image(images["logo"], save_path)
        
        return True
    except Exception as e:
        logger.error(f"Failed to store Pokemon set {set_data.get('name', 'unknown')}: {e}")
        return False

def store_pokemon_card(card_data: Dict[str, Any]) -> bool:
    """Store Pokemon card data to fallback storage."""
    try:
        fieldnames = ["id", "name", "supertype", "subtypes", "level", "rules", "hp", 
                     "types", "attacks", "weaknesses", "resistances", "retreatCost", 
                     "convertedRetreatCost", "damage", "ability", "ancientTrait", 
                     "images", "tcgplayer", "nationalPokedexNumbers", "legalities", 
                     "regulationMark", "flavorText", "artist", "rarity", "category", 
                     "number", "illustrationRare"]
        
        # Flatten nested objects for CSV storage
        flat_data = {
            "id": card_data.get("id", ""),
            "name": card_data.get("name", ""),
            "supertype": card_data.get("supertype", ""),
            "subtypes": json.dumps(card_data.get("subtypes", [])),
            "level": card_data.get("level", ""),
            "rules": json.dumps(card_data.get("rules", [])),
            "hp": card_data.get("hp", ""),
            "types": json.dumps(card_data.get("types", [])),
            "attacks": json.dumps(card_data.get("attacks", [])),
            "weaknesses": json.dumps(card_data.get("weaknesses", [])),
            "resistances": json.dumps(card_data.get("resistances", [])),
            "retreatCost": json.dumps(card_data.get("retreatCost", [])),
            "convertedRetreatCost": card_data.get("convertedRetreatCost", 0),
            "damage": card_data.get("damage", ""),
            "ability": json.dumps(card_data.get("ability", {})),
            "ancientTrait": json.dumps(card_data.get("ancientTrait", {})),
            "images": json.dumps(card_data.get("images", {})),
            "tcgplayer": json.dumps(card_data.get("tcgplayer", {})),
            "nationalPokedexNumbers": json.dumps(card_data.get("nationalPokedexNumbers", [])),
            "legalities": json.dumps(card_data.get("legalities", {})),
            "regulationMark": card_data.get("regulationMark", ""),
            "flavorText": card_data.get("flavorText", ""),
            "artist": card_data.get("artist", ""),
            "rarity": card_data.get("rarity", ""),
            "category": card_data.get("category", ""),
            "number": card_data.get("number", ""),
            "illustrationRare": card_data.get("illustrationRare", False)
        }
        
        append_to_csv(POKEMON_CARDS_CSV, flat_data, fieldnames)
        
        # Download card images if available
        images = card_data.get("images", {})
        card_id = card_data.get("id", "unknown")
        
        if images.get("small"):
            filename = get_image_filename(images["small"], card_id + "_small")
            save_path = os.path.join(POKEMON_CARD_IMAGES, filename)
            download_image(images["small"], save_path)
            
        if images.get("large"):
            filename = get_image_filename(images["large"], card_id + "_large")
            save_path = os.path.join(POKEMON_CARD_IMAGES, filename)
            download_image(images["large"], save_path)
        
        return True
    except Exception as e:
        logger.error(f"Failed to store Pokemon card {card_data.get('name', 'unknown')}: {e}")
        return False

def store_mtg_set(set_data: Dict[str, Any]) -> bool:
    """Store MTG set data to fallback storage."""
    try:
        logger.info(f"Attempting to store MTG set: {set_data.get('name', 'unknown')} ({set_data.get('code', 'unknown')})")
        
        fieldnames = ["id", "name", "code", "set_type", "released_at", "digital", 
                     "card_count", "icon_svg_uri", "scryfall_uri", "search_uri", 
                     "uri", "parent_set_code", "foil_only", "object", "nonfoil_only", 
                     "block_code", "tcgplayer_id", "block"]
        
        # Extract all available fields, using None for missing ones
        flat_data = {}
        for field in fieldnames:
            flat_data[field] = set_data.get(field)
        
        logger.debug(f"MTG set data prepared: {flat_data}")
        append_to_csv(MTG_SETS_CSV, flat_data, fieldnames)
        logger.info(f"Successfully stored MTG set to CSV: {set_data.get('name', 'unknown')}")
        
        # Download set icon if available
        if set_data.get("icon_svg_uri"):
            filename = f"{set_data.get('code', 'unknown')}_icon.svg"
            save_path = os.path.join(MTG_SET_IMAGES, filename)
            logger.debug(f"Downloading set icon: {filename}")
            if download_image(set_data["icon_svg_uri"], save_path):
                logger.info(f"Successfully downloaded set icon: {filename}")
            else:
                logger.warning(f"Failed to download set icon: {filename}")
        
        return True
    except Exception as e:
        logger.error(f"Failed to store MTG set {set_data.get('name', 'unknown')}: {e}")
        return False

def store_mtg_card(card_data: Dict[str, Any]) -> bool:
    """Store MTG card data to fallback storage."""
    try:
        fieldnames = ["id", "name", "set_name", "set_code", "collector_number", "type_line", 
                     "mana_cost", "cmc", "rarity", "oracle_text", "colors", "color_identity", 
                     "legalities", "prices_usd", "prices_usd_foil", "prices_usd_etched", 
                     "image_uris_small", "image_uris_normal", "image_uris_large", "artist", 
                     "illustration_id", "layout", "full_art", "textless", "booster", 
                     "story_spotlight", "preview", "printed_name", "power", "toughness", 
                     "flavor_text", "card_back_id", "artist_ids", "watermark", "frame", 
                     "frame_effects", "security_stamp", "finishes", "oversized", "promo", 
                     "reprint", "variation", "language", "set_uri", "scryfall_uri", 
                     "object", "created_at", "updated_at"]
        
        # Flatten nested objects for CSV storage
        flat_data = {
            "id": card_data.get("id", ""),
            "name": card_data.get("name", ""),
            "set_name": card_data.get("set_name", ""),
            "set_code": card_data.get("set", ""),
            "collector_number": card_data.get("collector_number", ""),
            "type_line": card_data.get("type_line", ""),
            "mana_cost": card_data.get("mana_cost", ""),
            "cmc": card_data.get("cmc", 0),
            "rarity": card_data.get("rarity", ""),
            "oracle_text": card_data.get("oracle_text", ""),
            "colors": json.dumps(card_data.get("colors", [])),
            "color_identity": json.dumps(card_data.get("color_identity", [])),
            "legalities": json.dumps(card_data.get("legalities", {})),
            "prices_usd": card_data.get("prices", {}).get("usd"),
            "prices_usd_foil": card_data.get("prices", {}).get("usd_foil"),
            "prices_usd_etched": card_data.get("prices", {}).get("usd_etched"),
            "image_uris_small": card_data.get("image_uris", {}).get("small"),
            "image_uris_normal": card_data.get("image_uris", {}).get("normal"),
            "image_uris_large": card_data.get("image_uris", {}).get("large"),
            "artist": card_data.get("artist", ""),
            "illustration_id": card_data.get("illustration_id", ""),
            "layout": card_data.get("layout", ""),
            "full_art": card_data.get("full_art", False),
            "textless": card_data.get("textless", False),
            "booster": card_data.get("booster", False),
            "story_spotlight": card_data.get("story_spotlight", False),
            "preview": card_data.get("preview", False),
            "printed_name": card_data.get("printed_name", ""),
            "power": card_data.get("power", ""),
            "toughness": card_data.get("toughness", ""),
            "flavor_text": card_data.get("flavor_text", ""),
            "card_back_id": card_data.get("card_back_id", ""),
            "artist_ids": json.dumps(card_data.get("artist_ids", [])),
            "watermark": card_data.get("watermark", ""),
            "frame": card_data.get("frame", ""),
            "frame_effects": json.dumps(card_data.get("frame_effects", [])),
            "security_stamp": card_data.get("security_stamp", ""),
            "finishes": json.dumps(card_data.get("finishes", [])),
            "oversized": card_data.get("oversized", False),
            "promo": card_data.get("promo", False),
            "reprint": card_data.get("reprint", False),
            "variation": card_data.get("variation", False),
            "language": card_data.get("lang", "en"),
            "set_uri": card_data.get("set_uri", ""),
            "scryfall_uri": card_data.get("scryfall_uri", ""),
            "object": card_data.get("object", ""),
            "created_at": card_data.get("created_at", ""),
            "updated_at": card_data.get("updated_at", "")
        }
        
        append_to_csv(MTG_CARDS_CSV, flat_data, fieldnames)
        
        # Download card images if available
        image_uris = card_data.get("image_uris", {})
        card_id = card_data.get("id", "unknown")
        
        for size in ["small", "normal", "large"]:
            if image_uris.get(size):
                filename = get_image_filename(image_uris[size], f"{card_id}_{size}")
                save_path = os.path.join(MTG_CARD_IMAGES, filename)
                download_image(image_uris[size], save_path)
        
        return True
    except Exception as e:
        logger.error(f"Failed to store MTG card {card_data.get('name', 'unknown')}: {e}")
        return False

def get_fallback_stats() -> Dict[str, Any]:
    """Get statistics about the fallback data."""
    stats = {
        "pokemon_sets": 0,
        "pokemon_cards": 0,
        "pokemon_card_images": 0,
        "pokemon_set_images": 0,
        "mtg_sets": 0,
        "mtg_cards": 0,
        "mtg_card_images": 0,
        "mtg_set_images": 0
    }
    
    try:
        # Count CSV records
        if os.path.exists(POKEMON_SETS_CSV):
            with open(POKEMON_SETS_CSV, 'r') as f:
                stats["pokemon_sets"] = sum(1 for _ in f) - 1  # Subtract header
                
        if os.path.exists(POKEMON_CARDS_CSV):
            with open(POKEMON_CARDS_CSV, 'r') as f:
                stats["pokemon_cards"] = sum(1 for _ in f) - 1
                
        if os.path.exists(MTG_SETS_CSV):
            with open(MTG_SETS_CSV, 'r') as f:
                stats["mtg_sets"] = sum(1 for _ in f) - 1
                
        if os.path.exists(MTG_CARDS_CSV):
            with open(MTG_CARDS_CSV, 'r') as f:
                stats["mtg_cards"] = sum(1 for _ in f) - 1
        
        # Count images
        if os.path.exists(POKEMON_CARD_IMAGES):
            stats["pokemon_card_images"] = len(os.listdir(POKEMON_CARD_IMAGES))
        if os.path.exists(POKEMON_SET_IMAGES):
            stats["pokemon_set_images"] = len(os.listdir(POKEMON_SET_IMAGES))
        if os.path.exists(MTG_CARD_IMAGES):
            stats["mtg_card_images"] = len(os.listdir(MTG_CARD_IMAGES))
        if os.path.exists(MTG_SET_IMAGES):
            stats["mtg_set_images"] = len(os.listdir(MTG_SET_IMAGES))
            
    except Exception as e:
        logger.error(f"Failed to get fallback stats: {e}")
    
    return stats

# Initialize directories on import
ensure_directories()
