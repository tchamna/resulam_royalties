#!/usr/bin/env python
"""Find missing authors in 2025 data"""

import pandas as pd
from src.config import AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE

# Read the CSV files
royalties_df = pd.read_csv("royalties_resulambooks_from_2015_2024_history_df.csv")
exploded_df = pd.read_csv("royalties_exploded_2024.csv")

# Filter for 2025
data_2025 = royalties_df[royalties_df['Year Sold'] == 2025]
data_2025_exploded = exploded_df[exploded_df['Year Sold'] == 2025]

print("=" * 80)
print("2025 ALL LANGUAGES ANALYSIS")
print("=" * 80)

print(f"\nTotal Revenue (Royalty USD): ${data_2025['Royalty USD'].sum():,.2f}")
print(f"Net Revenue (NET_REVENUE_PERCENTAGE={NET_REVENUE_PERCENTAGE}): ${data_2025['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE:,.2f}")

print(f"\nTotal rows in 2025: {len(data_2025)}")
print(f"Total rows in 2025 exploded: {len(data_2025_exploded)}")

print(f"\nTotal Royalty per Author USD: ${data_2025['Royalty per Author (USD)'].sum():,.2f}")
print(f"Total Royalty per Author USD (net): ${data_2025['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE:,.2f}")

# Get all unique authors from exploded data
unique_authors_raw = data_2025_exploded['Authors_Exploded'].unique().tolist()
print(f"\nUnique authors (raw): {len(unique_authors_raw)}")
print("Raw authors:", unique_authors_raw)

# Normalize authors
normalized_authors = {}
for author in unique_authors_raw:
    normalized = AUTHOR_NORMALIZATION.get(author, author)
    if normalized not in normalized_authors:
        normalized_authors[normalized] = []
    normalized_authors[normalized].append(author)

print(f"\nUnique authors (normalized): {len(normalized_authors)}")

print("\n" + "=" * 80)
print("AUTHOR EARNINGS (By Earnings):")
print("=" * 80)

author_earnings = {}
for author in normalized_authors.keys():
    # Calculate earnings
    mask = data_2025_exploded['Authors_Exploded'].apply(
        lambda x: AUTHOR_NORMALIZATION.get(x, x) == author
    )
    earnings = data_2025_exploded[mask]['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE
    author_earnings[author] = earnings

# Sort by earnings descending
for author, earnings in sorted(author_earnings.items(), key=lambda x: x[1], reverse=True):
    print(f"{author}: ${earnings:,.2f}")

total_author_earnings = sum(author_earnings.values())
print(f"\nTotal Author Earnings: ${total_author_earnings:,.2f}")

# Calculate Resulam share
num_authors = len(normalized_authors)
net_revenue = data_2025['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE
resulam_share = net_revenue / (num_authors + 1)

print(f"\n" + "=" * 80)
print("FINANCIAL BREAKDOWN:")
print("=" * 80)
print(f"Total Revenue: ${data_2025['Royalty USD'].sum():,.2f}")
print(f"Net Revenue (100%): ${net_revenue:,.2f}")
print(f"Number of Authors (normalized): {num_authors}")
print(f"Resulam Share (Net Revenue / (N+1)): ${resulam_share:,.2f}")
print(f"Total Author Earnings: ${total_author_earnings:,.2f}")
print(f"Grand Total (Resulam + Authors): ${resulam_share + total_author_earnings:,.2f}")

print(f"\n" + "=" * 80)
print("VERIFICATION:")
print("=" * 80)
expected = 2648.57
actual = resulam_share + total_author_earnings
diff = abs(expected - actual)

print(f"Expected Net Revenue: ${expected:,.2f}")
print(f"Actual Total: ${actual:,.2f}")
print(f"Difference: ${diff:,.2f}")

if diff > 0.01:
    print(f"\n⚠️  DISCREPANCY FOUND: ${diff:,.2f}")
else:
    print(f"\n✓ MATCH!")
