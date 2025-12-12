import pandas as pd
from src.config import BOOKS_DATABASE_PATH
from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY

books_df = pd.read_csv(BOOKS_DATABASE_PATH)
royalties_df = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')

selected_category = 'Animal Fairy Tales- Contes Animaux'
category_books = books_df[books_df['category'] == selected_category]

print('='*80)
print('ANIMAL FAIRY TALES - COMPLETE FILTERING BREAKDOWN')
print('='*80)
print()

db_nicknames = category_books['book_nick_name'].dropna().tolist()
category_nicknames = set()

print('Step 1: Building category nicknames set')
print('-' * 80)

for db_nick in db_nicknames:
    print(f'\nDB Nickname: {db_nick}')
    
    if db_nick in DB_NICKNAME_TO_ROYALTY:
        mapped = DB_NICKNAME_TO_ROYALTY[db_nick]
        category_nicknames.update(mapped)
        print(f'  → Maps to royalty nicknames: {mapped}')
    else:
        category_nicknames.add(db_nick)
        print(f'  → No mapping, adding as-is: {db_nick}')

print()
print('='*80)
print(f'Final category_nicknames set ({len(category_nicknames)} items):')
print('-' * 80)
for nick in sorted(category_nicknames):
    print(f'  {nick}')

print()
print('='*80)
print('Step 2: Filtering royalties')
print('-' * 80)

filtered_df = royalties_df[royalties_df['book_nick_name'].isin(category_nicknames)]
print(f'\nTotal royalty records: {len(filtered_df)}')
print(f'Unique book nicknames: {filtered_df["book_nick_name"].nunique()}')
print()

for nick in sorted(filtered_df['book_nick_name'].unique()):
    count = len(filtered_df[filtered_df['book_nick_name'] == nick])
    total = filtered_df[filtered_df['book_nick_name'] == nick]['Royalty USD'].sum()
    print(f'  {nick:50} | {count:4} records | ${total:>8.2f}')

total_royalty = filtered_df['Royalty USD'].sum()
print()
print(f'Total Royalty: ${total_royalty:,.2f}')
