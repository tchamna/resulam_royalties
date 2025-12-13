"""
Multi-page Dash application supporting both public and authors dashboards
Routes:
  - / : Public dashboard (Purchase + Sales Overview)
  - /authors : Internal authors analytics dashboard
"""
import dash
from dash import html, dcc, Input, Output
import dash_bootstrap_components as dbc
from typing import Dict
from pathlib import Path
import pandas as pd

from ..config import DASHBOARD_CONFIG, CURRENT_YEAR, BOOKS_DATABASE_PATH
from .public import PublicDashboard
from .app import ResulamDashboard


class MultiPageDashboard:
    """Multi-page dashboard combining public and authors views"""
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        """Initialize multi-page dashboard with both public and full versions"""
        # Create both dashboard instances
        self.public_dashboard = PublicDashboard(data)
        self.authors_dashboard = ResulamDashboard(data)
        
        # Use the public dashboard's app as the base (they both have their own Flask servers with webhooks)
        self.app = self.public_dashboard.app
        
        # Register webhook blueprint from authors dashboard if not already registered
        import os
        if hasattr(self.authors_dashboard.app.server, 'blueprints'):
            for name, blueprint in list(self.authors_dashboard.app.server.blueprints.items()):
                if name not in self.app.server.blueprints:
                    try:
                        self.app.server.register_blueprint(blueprint)
                    except Exception:
                        pass
        
        # Save original public layout
        self.public_layout = self.public_dashboard.app.layout
        
        # Build new multi-page layout with routing
        self._build_layout()
        
        # Register routing callback
        self._register_callbacks()
    
    def _build_layout(self):
        """Build multi-page layout with URL routing"""
        # Create a wrapper layout that includes URL routing
        self.app.layout = dbc.Container([
            dcc.Location(id='url', refresh=False),
            html.Div(id='page-content')
        ], fluid=True)
    
    def _register_callbacks(self):
        """Register callback to route between dashboards based on URL"""
        
        @self.app.callback(
            Output('page-content', 'children'),
            Input('url', 'pathname')
        )
        def display_page(pathname):
            # Route based on pathname
            if pathname and '/authors' in pathname:
                # Return the authors dashboard layout
                return self.authors_dashboard.app.layout
            else:
                # Return the public dashboard layout  
                return self.public_layout
        
        # Copy callbacks from both dashboards using the app's callback registry
        # This ensures all callbacks are available regardless of which layout is displayed
        try:
            # Get public dashboard callbacks
            for callback_id, callback_func in self.public_dashboard.app._callbacks.items():
                if callback_id not in self.app._callbacks:
                    self.app._callbacks[callback_id] = callback_func
        except Exception:
            pass
        
        try:
            # Get authors dashboard callbacks  
            for callback_id, callback_func in self.authors_dashboard.app._callbacks.items():
                if callback_id not in self.app._callbacks:
                    self.app._callbacks[callback_id] = callback_func
        except Exception:
            pass
    
    def run(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
        """Run the multi-page dashboard"""
        self.app.run(host=host, port=port, debug=debug)


def create_multi_page_dashboard(data: Dict[str, pd.DataFrame]) -> MultiPageDashboard:
    """Factory function to create multi-page dashboard"""
    return MultiPageDashboard(data)

