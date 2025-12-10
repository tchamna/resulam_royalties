## Exchange Rates Configuration Guide

### Overview
The dashboard now supports **both hardcoded and live exchange rates** for converting royalties to USD.

### Quick Start

#### 1. View Exchange Rate Settings
```python
# In src/config.py
USE_LIVE_RATES = False  # Change to True for live rates
EXCHANGE_RATES_HARDCODED = {
    'EUR': 1.0,
    'JPY': 0.0073,
    'USD': 1.0,
    'CAD': 0.8,
    'GBP': 1.3,
    ...
}
```

#### 2. Interactive Configuration Tool
Run the interactive tool to switch between modes:
```bash
python configure_exchange_rates.py
```

This tool allows you to:
- View hardcoded rates
- Fetch live rates from API
- Compare both sets
- Update config.py automatically

### Where Revenue Comes From

Your revenue is calculated from the **"Combined Sales" sheet** in:
```
G:\My Drive\Mbú'ŋwɑ̀'nì\RoyaltiesResulam\KDP_OrdersResulamBookSales2015_2024RoyaltiesReportsHistory.xlsx
```

The source data contains:
- **Royalty** column: The royalty amount in the transaction currency
- **Currency** column: The currency code (EUR, JPY, USD, CAD, GBP, etc.)
- **Marketplace** column: Where the sale happened (Amazon.com, Amazon.fr, etc.)

### Revenue Calculation Formula

```
Total Revenue (USD) = SUM(Royalty × Exchange_Rate) for all transactions

Where:
- Royalty = Amount from source data (in original currency)
- Exchange_Rate = Conversion rate to USD
```

### Currency Conversion Methods

#### Method 1: Hardcoded Rates (Default - Offline)
✅ **Pros:**
- Works without internet
- Consistent and predictable
- No API rate limits
- Fast processing

❌ **Cons:**
- May become outdated over time
- Manual updates needed
- Less accurate for older historical data

**Use when:** You want fast, reliable conversions without internet dependency

#### Method 2: Live Rates (From API - Online)
✅ **Pros:**
- Always up-to-date
- Accurate current conversion rates
- Auto-cached for 24 hours
- Better for recent data

❌ **Cons:**
- Requires internet connection
- Depends on API availability
- Slightly slower first time
- API rate limits (1500/month free)

**Use when:** You want the most accurate current rates

### Supported Currencies

Both methods support these currencies:
- **EUR** (Euro)
- **JPY** (Japanese Yen)
- **USD** (US Dollar)
- **CAD** (Canadian Dollar)
- **GBP** (British Pound)
- **BRL** (Brazilian Real)
- **AUD** (Australian Dollar)
- **PLN** (Polish Zloty)
- **SEK** (Swedish Krona)
- **INR** (Indian Rupee)

### How to Switch Methods

**Option A: Direct Edit**
1. Open `src/config.py`
2. Change: `USE_LIVE_RATES = False` to `True` (or vice versa)
3. Save and restart the dashboard

**Option B: Interactive Tool**
```bash
python configure_exchange_rates.py
# Then select option 2 to update config automatically
```

### Testing Exchange Rates

Test both methods without running the full dashboard:
```bash
python -m src.utils.exchange_rates
```

This shows:
- Hardcoded rates
- Live rates (fetched from API)
- Comparison between both

### Example Revenue Breakdown

If you have sales in multiple currencies:
```
EUR 1,000.00 × 1.0  = $1,000.00 USD
GBP   500.00 × 1.3  =   $650.00 USD
JPY 100,000 × 0.0073 =   $730.00 USD
---
Total Revenue = $2,380.00 USD
```

### Cache Management

Live rates are automatically cached:
- **Location:** `data/exchange_rates_cache.json`
- **Duration:** 24 hours
- **Auto-refresh:** When cache expires or on next run

### Troubleshooting

**Q: Dashboard shows different revenue after switching to live rates?**
A: This is normal! Historical exchange rates change over time. Live rates might differ from hardcoded rates, especially for older transactions.

**Q: Live rates failing, but I need them?**
A: The system automatically falls back to hardcoded rates. Check:
- Internet connection
- API service availability (exchangerate-api.com)
- Check cache: `data/exchange_rates_cache.json`

**Q: How accurate are the hardcoded rates?**
A: They're approximate average rates. For precise accounting, use live rates or verify against your actual transaction rates in the Excel file.

### Advanced: Using Custom Rates

To use custom exchange rates, edit `src/config.py`:

```python
EXCHANGE_RATES_HARDCODED = {
    'EUR': 1.08,  # Your custom rate
    'GBP': 1.27,
    'JPY': 0.0068,
    # ... etc
}
```

Then run the dashboard - it will use your custom rates.

---

**Last Updated:** December 10, 2025
**Dashboard Version:** 2.0 (with live rates support)
