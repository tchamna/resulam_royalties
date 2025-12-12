import pandas as pd
from src.config import BOOKS_DATABASE_PATH
from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES

books_df = pd.read_csv(BOOKS_DATABASE_PATH)
royalties = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')

print('=== CATEGORY ANALYSIS ===')
print()

# Get all categories
categories = books_df['category'].dropna().unique()
royalty_nicks = set(royalties['book_nick_name'].unique())

for cat in sorted(categories):
    cat_books = books_df[books_df['category'] == cat]
    db_nicknames = set(cat_books['book_nick_name'].dropna().tolist())
    
    # Check which exist in royalties
    found_in_royalties = db_nicknames & royalty_nicks
    missing = db_nicknames - royalty_nicks
    
    filtered = royalties[royalties['book_nick_name'].isin(db_nicknames)]
    
    print(f'CATEGORY: {cat}')
    print(f'  Books in DB: {len(cat_books)}')
    print(f'  DB nicknames match royalties: {len(found_in_royalties)}/{len(db_nicknames)}')
    print(f'  Royalty records: {len(filtered)}')
    if missing:
        print(f'  MISSING from royalties: {missing}')
    print()

# Also show what nicknames exist in royalties but NOT in books DB
print('='*60)
print('Nicknames in ROYALTIES but NOT in books database:')
db_all_nicks = set(books_df['book_nick_name'].dropna().tolist())
orphan_nicks = royalty_nicks - db_all_nicks
for nick in sorted(orphan_nicks):
    count = len(royalties[royalties['book_nick_name'] == nick])
    print(f'  {nick}: {count} records')
