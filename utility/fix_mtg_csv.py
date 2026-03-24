#!/usr/bin/env python3
"""
Fix MTG CSV file - clean up corrupted data and structure
"""

import csv
import os
import json
from datetime import datetime

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

def fix_csv_file(input_file, output_file):
    """Fix the CSV file by cleaning up corrupted data"""
    print(f"Reading CSV file: {input_file}")
    
    if not os.path.exists(input_file):
        print(f"Error: {input_file} not found")
        return False
    
    try:
        with open(input_file, 'r', encoding='utf-8') as infile:
            reader = csv.DictReader(infile)
            
            # Get fieldnames and clean them up
            fieldnames = [f.strip() for f in reader.fieldnames if f.strip()]
            print(f"Fieldnames: {fieldnames}")
            
            # Read all rows
            rows = []
            for row in reader:
                # Clean up the row data
                clean_row = {}
                for field in fieldnames:
                    value = row.get(field, '').strip()
                    clean_row[field] = value
                
                rows.append(clean_row)
            
            print(f"Read {len(rows)} rows")
    
    except Exception as e:
        print(f"Error reading CSV: {e}")
        return False
    
    # Process and fix the data
    fixed_rows = []
    all_fields = set(fieldnames)
    
    # First pass: collect all possible fields
    for row in rows:
        all_fields.update(row.keys())
    
    all_fields = list(all_fields)
    print(f"All fields found: {all_fields}")
    
    for i, row in enumerate(rows):
        try:
            # Fix game_type - recalculate it based on set_type
            set_type = row.get('set_type', '')
            game_type = get_game_type(set_type)
            row['game_type'] = game_type
            
            # Fix card_count - convert to int
            card_count = row.get('card_count', '0')
            try:
                row['card_count'] = int(card_count)
            except:
                row['card_count'] = 0
            
            # Fix digital - convert to boolean
            digital = row.get('digital', 'False')
            row['digital'] = digital.lower() == 'true'
            
            # Fix foil_only - convert to boolean
            if 'foil_only' in row:
                foil_only = row.get('foil_only', 'False')
                row['foil_only'] = foil_only.lower() == 'true'
            
            # Fix nonfoil_only - convert to boolean
            if 'nonfoil_only' in row:
                nonfoil_only = row.get('nonfoil_only', 'False')
                row['nonfoil_only'] = nonfoil_only.lower() == 'true'
            
            # Add metadata
            row['last_updated'] = datetime.now().isoformat()
            
            fixed_rows.append(row)
            
            if i < 5:  # Show first few rows for debugging
                print(f"Row {i}: {row.get('name', 'Unknown')} - {row.get('game_type', 'Unknown')}")
                
        except Exception as e:
            print(f"Error processing row {i}: {e}")
            continue
    
    print(f"Fixed {len(fixed_rows)} rows")
    
    # Write the fixed CSV
    try:
        final_fields = all_fields + ['last_updated']
        with open(output_file, 'w', newline='', encoding='utf-8') as outfile:
            writer = csv.DictWriter(outfile, fieldnames=final_fields)
            writer.writeheader()
            writer.writerows(fixed_rows)
        
        print(f"Successfully wrote fixed CSV: {output_file}")
        return True
        
    except Exception as e:
        print(f"Error writing fixed CSV: {e}")
        return False

def main():
    """Main function"""
    input_file = "fallback_data/MTG/mtgsets.csv"
    output_file = "fallback_data/MTG/mtgsets_clean.csv"
    
    print("MTG CSV Fix Tool")
    print("=" * 50)
    
    if fix_csv_file(input_file, output_file):
        print("✅ CSV file fixed successfully!")
        
        # Test the fixed file
        print("\nTesting fixed CSV...")
        try:
            import sys
            import os
            sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            from tcgpricetracker import load_sets_from_csv
            
            sets = load_sets_from_csv(output_file)
            print(f"✅ Successfully loaded {len(sets)} sets from fixed CSV")
            
            if sets:
                sample = sets[0]
                print(f"Sample set: {sample.get('name', 'Unknown')}")
                print(f"Game type: {sample.get('game_type', 'Unknown')}")
                print(f"Card count: {sample.get('card_count', 'Unknown')}")
                print(f"Digital: {sample.get('digital', 'Unknown')}")
        except Exception as e:
            print(f"❌ Error testing fixed CSV: {e}")
    else:
        print("❌ Failed to fix CSV file")

if __name__ == "__main__":
    main()
