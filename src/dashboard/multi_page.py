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
        
        # Use authors dashboard as the shared Dash app
        self.app = self.authors_dashboard.app

        # Preserve layouts before we rebind callbacks
        self.public_layout = self.public_dashboard.app.layout
        self.authors_layout = self.authors_dashboard.app.layout

        # Rebind public callbacks onto the shared app so / uses public logic/IDs
        self.public_dashboard.app = self.app
        self.public_dashboard._register_callbacks()
        
        # Create new routing layout
        self._build_routing_layout()
        
        # Register routing callback
        self._register_routing_callback()

        # Allow callbacks from both layouts
        self.app.validation_layout = html.Div([
            self.app.layout,       # routing container
            self.public_layout,    # public page layout
            self.authors_layout    # authors page layout
        ])
    
    def _build_routing_layout(self):
        """Build layout with URL routing"""
        self.app.layout = dbc.Container([
            dcc.Location(id='multi-page-url', refresh=False),
            html.Div(id='multi-page-content'),
            html.Div(id='page-title-setter', style={"display": "none"})
        ], fluid=True)
    
    def _register_routing_callback(self):
        """Register routing callback"""
        self.app.callback(
            Output('multi-page-content', 'children'),
            Input('multi-page-url', 'pathname')
        )(self._route_content)

        # Client-side title switcher so each route has its own page title
        self.app.clientside_callback(
            """
            function(pathname) {
                const isAuthors = pathname && pathname.indexOf('/authors') !== -1;
                document.title = isAuthors ? 'Resulam Royalties Dashboard' : 'African Languages Books - Resulam';
                return '';
            }
            """,
            Output('page-title-setter', 'children'),
            Input('multi-page-url', 'pathname')
        )
    
    def _route_content(self, pathname):
        """Return the appropriate layout based on the current path."""
        if pathname and '/authors' in pathname:
            return self.authors_layout
        return self.public_dashboard.app.layout

    def run(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
        """Run the appropriate dashboard based on current context"""
        # For now, run the public dashboard as default
        # In production, the web server handles the routing
        if self.public_dashboard is None:
            self.public_dashboard = PublicDashboard(self.data)
        self.app = self.public_dashboard.app
        self.app.run(host=host, port=port, debug=debug)
    
    def run(self, host: str = "127.0.0.1", port: int = 8050, debug: bool = False):
        """Run the multi-page dashboard"""
        self.app.run(host=host, port=port, debug=debug)


def create_multi_page_dashboard(data: Dict[str, pd.DataFrame]) -> MultiPageDashboard:
    """Factory function to create multi-page dashboard"""
    return MultiPageDashboard(data)
