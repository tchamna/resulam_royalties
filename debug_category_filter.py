"""
Debug script to test the category filter functionality
"""
import pandas as pd
from src.config import BOOKS_DATABASE_PATH

def main():
    print("=" * 60)
    print("DEBUG: Category Filter Test")
    print("=" * 60)
    
    # Load books database
    print(f"\n1. Loading books from: {BOOKS_DATABASE_PATH}")
    try:
        books_df = pd.read_csv(BOOKS_DATABASE_PATH)
        print(f"   ✅ Loaded {len(books_df)} books")
    except Exception as e:
        print(f"   ❌ Error loading: {e}")
        return
    
    # Check if category column exists
    print(f"\n2. Checking columns...")
    print(f"   Columns: {books_df.columns.tolist()}")
    
    if 'category' not in books_df.columns:
        print("   ❌ 'category' column NOT FOUND!")
        return
    else:
        print("   ✅ 'category' column exists")
    
    # Show unique categories
    print(f"\n3. Unique categories:")
    categories = books_df['category'].dropna().unique().tolist()
    for i, cat in enumerate(categories, 1):
        count = len(books_df[books_df['category'] == cat])
        print(f"   {i}. '{cat}' ({count} books)")
    
    # Test filtering for each category
    print(f"\n4. Testing filter for each category:")
    for cat in categories:
        filtered = books_df[books_df['category'] == cat]
        print(f"\n   Category: '{cat}'")
        print(f"   Found: {len(filtered)} books")
        if len(filtered) > 0:
            for _, row in filtered.head(3).iterrows():
                print(f"      - {row['book_nick_name']}")
            if len(filtered) > 3:
                print(f"      ... and {len(filtered) - 3} more")
    
    # Test 'all' filter behavior
    print(f"\n5. Testing 'all' filter (should show all {len(books_df)} books):")
    selected_category = "all"
    if selected_category and selected_category != "all":
        filtered = books_df[books_df['category'] == selected_category]
    else:
        filtered = books_df
    print(f"   Result: {len(filtered)} books")
    
    # Test specific category filter
    print(f"\n6. Testing specific category 'Grammaire - Grammar':")
    selected_category = "Grammaire - Grammar"
    if selected_category and selected_category != "all":
        filtered = books_df[books_df['category'] == selected_category]
    else:
        filtered = books_df
    print(f"   Result: {len(filtered)} books")
    for _, row in filtered.iterrows():
        print(f"      - {row['book_nick_name']}")
    
    print("\n" + "=" * 60)
    print("DEBUG COMPLETE")
    print("=" * 60)

if __name__ == "__main__":
    main()
