#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Main application entry point for Resulam Royalties Dashboard

This is the refactored, production-ready version of the original script.
Run this file to start the dashboard server.
"""
import sys
import os
import argparse
from pathlib import Path
from flask import redirect
from werkzeug.middleware.dispatcher import DispatcherMiddleware

# Add src to path
sys.path.insert(0, str(Path(__file__).parent))

# Ensure UTF-8 output encoding
if sys.stdout.encoding != 'utf-8':
    sys.stdout.reconfigure(encoding='utf-8')
if sys.stderr.encoding != 'utf-8':
    sys.stderr.reconfigure(encoding='utf-8')

# Debug: Show environment variables
print(f"\n🔍 DEBUG: USE_S3_DATA environment variable = {os.getenv('USE_S3_DATA', 'NOT SET')}")

from src.data import load_and_process_all_data
from src.dashboard import create_dashboard, create_public_dashboard, create_multi_page_dashboard
from src.utils.helpers import export_processed_data, validate_data_files
from src.utils.s3_sync import sync_data_on_startup
from src.config import (
    BOOKS_DATABASE_PATH,
    ROYALTIES_HISTORY_PATH,
    USE_LIVE_RATES
)


def _run_public_app(data, host: str, port: int, debug: bool):
    """Run public dashboard in its own process."""
    dashboard = create_public_dashboard(data)
    dashboard.run(host=host, port=port, debug=debug)


def _run_authors_app(data, host: str, port: int, debug: bool):
    """Run authors dashboard in its own process."""
    dashboard = create_dashboard(data)
    dashboard.run(host=host, port=port, debug=debug)


def main():
    """Main application function"""
    
    # Create startup marker file for container restart detection
    import time
    marker_file = '/tmp/.container_start_time' if os.name != 'nt' else 'C:\\temp\\.container_start_time'
    try:
        os.makedirs(os.path.dirname(marker_file), exist_ok=True)
        with open(marker_file, 'w') as f:
            f.write(str(time.time()))
        print(f"\n✅ Created startup marker: {marker_file}")
    except Exception as e:
        print(f"\n⚠️  Could not create startup marker: {e}")
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description='Resulam Royalties Dashboard')
    parser.add_argument('--host', type=str, default='127.0.0.1', help='Host to bind to (default: 127.0.0.1)')
    parser.add_argument('--port', type=int, default=8050, help='Port to bind to (default: 8050)')
    parser.add_argument('--authors-port', type=int, default=8051, help='Port for authors app when running both')
    parser.add_argument('--public-port', type=int, default=8050, help='Port for public app when running both')
    parser.add_argument('--debug', action='store_true', help='Enable debug mode')
    parser.add_argument('--public', action='store_true', help='Run public dashboard only')
    parser.add_argument('--authors', action='store_true', help='Run authors dashboard only')
    parser.add_argument('--dual', action='store_true', default=False, help='Run public and authors dashboards on separate ports')
    args = parser.parse_args()
    
    print("\n" + "="*70)
    print("📚 RESULAM ROYALTIES DASHBOARD")
    print("="*70)
    
    # Sync data from S3 if configured
    print("\n📡 Checking for S3 data sync...")
    sync_data_on_startup()
    
    # Show exchange rate configuration
    rate_source = "🌐 LIVE (from API)" if USE_LIVE_RATES else "🔒 HARDCODED"
    print(f"\n💱 Exchange Rates: {rate_source}")
    print(f"   ℹ️  To switch, run: python configure_exchange_rates.py")
    
    # Validate data files exist
    print("\n🔍 Validating data files...")
    required_files = [
        BOOKS_DATABASE_PATH,
        ROYALTIES_HISTORY_PATH
    ]
    
    if not validate_data_files(required_files):
        print("\n❌ Please ensure all required data files are in place.")
        print("   Update paths in src/config.py if needed.")
        return
    
    # Load and process data
    print("\n📊 Loading and processing data...")
    try:
        data = load_and_process_all_data()
        print(f"✅ Data loaded successfully!")
        print(f"   - Books: {len(data['books'])} records")
        print(f"   - Royalties: {len(data['royalties_history'])} records")
        print(f"   - Authors (exploded): {len(data['royalties_exploded'])} records")
    except Exception as e:
        print(f"\n❌ Error loading data: {e}")
        print("   Please check your data files and try again.")
        return
    
    # Export processed data
    print("\n💾 Exporting processed data...")
    try:
        exported_files = export_processed_data(data)
        print(f"✅ Processed data exported successfully!")
    except Exception as e:
        print(f"⚠️  Warning: Could not export data: {e}")
    
    # Create and run dashboard
    print("\n🚀 Starting dashboard...")
    try:
        if args.dual:
            # Run two independent Dash apps on separate ports
            from multiprocessing import Process

            print("   Mode: DUAL INSTANCES")
            print(f"   Public  : http://{args.host}:{args.public_port}/")
            print(f"   Authors : http://{args.host}:{args.authors_port}/")
            p1 = Process(target=_run_public_app, args=(data, args.host, args.public_port, args.debug))
            p2 = Process(target=_run_authors_app, args=(data, args.host, args.authors_port, args.debug))
            p1.start()
            p2.start()
            p1.join()
            p2.join()
        elif args.public:
            print("   Mode: PUBLIC DASHBOARD ONLY")
            dashboard = create_public_dashboard(data)
            dashboard.run(host=args.host, port=args.port, debug=args.debug)
        elif args.authors:
            print("   Mode: AUTHORS DASHBOARD ONLY")
            dashboard = create_dashboard(data)
            dashboard.run(host=args.host, port=args.port, debug=args.debug)
        else:
            print("   Mode: SINGLE PORT (WSGI dispatcher)")
            print("   Routes:")
            print(f"     - http://{args.host}:{args.port}/        (Public)")
            print(f"     - http://{args.host}:{args.port}/authors/ (Authors)")

            # Build two independent Dash apps and dispatch them via Werkzeug
            public_dashboard = create_public_dashboard(data, prefix="/")
            authors_dashboard = create_dashboard(data, prefix="/authors/")

            # Use the public Dash Flask server as the base app
            server = public_dashboard.app.server

            @server.route("/authors")
            def _authors_redirect():
                return redirect("/authors/")

            # Mount the authors Dash app at /authors
            server.wsgi_app = DispatcherMiddleware(
                server.wsgi_app,
                {
                    "/authors": authors_dashboard.app.server,
                },
            )

            server.run(host=args.host, port=args.port, debug=args.debug)
    except Exception as e:
        print(f"\n❌ Error starting dashboard: {e}")
        raise


if __name__ == "__main__":
    main()
