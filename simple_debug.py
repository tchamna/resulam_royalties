#!/usr/bin/env python3
"""
Simple debug script to check languages in royalties CSV
"""
import pandas as pd

print("Loading royalties_resulambooks_from_2015_2024_history_df.csv...")
royalties = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')

print(f"Total records: {len(royalties)}")
print(f"\nLanguage column info:")
print(f"  Type: {royalties['Language'].dtype}")
print(f"  Unique count: {len(royalties['Language'].unique())}")
print(f"  Null count: {royalties['Language'].isna().sum()}")

languages = sorted(royalties['Language'].dropna().unique().tolist())
print(f"\nAll languages in royalties CSV ({len(languages)} total):")
for lang in languages:
    count = len(royalties[royalties['Language'] == lang])
    marker = " <-- DIOULA" if lang == 'Dioula' else ""
    print(f"  {lang}: {count} records{marker}")

# Check specifically for Dioula
dioula_count = len(royalties[royalties['Language'] == 'Dioula'])
print(f"\nDioula count: {dioula_count}")
if dioula_count > 0:
    print("Dioula records found:")
    print(royalties[royalties['Language'] == 'Dioula'][['Title', 'Language']].head(3).to_string())
