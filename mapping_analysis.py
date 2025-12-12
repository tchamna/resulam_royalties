import pandas as pd
from src.config import BOOKS_DATABASE_PATH
from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY

books_df = pd.read_csv(BOOKS_DATABASE_PATH)
royalties_df = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')

selected_category = 'Animal Fairy Tales- Contes Animaux'
category_books = books_df[books_df['category'] == selected_category]

print('='*80)
print('MAPPING ANALYSIS')
print('='*80)
print()

db_nicknames = category_books['book_nick_name'].dropna().tolist()

print('DB Nicknames and their Royalty Matches:')
print()

for db_nick in db_nicknames:
    print(f'DB: {db_nick}')
    
    # Check if mapping exists
    if db_nick in DB_NICKNAME_TO_ROYALTY:
        print(f'  Mapping found -> {DB_NICKNAME_TO_ROYALTY[db_nick]}')
    else:
        print(f'  No mapping - checking direct match in royalties...')
        direct = royalties_df[royalties_df['book_nick_name'] == db_nick]
        if len(direct) > 0:
            print(f'    Direct match found: {len(direct)} records')
            unique_nicks = direct['book_nick_name'].unique()
            for nick in unique_nicks:
                print(f'      - {nick}')
        else:
            print(f'    No direct match in royalties!')
    
    # Check for similar nicknames
    similar = royalties_df[royalties_df['book_nick_name'].str.contains(db_nick.split('_')[0], case=False, na=False)]
    if len(similar) > 0:
        print(f'  Similar nicknames in royalties:')
        for nick in similar['book_nick_name'].unique():
            count = len(similar[similar['book_nick_name'] == nick])
            print(f'    - {nick} ({count} records)')
    
    print()
