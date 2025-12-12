import pandas as pd
from src.config import BOOKS_DATABASE_PATH

books_df = pd.read_csv(BOOKS_DATABASE_PATH)

selected_category = 'Animal Fairy Tales- Contes Animaux'
category_books = books_df[books_df['category'] == selected_category]

print('='*80)
print('ANIMAL FAIRY TALES - CONTES ANIMAUX - DETAILED AUDIT')
print('='*80)
print()

for idx, row in category_books.iterrows():
    print(f'Title: {row["title"]}')
    print(f'DB Nickname: {row["book_nick_name"]}')
    print()
