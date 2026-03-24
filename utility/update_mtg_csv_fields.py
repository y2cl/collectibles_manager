#!/usr/bin/env python3
"""
Update MTG Sets CSV to include all Scryfall set fields
"""

import csv
import os
import sys
from datetime import datetime

# Complete list of Scryfall set fields
SCRYFALL_SET_FIELDS = [
    "object", "id", "code", "mtgo_code", "arena_code", "tcgplayer_id", 
    "name", "uri", "scryfall_uri", "search_uri", "released_at", "set_type", 
    "card_count", "digital", "nonfoil_only", "foil_only", "icon_svg_uri",
    "parent_set_code", "block_code", "block", "printed_size",
    "digital_size", "foil_only_printed_size", "nonfoil_only_printed_size",
    "mkm_id", "mkm_name", "related_uris", "purchase_uris", "booster_types"
]

def update_csv_fields(input_file: str, output_file: str = None):
    """Update CSV to include all required fields"""
    
    if output_file is None:
        output_file = input_file
    
    # Read existing CSV
    existing_sets = []
    existing_headers = []
    
    if os.path.exists(input_file):
        with open(input_file, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            existing_headers = reader.fieldnames or []
            existing_sets = list(reader)
    
    # Prepare new headers
    new_headers = list(SCRYFALL_SET_FIELDS)
    new_headers.append('game_type')  # Custom field
    new_headers.append('last_updated')  # Custom field
    
    print(f"Existing headers ({len(existing_headers)}): {existing_headers}")
    print(f"New headers ({len(new_headers)}): {new_headers}")
    
    # Write updated CSV
    with open(output_file, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=new_headers)
        writer.writeheader()
        
        for set_data in existing_sets:
            # Create new row with all fields
            new_row = {}
            
            # Initialize all fields to empty string
            for field in new_headers:
                new_row[field] = ''
            
            # Copy existing data
            for field, value in set_data.items():
                if field in new_headers:
                    new_row[field] = value
            
            # Ensure last_updated is set
            if not new_row.get('last_updated'):
                new_row['last_updated'] = datetime.now().isoformat()
            
            writer.writerow(new_row)
    
    print(f"✅ Updated CSV with {len(existing_sets)} sets and {len(new_headers)} fields")
    return len(existing_sets), len(new_headers)

def main():
    """Main function"""
    csv_file = "fallback_data/MTG/mtgsets.csv"
    
    if not os.path.exists(csv_file):
        print(f"❌ CSV file not found: {csv_file}")
        return 1
    
    print("MTG CSV Field Updater")
    print("=" * 50)
    print(f"Processing: {csv_file}")
    
    # Create backup
    backup_file = csv_file.replace('.csv', '_before_field_update.csv')
    os.replace(csv_file, backup_file)
    print(f"✅ Backup created: {backup_file}")
    
    # Update fields
    try:
        sets_count, fields_count = update_csv_fields(backup_file, csv_file)
        print(f"✅ Successfully updated {sets_count} sets with {fields_count} fields")
        return 0
    except Exception as e:
        print(f"❌ Error updating CSV: {e}")
        # Restore backup
        os.replace(backup_file, csv_file)
        print("✅ Restored backup")
        return 1

if __name__ == "__main__":
    sys.exit(main())
