#!/usr/bin/env python3
"""Add MTG columns to collection_cards table"""
import sqlite3
import os

DB_PATH = os.path.join(os.path.dirname(__file__), "collectibles.db")

conn = sqlite3.connect(DB_PATH)
cursor = conn.cursor()

# Check which columns already exist
cursor.execute("PRAGMA table_info(collection_cards)")
existing = {row[1] for row in cursor.fetchall()}

new_columns = [
    ("scryfall_id", "TEXT"),
    ("mana_cost", "TEXT"),
    ("type_line", "TEXT"),
    ("oracle_text", "TEXT"),
    ("keywords", "TEXT"),
    ("power", "TEXT"),
    ("toughness", "TEXT"),
    ("rarity", "TEXT"),
    ("color_identity", "TEXT"),
    ("finish", "TEXT"),
    ("tcg_link", "TEXT"),
]

for col_name, col_type in new_columns:
    if col_name not in existing:
        print(f"Adding column: {col_name}")
        cursor.execute(f"ALTER TABLE collection_cards ADD COLUMN {col_name} {col_type}")
    else:
        print(f"Column already exists: {col_name}")

conn.commit()
conn.close()
print("Done!")
