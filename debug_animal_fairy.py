import pandas as pd
from src.config import BOOKS_DATABASE_PATH
from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES

books_df = pd.read_csv(BOOKS_DATABASE_PATH)
royalties = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')

# Check Animal Fairy Tales category
selected_category = 'Animal Fairy Tales'
category_books = books_df[books_df['category'] == selected_category]
print(f'Books in database with category "{selected_category}": {len(category_books)}')
print('='*60)
for _, row in category_books.iterrows():
    title = str(row['title'])[:50] if pd.notna(row['title']) else 'N/A'
    nick = row['book_nick_name'] if pd.notna(row['book_nick_name']) else 'N/A'
    print(f'  Title: {title}...')
    print(f'  DB Nickname: {nick}')
    print()

# Collect nicknames from database
category_nicknames = set()
for _, row in category_books.iterrows():
    db_nick = row['book_nick_name']
    if pd.notna(db_nick):
        category_nicknames.add(db_nick)

print(f'Nicknames from DB: {category_nicknames}')
print()

# Check which exist in royalties
royalty_nicks = set(royalties['book_nick_name'].unique())
matching = category_nicknames & royalty_nicks
print(f'Matching in royalties: {matching}')

# Check what's in royalties that might be animal tales
print()
print('Checking royalties for animal-related nicknames:')
for nick in sorted(royalty_nicks):
    if 'animal' in nick.lower() or 'tale' in nick.lower() or 'fables' in nick.lower() or 'contes' in nick.lower():
        print(f'  {nick}')

filtered = royalties[royalties['book_nick_name'].isin(category_nicknames)]
print(f'\nTotal royalty records for category: {len(filtered)}')
print(f'Total USD: ${filtered["Royalty USD"].sum():.2f}')
