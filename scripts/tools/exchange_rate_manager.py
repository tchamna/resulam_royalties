#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
Interactive Exchange Rate Configuration Tool
Allows user to switch between hardcoded and live exchange rates
"""

import sys
from pathlib import Path
from src.config import EXCHANGE_RATES_HARDCODED
from src.utils.exchange_rates import get_exchange_rates

def display_menu():
    """Display the main menu"""
    print("\n" + "="*70)
    print("💱 EXCHANGE RATE CONFIGURATION")
    print("="*70)
    print("\nChoose how to get exchange rates:\n")
    print("1. 🔒 Use HARDCODED rates (offline, no API calls)")
    print("2. 🌐 Use LIVE rates from API (requires internet)")
    print("3. 📊 View current rates")
    print("4. 📝 Update config.py with your choice")
    print("5. ❌ Exit\n")

def show_rates(use_live=False):
    """Display exchange rates"""
    print("\n" + "-"*70)
    rates = get_exchange_rates(
        use_live=use_live,
        hardcoded_fallback=EXCHANGE_RATES_HARDCODED
    )
    
    print("\n📋 Exchange Rates to USD:\n")
    for currency in sorted(rates.keys()):
        rate = rates[currency]
        print(f"   {currency:5s} → {rate:10.6f} USD")
    print("\n" + "-"*70)

def update_config(use_live):
    """Update config.py with the user's choice"""
    config_path = Path(__file__).parent / "src" / "config.py"
    
    with open(config_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Replace the USE_LIVE_RATES value
    old_value = "USE_LIVE_RATES = False" if not use_live else "USE_LIVE_RATES = True"
    new_value = "USE_LIVE_RATES = True" if use_live else "USE_LIVE_RATES = False"
    
    if old_value in content:
        content = content.replace(old_value, new_value)
        with open(config_path, 'w', encoding='utf-8') as f:
            f.write(content)
        
        rate_type = "LIVE" if use_live else "HARDCODED"
        print(f"\n✅ Config updated to use {rate_type} rates")
        return True
    else:
        print("\n⚠️  Could not find USE_LIVE_RATES in config.py")
        return False

def main():
    """Main function"""
    print("\n" + "="*70)
    print("🚀 RESULAM ROYALTIES - EXCHANGE RATE MANAGER")
    print("="*70)
    
    while True:
        display_menu()
        choice = input("Enter your choice (1-5): ").strip()
        
        if choice == '1':
            print("\n✅ Selected: HARDCODED rates")
            show_rates(use_live=False)
            if input("\nUpdate config.py? (y/n): ").lower() == 'y':
                update_config(use_live=False)
        
        elif choice == '2':
            print("\n✅ Selected: LIVE rates (fetching...)")
            show_rates(use_live=True)
            if input("\nUpdate config.py? (y/n): ").lower() == 'y':
                update_config(use_live=True)
        
        elif choice == '3':
            use_live = input("\nFetch LIVE rates? (y/n): ").lower() == 'y'
            show_rates(use_live=use_live)
        
        elif choice == '4':
            print("\n" + "="*70)
            print("📝 UPDATE CONFIG")
            print("="*70)
            mode = input("\nUse LIVE (l) or HARDCODED (h) rates? ").lower().strip()
            if mode == 'l':
                update_config(use_live=True)
            elif mode == 'h':
                update_config(use_live=False)
            else:
                print("Invalid choice")
        
        elif choice == '5':
            print("\n👋 Goodbye!\n")
            break
        
        else:
            print("\n❌ Invalid choice. Please try again.")

if __name__ == '__main__':
    try:
        main()
    except KeyboardInterrupt:
        print("\n\n👋 Exiting...\n")
        sys.exit(0)
