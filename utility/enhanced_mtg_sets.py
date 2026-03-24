#!/usr/bin/env python3
"""
Enhanced MTG Sets Handler - Captures all Scryfall API fields with incremental updates
"""

import csv
import os
import json
from typing import Dict, List, Optional, Set
from datetime import datetime
import requests

# Complete list of all possible Scryfall set fields
SCRYFALL_SET_FIELDS = [
    "object", "id", "code", "mtgo_code", "arena_code", "tcgplayer_id", 
    "name", "uri", "scryfall_uri", "search_uri", "released_at", "set_type", 
    "card_count", "digital", "nonfoil_only", "foil_only", "icon_svg_uri",
    "parent_set_code", "block_code", "block", "released_at", "printed_size",
    "digital_size", "foil_only_printed_size", "nonfoil_only_printed_size",
    "object_type", "set_type", "uri", "scryfall_uri", "search_uri", 
    "related_uris", "purchase_uris", "booster_types", "mkm_id", "mkm_name"
]

# Game Type to Set Type mapping
GAME_TYPE_MAPPING = {
    "Main": ["core", "expansion", "masters", "eternal", "masterpiece", "from_the_vault", "starter", "draft_innovation"],
    "Digital": ["alchemy", "treasure_chest"],
    "Commander": ["arsenal", "spellbook", "commander"],
    "Planechase": ["planechase"],
    "Pre-Built": ["premium_deck", "duel_deck", "archenemy"],
    "Vanguard": ["vanguard"],
    "Funny": ["funny"],
    "Other": ["box", "promo", "token", "memorabilia", "minigame"]
}

def get_game_type(set_type):
    """Get game type based on set type"""
    if not set_type:
        return "Other"
    set_type = set_type.lower()
    for game_type, set_types in GAME_TYPE_MAPPING.items():
        if set_type in set_types:
            return game_type
    return "Other"

def get_all_scryfall_sets() -> List[Dict]:
    """Get all sets from Scryfall API with complete field capture"""
    all_sets = []
    try:
        url = "https://api.scryfall.com/sets"
        page = 1
        
        while url:
            print(f"Fetching page {page}...")
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            data = response.json()
            
            sets = data.get("data", [])
            all_sets.extend(sets)
            
            print(f"  Retrieved {len(sets)} sets (total: {len(all_sets)})")
            
            # Check for pagination
            if data.get("has_more"):
                url = data.get("next_page")
                page += 1
            else:
                break
                
    except Exception as e:
        print(f"Error fetching sets: {e}")
        return []
    
    return all_sets

def load_existing_sets(csv_file: str) -> Dict[str, Dict]:
    """Load existing sets from CSV into a dict keyed by set code"""
    existing_sets = {}
    
    if not os.path.exists(csv_file):
        return existing_sets
    
    try:
        with open(csv_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                set_code = row.get('code', '')
                if set_code:
                    existing_sets[set_code] = row
    except Exception as e:
        print(f"Error loading existing sets: {e}")
        return {}
    
    return existing_sets

def flatten_set_data(set_data: Dict) -> Dict:
    """Flatten nested set data for CSV storage"""
    flattened = {}
    
    # Add all direct fields
    for field in SCRYFALL_SET_FIELDS:
        value = set_data.get(field, '')
        if value is None:
            value = ''
        elif isinstance(value, (dict, list)):
            # Convert complex objects to JSON strings
            value = json.dumps(value)
        flattened[field] = value
    
    # Add game_type
    set_type = set_data.get('set_type', '')
    flattened['game_type'] = get_game_type(set_type)
    
    # Add metadata
    flattened['last_updated'] = datetime.now().isoformat()
    
    return flattened

def compare_sets(existing: Dict, new: Dict) -> bool:
    """Compare two sets to see if they need updating"""
    # Compare key fields that might change
    key_fields = ['name', 'card_count', 'released_at', 'set_type', 'digital']
    
    for field in key_fields:
        existing_val = str(existing.get(field, '')).strip()
        new_val = str(new.get(field, '')).strip()
        if existing_val != new_val:
            return True
    
    return False

def update_sets_csv(csv_file: str, force_update: bool = False) -> None:
    """Update sets CSV with incremental changes"""
    print("Starting enhanced MTG sets update...")
    
    # Get all sets from Scryfall
    print("Fetching all sets from Scryfall API...")
    all_sets = get_all_scryfall_sets()
    
    if not all_sets:
        print("No sets retrieved from API")
        return
    
    print(f"Total sets from API: {len(all_sets)}")
    
    # Load existing sets
    print("Loading existing sets...")
    existing_sets = load_existing_sets(csv_file)
    print(f"Existing sets in CSV: {len(existing_sets)}")
    
    # Prepare all fields for CSV
    all_fieldnames = set(SCRYFALL_SET_FIELDS)
    all_fieldnames.add('game_type')
    all_fieldnames.add('last_updated')
    
    # Add any fields that might exist in existing CSV
    if existing_sets:
        existing_fields = set()
        for set_data in existing_sets.values():
            existing_fields.update(set_data.keys())
        all_fieldnames.update(existing_fields)
    
    fieldnames = sorted(list(all_fieldnames))
    
    # Process updates
    updated_sets = []
    new_sets = []
    unchanged_sets = []
    
    for set_data in all_sets:
        set_code = set_data.get('code', '')
        if not set_code:
            continue
        
        flattened = flatten_set_data(set_data)
        
        if set_code in existing_sets:
            existing = existing_sets[set_code]
            if force_update or compare_sets(existing, flattened):
                updated_sets.append((set_code, flattened, existing))
            else:
                unchanged_sets.append(set_code)
        else:
            new_sets.append((set_code, flattened))
    
    print(f"\nUpdate Summary:")
    print(f"  New sets: {len(new_sets)}")
    print(f"  Updated sets: {len(updated_sets)}")
    print(f"  Unchanged sets: {len(unchanged_sets)}")
    
    if not new_sets and not updated_sets and not force_update:
        print("No updates needed.")
        return
    
    # Create backup
    if os.path.exists(csv_file):
        backup_file = csv_file.replace('.csv', f'_backup_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv')
        os.rename(csv_file, backup_file)
        print(f"Created backup: {backup_file}")
    
    # Write updated CSV
    print("Writing updated CSV...")
    
    with open(csv_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        
        # Write unchanged existing sets
        for set_code in unchanged_sets:
            writer.writerow(existing_sets[set_code])
        
        # Write new sets
        for set_code, flattened in new_sets:
            writer.writerow(flattened)
        
        # Write updated sets
        for set_code, flattened, old_data in updated_sets:
            writer.writerow(flattened)
    
    print(f"Successfully updated {csv_file}")
    
    # Show details of changes
    if new_sets:
        print(f"\nNew sets added:")
        for set_code, flattened in new_sets[:10]:  # Show first 10
            print(f"  {set_code}: {flattened.get('name', 'Unknown')}")
        if len(new_sets) > 10:
            print(f"  ... and {len(new_sets) - 10} more")
    
    if updated_sets:
        print(f"\nUpdated sets:")
        for set_code, flattened, old_data in updated_sets[:10]:  # Show first 10
            print(f"  {set_code}: {flattened.get('name', 'Unknown')}")
        if len(updated_sets) > 10:
            print(f"  ... and {len(updated_sets) - 10} more")

def main():
    """Main function"""
    csv_file = "fallback_data/MTG/mtgsets.csv"
    
    print("Enhanced MTG Sets Updater")
    print("=" * 50)
    
    # Check if CSV exists and show current state
    if os.path.exists(csv_file):
        existing = load_existing_sets(csv_file)
        print(f"Current CSV has {len(existing)} sets")
        
        # Show field count
        if existing:
            sample_set = list(existing.values())[0]
            print(f"Current fields: {len(sample_set)}")
    else:
        print("No existing CSV found - will create new one")
    
    print("\nOptions:")
    print("1. Incremental update (only new/changed sets)")
    print("2. Force complete update (all sets)")
    
    try:
        choice = input("\nChoose option (1 or 2): ").strip()
        force_update = choice == '2'
        
        update_sets_csv(csv_file, force_update)
        
    except KeyboardInterrupt:
        print("\nUpdate cancelled.")
    except Exception as e:
        print(f"Error during update: {e}")

if __name__ == "__main__":
    main()
