import pandas as pd

# Load the CSV that was exported
df = pd.read_csv('royalties_resulambooks_from_2015_2024_history_df.csv')
df_exploded = pd.read_csv('royalties_exploded_2024.csv')

print("=== NON-EXPLODED DATA ===")
print(f"Total rows: {len(df)}")
print(f"Unique 'Authors' values: {df['Authors'].nunique()}")
print(f"Sample Authors column:\n{df['Authors'].head(10).tolist()}\n")

print("=== EXPLODED DATA ===")
print(f"Total rows: {len(df_exploded)}")
print(f"Unique 'Authors_Exploded' values: {df_exploded['Authors_Exploded'].nunique()}")
print(f"Sample Authors_Exploded column:\n{df_exploded['Authors_Exploded'].head(10).tolist()}\n")

print("=== COMPARISON ===")
authors_from_non_exploded = set(df['Authors'].unique())
authors_from_exploded = set(df_exploded['Authors_Exploded'].unique())

print(f"Authors in non-exploded (Authors column): {len(authors_from_non_exploded)}")
print(f"Authors in exploded (Authors_Exploded column): {len(authors_from_exploded)}")
print(f"\nIn non-exploded but NOT in exploded: {authors_from_non_exploded - authors_from_exploded}")
print(f"In exploded but NOT in non-exploded: {authors_from_exploded - authors_from_non_exploded}")
