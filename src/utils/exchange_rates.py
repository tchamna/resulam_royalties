"""
Exchange rates utility module
Supports both hardcoded and live exchange rate fetching
"""

import requests
from typing import Dict, Optional
from datetime import datetime, timedelta
import json
from pathlib import Path

# Supported free APIs for exchange rates
AVAILABLE_APIS = {
    'exchangerate_api': 'https://api.exchangerate-api.com/v4/latest/',  # Free tier: 1500/month
    'open_exchange': 'https://openexchangerates.org/api/latest',  # Free tier: 1000/month
    'fixer': 'https://data.fixer.io/latest'  # Free tier: 100/month
}

class ExchangeRateManager:
    """Manages exchange rate fetching and caching"""
    
    def __init__(self, cache_dir: Optional[Path] = None, cache_hours: int = 24):
        """
        Initialize exchange rate manager
        
        Args:
            cache_dir: Directory to cache exchange rates (default: ./data)
            cache_hours: How long to cache rates before refreshing (default: 24 hours)
        """
        self.cache_dir = cache_dir or Path(__file__).parent.parent.parent / "data"
        self.cache_dir.mkdir(exist_ok=True)
        self.cache_file = self.cache_dir / "exchange_rates_cache.json"
        self.cache_hours = cache_hours
    
    def get_rates(self, base_currency: str = 'USD', 
                  use_live: bool = False,
                  hardcoded_fallback: Optional[Dict[str, float]] = None) -> Dict[str, float]:
        """
        Get exchange rates with fallback options
        
        Args:
            base_currency: Base currency for conversion (default: USD)
            use_live: If True, attempt to fetch live rates; otherwise use cache/hardcoded
            hardcoded_fallback: Hardcoded rates to use as fallback
            
        Returns:
            Dictionary of exchange rates
        """
        
        # Try cache first if available
        cached_rates = self._load_cache()
        if cached_rates and not use_live:
            print("✅ Using cached exchange rates")
            return cached_rates
        
        # Try live rates if requested
        if use_live:
            live_rates = self._fetch_live_rates(base_currency)
            if live_rates:
                self._save_cache(live_rates)
                print("✅ Using LIVE exchange rates (auto-cached)")
                return live_rates
            else:
                print("⚠️  Failed to fetch live rates, using fallback")
        
        # Use hardcoded fallback
        if hardcoded_fallback:
            print("ℹ️  Using hardcoded exchange rates")
            return hardcoded_fallback
        
        # Default minimal rates
        print("⚠️  No rates available, using defaults")
        return {'USD': 1.0}
    
    def _fetch_live_rates(self, base_currency: str = 'USD') -> Optional[Dict[str, float]]:
        """
        Attempt to fetch live exchange rates from API
        
        Args:
            base_currency: Base currency (default: USD)
            
        Returns:
            Dictionary of exchange rates or None if failed
        """
        
        # Try exchangerate-api (most reliable free option)
        try:
            url = f"{AVAILABLE_APIS['exchangerate_api']}{base_currency}"
            response = requests.get(url, timeout=5)
            response.raise_for_status()
            data = response.json()
            
            if 'rates' in data:
                rates = data['rates']
                # The API returns "how much is 1 base_currency worth in other currencies"
                # We need "how much is 1 foreign_currency worth in USD"
                # So we always invert: 1/rate gives us the reciprocal
                rates = {curr: 1/rate for curr, rate in rates.items()}
                print(f"📡 Successfully fetched rates from exchangerate-api (updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')})")
                return rates
        except Exception as e:
            print(f"⚠️  exchangerate-api failed: {str(e)}")
        
        return None
    
    def _load_cache(self) -> Optional[Dict[str, float]]:
        """Load cached exchange rates if available and not expired"""
        
        if not self.cache_file.exists():
            return None
        
        try:
            with open(self.cache_file, 'r') as f:
                cache_data = json.load(f)
            
            # Check if cache is still valid
            cached_time = datetime.fromisoformat(cache_data.get('timestamp', ''))
            age_hours = (datetime.now() - cached_time).total_seconds() / 3600
            
            if age_hours < self.cache_hours:
                return cache_data.get('rates', {})
            else:
                print(f"⚠️  Exchange rate cache expired ({age_hours:.1f} hours old)")
                return None
        except Exception as e:
            print(f"⚠️  Failed to load cache: {str(e)}")
            return None
    
    def _save_cache(self, rates: Dict[str, float]) -> None:
        """Save rates to cache file"""
        
        try:
            cache_data = {
                'timestamp': datetime.now().isoformat(),
                'rates': rates
            }
            with open(self.cache_file, 'w') as f:
                json.dump(cache_data, f, indent=2)
        except Exception as e:
            print(f"⚠️  Failed to save cache: {str(e)}")


def get_exchange_rates(use_live: bool = False,
                      hardcoded_fallback: Optional[Dict[str, float]] = None,
                      base_currency: str = 'USD') -> Dict[str, float]:
    """
    Convenience function to get exchange rates
    
    Args:
        use_live: If True, fetch live rates from API
        hardcoded_fallback: Fallback rates if live fetch fails
        base_currency: Base currency for conversion
        
    Returns:
        Dictionary of exchange rates to USD
    """
    manager = ExchangeRateManager()
    return manager.get_rates(
        base_currency=base_currency,
        use_live=use_live,
        hardcoded_fallback=hardcoded_fallback
    )


if __name__ == '__main__':
    """Test the exchange rate manager"""
    
    from src.config import EXCHANGE_RATES_HARDCODED
    
    print("\n" + "="*70)
    print("🔄 EXCHANGE RATE MANAGER - TEST")
    print("="*70 + "\n")
    
    # Test 1: Using hardcoded rates
    print("1️⃣  Hardcoded rates:")
    print("-" * 70)
    rates = get_exchange_rates(use_live=False, hardcoded_fallback=EXCHANGE_RATES_HARDCODED)
    for currency, rate in sorted(rates.items()):
        print(f"   {currency}: {rate} USD")
    
    # Test 2: Try live rates
    print("\n2️⃣  Attempting to fetch LIVE rates:")
    print("-" * 70)
    rates = get_exchange_rates(use_live=True, hardcoded_fallback=EXCHANGE_RATES_HARDCODED)
    for currency, rate in sorted(rates.items())[:5]:  # Show first 5
        print(f"   {currency}: {rate} USD")
    print(f"   ... (total {len(rates)} currencies)")
    
    print("\n" + "="*70)
    print("✅ Exchange rate manager ready to use!")
    print("="*70 + "\n")
