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
        
        # Use authors dashboard as base since it has all features
        self.app = self.authors_dashboard.app
        
        # Store original layout
        self.authors_layout = self.authors_dashboard.app.layout
        
        # Create new routing layout
        self._build_routing_layout()
        
        # Register routing callback
        self._register_routing_callback()
    
    def _build_routing_layout(self):
        """Build layout with URL routing"""
        self.app.layout = dbc.Container([
            dcc.Location(id='multi-page-url', refresh=False),
            html.Div(id='multi-page-content'),
            html.Div(id='page-title-setter', style={"display": "none"})
        ], fluid=True)
    
    def _register_routing_callback(self):
        """Register routing callback"""
        @self.app.callback(
            Output('multi-page-content', 'children'),
            Input('multi-page-url', 'pathname')
        )
        def route_content(pathname):
            if pathname and '/authors' in pathname:
                # Return full authors dashboard content
                return self.authors_layout
            else:
                # Return simplified public dashboard content
                return self.public_dashboard.app.layout

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
