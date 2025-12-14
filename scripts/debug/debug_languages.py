#!/usr/bin/env python3
"""
Debug script to check what languages are in self.royalties when dashboard initializes
"""
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))

from src.data import load_and_process_all_data

print("Loading data...")
data = load_and_process_all_data()

print("\nChecking royalties_history dataframe...")
royalties = data['royalties_history']

print(f"Total records: {len(royalties)}")
print(f"Language column type: {royalties['Language'].dtype}")
print(f"Unique languages: {len(royalties['Language'].unique())}")

languages = sorted(royalties['Language'].dropna().unique().tolist())
print("\nAll languages in royalties_history:")
for lang in languages:
    count = len(royalties[royalties['Language'] == lang])
    print(f"  {lang}: {count} records")

# Check specifically for Dioula
dioula_count = len(royalties[royalties['Language'] == 'Dioula'])
print(f"\nDioula count: {dioula_count}")

# Check for any case variations
dioula_variants = royalties[royalties['Language'].str.contains('ioula', case=False, na=False)]
print(f"Dioula variants found: {len(dioula_variants)}")
if len(dioula_variants) > 0:
    print("Dioula variants:")
    print(dioula_variants[['Title', 'Language']].drop_duplicates().to_string())
