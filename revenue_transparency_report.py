#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Revenue Source Transparency Report
Shows exactly where every dollar comes from and how currencies are converted
"""

import pandas as pd
from src.config import EXCHANGE_RATES_HARDCODED, ROYALTIES_HISTORY_PATH, USE_LIVE_RATES
from src.utils.exchange_rates import get_exchange_rates

print("\n" + "="*80)
print("💰 REVENUE SOURCE & CURRENCY CONVERSION REPORT")
print("="*80)

# Get exchange rates being used
rate_source = "LIVE (from API)" if USE_LIVE_RATES else "HARDCODED (offline)"
rates = get_exchange_rates(use_live=USE_LIVE_RATES, hardcoded_fallback=EXCHANGE_RATES_HARDCODED)

print(f"\n📊 Exchange Rate Source: {rate_source}\n")

# Load source data
print(f"📂 Reading from: {ROYALTIES_HISTORY_PATH}\n")
try:
    combined_sales = pd.read_excel(ROYALTIES_HISTORY_PATH, sheet_name="Combined Sales")
except:
    print("❌ Error: Cannot find the Excel file. Check the path in src/config.py")
    exit(1)

# Calculate revenue by currency
print("="*80)
print("📈 REVENUE BREAKDOWN BY CURRENCY\n")
print(f"{'Currency':<10} {'Count':<8} {'Local Amount':<20} {'Rate':<10} {'USD Amount':<20}")
print("-"*80)

total_revenue_usd = 0
currency_details = []

for currency in sorted(combined_sales['Currency'].unique()):
    currency_data = combined_sales[combined_sales['Currency'] == currency]
    count = len(currency_data)
    local_total = currency_data['Royalty'].sum()
    rate = rates.get(currency, EXCHANGE_RATES_HARDCODED.get(currency, 1.0))
    usd_total = local_total * rate
    total_revenue_usd += usd_total
    
    currency_details.append({
        'Currency': currency,
        'Count': count,
        'Local Amount': local_total,
        'Rate': rate,
        'USD Amount': usd_total
    })
    
    print(f"{currency:<10} {count:<8} {local_total:>18,.2f}  {rate:>8.6f}  {usd_total:>18,.2f}")

print("-"*80)
print(f"{'TOTAL':<10} {len(combined_sales):<8} {combined_sales['Royalty'].sum():>18,.2f}  {'':<10} {total_revenue_usd:>18,.2f}")
print("="*80)

# Revenue by marketplace
print("\n🌍 REVENUE BY MARKETPLACE (USD)\n")
print(f"{'Marketplace':<30} {'Transactions':<15} {'Revenue (USD)':<20}")
print("-"*80)

marketplace_revenue = []
for marketplace in sorted(combined_sales['Marketplace'].unique()):
    mp_data = combined_sales[combined_sales['Marketplace'] == marketplace]
    mp_revenue = 0
    for currency in mp_data['Currency'].unique():
        currency_data = mp_data[mp_data['Currency'] == currency]
        local_amount = currency_data['Royalty'].sum()
        rate = rates.get(currency, EXCHANGE_RATES_HARDCODED.get(currency, 1.0))
        mp_revenue += local_amount * rate
    
    marketplace_revenue.append({
        'Marketplace': marketplace,
        'Count': len(mp_data),
        'Revenue': mp_revenue
    })
    
    print(f"{marketplace:<30} {len(mp_data):<15} ${mp_revenue:>18,.2f}")

print("-"*80)
print(f"{'TOTAL':<30} {len(combined_sales):<15} ${total_revenue_usd:>18,.2f}")
print("="*80)

# Top books by revenue
print("\n📚 TOP 15 BOOKS BY REVENUE (USD)\n")
print(f"{'Book Title':<50} {'Units':<10} {'Revenue (USD)':<20}")
print("-"*80)

book_revenue = {}
for idx, row in combined_sales.iterrows():
    title = row['Title'][:48]
    if title not in book_revenue:
        book_revenue[title] = {'units': 0, 'revenue': 0}
    
    currency = row['Currency']
    rate = rates.get(currency, EXCHANGE_RATES_HARDCODED.get(currency, 1.0))
    book_revenue[title]['units'] += row['Net Units Sold']
    book_revenue[title]['revenue'] += row['Royalty'] * rate

sorted_books = sorted(book_revenue.items(), key=lambda x: x[1]['revenue'], reverse=True)
for title, data in sorted_books[:15]:
    print(f"{title:<50} {data['units']:<10} ${data['revenue']:>18,.2f}")

print("-"*80)
total_units = combined_sales['Net Units Sold'].sum()
print(f"{'TOTAL':<50} {total_units:<10} ${total_revenue_usd:>18,.2f}")

# Show exact calculation example
print("\n" + "="*80)
print("🔢 CALCULATION EXAMPLE\n")
print("How the revenue was calculated:\n")

sample_row = combined_sales.iloc[0]
sample_currency = sample_row['Currency']
sample_royalty = sample_row['Royalty']
sample_rate = rates.get(sample_currency, EXCHANGE_RATES_HARDCODED.get(sample_currency, 1.0))
sample_usd = sample_royalty * sample_rate

print(f"Sample Transaction from source data:")
print(f"  Title:     {sample_row['Title'][:50]}")
print(f"  Royalty:   {sample_royalty:,.2f} {sample_currency}")
print(f"  Marketplace: {sample_row['Marketplace']}")
print(f"\nConversion:")
print(f"  {sample_royalty:,.2f} {sample_currency} × {sample_rate:.6f} (exchange rate) = ${sample_usd:,.2f} USD")
print("\n" + "="*80)

print(f"\n✅ Total Revenue Summary: ${total_revenue_usd:,.2f} USD\n")
print(f"✅ Based on {len(combined_sales)} transactions across {len(combined_sales['Currency'].unique())} currencies")
print(f"✅ From {len(combined_sales['Marketplace'].unique())} Amazon marketplaces\n")

print("="*80 + "\n")
