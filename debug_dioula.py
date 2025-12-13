#!/usr/bin/env python3
"""
Debug script to trace Dioula language through the data pipeline
"""
import pandas as pd
from src.config import BOOKS_DATABASE_PATH, ROYALTIES_HISTORY_PATH
from src.data import load_and_process_all_data

print("=" * 70)
print("DIOULA LANGUAGE DEBUG SCRIPT")
print("=" * 70)

# Step 1: Check books database
print("\n[1] BOOKS DATABASE CHECK")
print("-" * 70)
books_df = pd.read_csv(BOOKS_DATABASE_PATH)
dioula_books = books_df[books_df['language_name'].str.contains('Dioula', case=False, na=False)]
print(f"Books with 'Dioula' in language_name: {len(dioula_books)}")
if len(dioula_books) > 0:
    print(dioula_books[['id', 'title', 'language_name', 'book_nick_name']].to_string())
else:
    print("No Dioula books found in database")

# Step 2: Check royalties history Excel file
print("\n[2] ROYALTIES HISTORY EXCEL CHECK")
print("-" * 70)
try:
    combined_sales = pd.read_excel(ROYALTIES_HISTORY_PATH, sheet_name="Combined Sales")
    dioula_sales = combined_sales[combined_sales['Title'].str.contains('Dioula', case=False, na=False)]
    print(f"Sales records with 'Dioula' in title: {len(dioula_sales)}")
    if len(dioula_sales) > 0:
        print(dioula_sales[['Title', 'ASIN/ISBN']].head(3).to_string())
except Exception as e:
    print(f"Error reading Excel: {e}")

# Step 3: Check processed data
print("\n[3] PROCESSED DATA CHECK")
print("-" * 70)
try:
    data = load_and_process_all_data()
    royalties = data['royalties_history']
    
    dioula_records = royalties[royalties['Language'] == 'Dioula']
    print(f"Dioula records after processing: {len(dioula_records)}")
    
    if len(dioula_records) > 0:
        print("\n✓ Dioula FOUND in processed data!")
        print(dioula_records[['Title', 'Language', 'book_nick_name']].head(3).to_string())
    else:
        print("\n✗ Dioula NOT found in processed data")
        
        # Check what the Dioula book title maps to
        print("\nChecking mapping for Dioula book...")
        dioula_book = books_df[books_df['language_name'] == 'Dioula']
        if len(dioula_book) > 0:
            book_title = dioula_book.iloc[0]['title']
            print(f"Book title from database: {book_title}")
            
            # Check if this title exists in royalties
            matching = royalties[royalties['Title'].str.contains(book_title.split(':')[0], case=False, na=False)]
            print(f"Matching royalty records: {len(matching)}")
            if len(matching) > 0:
                print(matching[['Title', 'Language']].head(3).to_string())
except Exception as e:
    print(f"Error processing data: {e}")
    import traceback
    traceback.print_exc()

# Step 4: Check all unique languages
print("\n[4] ALL UNIQUE LANGUAGES IN PROCESSED DATA")
print("-" * 70)
try:
    data = load_and_process_all_data()
    royalties = data['royalties_history']
    all_langs = sorted(royalties['Language'].dropna().unique().tolist())
    print(f"Total unique languages: {len(all_langs)}")
    for lang in all_langs:
        count = len(royalties[royalties['Language'] == lang])
        marker = " ← DIOULA" if lang == 'Dioula' else ""
        print(f"  {lang}: {count} records{marker}")
except Exception as e:
    print(f"Error: {e}")

print("\n" + "=" * 70)
