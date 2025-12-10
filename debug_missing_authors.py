#!/usr/bin/env python
"""Debug script to find missing authors in 2025 data"""

import pandas as pd
from src.data.processor import DataProcessor
from src.config import AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE

# Load data
processor = DataProcessor()
data = processor.load_and_process_data()

royalties = data['royalties']
royalties_exploded = data['royalties_exploded']

# Filter for 2025
data_2025 = royalties[royalties['Year Sold'] == 2025]
data_2025_exploded = royalties_exploded[royalties_exploded['Year Sold'] == 2025]

print("=" * 80)
print("DEBUG: 2025 All Languages Analysis")
print("=" * 80)

print(f"\nTotal Revenue (Royalty USD sum): ${data_2025['Royalty USD'].sum():,.2f}")
print(f"Net Revenue (with NET_REVENUE_PERCENTAGE={NET_REVENUE_PERCENTAGE}): ${data_2025['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE:,.2f}")

print(f"\nTotal rows in 2025: {len(data_2025)}")
print(f"Total rows in 2025 exploded: {len(data_2025_exploded)}")

print(f"\nTotal Royalties Shared (sum of Royalty per Author USD): ${data_2025['Royalty per Author (USD)'].sum():,.2f}")
print(f"Total Royalties Shared (net): ${data_2025['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE:,.2f}")

# Get all unique authors
unique_authors_raw = data_2025_exploded['Authors_Exploded'].unique().tolist()
print(f"\nUnique authors (raw): {len(unique_authors_raw)}")

# Normalize and deduplicate
normalized = {}
for author in unique_authors_raw:
    normalized_name = AUTHOR_NORMALIZATION.get(author, author)
    if normalized_name not in normalized:
        normalized[normalized_name] = author

unique_authors_normalized = sorted(normalized.keys())
print(f"Unique authors (normalized): {len(unique_authors_normalized)}")

print("\n" + "=" * 80)
print("AUTHOR EARNINGS BREAKDOWN:")
print("=" * 80)

author_earnings = {}
for author in unique_authors_normalized:
    # Find all raw author names that map to this normalized name
    mask = data_2025_exploded['Authors_Exploded'].apply(
        lambda x: AUTHOR_NORMALIZATION.get(x, x) == author
    )
    earnings = data_2025_exploded[mask]['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE
    author_earnings[author] = earnings

# Sort by earnings
for author, earnings in sorted(author_earnings.items(), key=lambda x: x[1], reverse=True):
    print(f"{author}: ${earnings:,.2f}")

total_authors_earnings = sum(author_earnings.values())
print(f"\nSum of all author earnings: ${total_authors_earnings:,.2f}")

# Calculate Resulam share
num_authors = len(unique_authors_normalized)
net_revenue = data_2025['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE
resulam_share = net_revenue / (num_authors + 1)

print(f"\n" + "=" * 80)
print("FINANCIAL BREAKDOWN:")
print("=" * 80)
print(f"Total Revenue: ${data_2025['Royalty USD'].sum():,.2f}")
print(f"Net Revenue (100%): ${net_revenue:,.2f}")
print(f"Number of Authors: {num_authors}")
print(f"Resulam Share (Net Revenue / (N+1)): ${resulam_share:,.2f}")
print(f"Total Royalties Shared: ${total_authors_earnings:,.2f}")
print(f"Sum (Resulam Share + Authors): ${resulam_share + total_authors_earnings:,.2f}")

print(f"\n" + "=" * 80)
print("VERIFICATION:")
print("=" * 80)
expected_net_revenue = 2648.57
actual_total = resulam_share + total_authors_earnings
difference = expected_net_revenue - actual_total

print(f"Expected Net Revenue: ${expected_net_revenue:,.2f}")
print(f"Actual Total (Resulam + Authors): ${actual_total:,.2f}")
print(f"Difference: ${difference:,.2f}")

if abs(difference) > 0.01:
    print(f"\n⚠️ MISSING: ${abs(difference):,.2f}")
else:
    print(f"\n✓ MATCH!")
