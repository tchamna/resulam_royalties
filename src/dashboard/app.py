"""
Modern Dash Dashboard Application
"""
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from typing import Dict
from pathlib import Path
import pandas as pd

from ..config import DASHBOARD_CONFIG, CURRENT_YEAR, LAST_YEAR, AUTHOR_NORMALIZATION
from ..visualization import SalesCharts, AuthorCharts, GeographicCharts, SummaryMetrics


def normalize_author_name(name: str) -> str:
    """Normalize author name using the AUTHOR_NORMALIZATION mapping"""
    if name in AUTHOR_NORMALIZATION:
        return AUTHOR_NORMALIZATION[name]
    return name


def get_unique_authors(authors_series: pd.Series) -> list:
    """Get unique authors removing display duplicates and applying normalization"""
    # Get unique values and remove exact duplicates that appear due to Unicode issues
    authors = authors_series.unique().tolist()
    
    # Normalize and deduplicate
    normalized = {}
    for author in authors:
        normalized_name = normalize_author_name(author)
        if normalized_name not in normalized:
            normalized[normalized_name] = True
    
    return sorted(normalized.keys())


def count_unique_normalized_authors(authors_series: pd.Series) -> int:
    """Count unique authors after normalizing - uses individual authors from exploded data"""
    return len(get_unique_authors(authors_series))


class ResulamDashboard:
    """Main dashboard application class"""
    
    def __init__(self, data: Dict[str, pd.DataFrame]):
        """
        Initialize dashboard with processed data
        
        Args:
            data: Dictionary containing processed dataframes
        """
        self.data = data
        self.royalties = data['royalties_history'].copy()
        self.royalties_exploded = data['royalties_exploded'].copy()
        
        # Ensure Year Sold column exists
        if 'Year Sold' not in self.royalties.columns:
            self.royalties['Year Sold'] = pd.to_datetime(self.royalties['Royalty Date']).dt.year
        if 'Year Sold' not in self.royalties_exploded.columns:
            self.royalties_exploded['Year Sold'] = pd.to_datetime(self.royalties_exploded['Royalty Date']).dt.year
        
        # Initialize Dash app with Bootstrap theme
        assets_path = Path(__file__).parent.parent.parent / 'assets'
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.BOOTSTRAP, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
            assets_folder=str(assets_path)
        )
        
        self.app.title = DASHBOARD_CONFIG['title']
        
        # Calculate metrics
        self.metrics = SummaryMetrics.calculate_metrics(self.royalties)
        
        # Get available years for filtering
        self.available_years = sorted(self.royalties['Year Sold'].unique().tolist())
        
        # Setup layout and callbacks
        self._create_layout()
        self._register_callbacks()
    
    def _create_layout(self):
        """Create the dashboard layout"""
        
        # Header
        header = dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.Div([
                        html.Img(
                            src="assets/resulam_logo_egg.png",
                            style={"height": "80px", "margin-bottom": "10px"}
                        )
                    ], className="text-center mb-2")
                ], width="auto", className="mx-auto")
            ], className="justify-content-center mb-2"),
            dbc.Row([
                dbc.Col([
                    html.H1(
                        "Resulam Royalties Dashboard",
                        className="text-center text-primary mb-4"
                    ),
                    html.P(
                        f"Book Sales Analysis: 2015 - {LAST_YEAR}",
                        className="text-center text-muted mb-4"
                    )
                ])
            ])
        ], fluid=True, className="bg-light py-4 mb-4")
        
        # Year filter section
        filter_section = dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Filter by Year:", className="fw-bold"),
                    dcc.Dropdown(
                        id="year-filter",
                        options=[
                            {"label": "All Years", "value": "all"}
                        ] + [
                            {"label": str(year), "value": year}
                            for year in self.available_years
                        ],
                        value="all",
                        clearable=False,
                        style={"width": "100%"}
                    )
                ], md=3)
            ], className="mb-3")
        ], fluid=True, className="py-3 mb-4")
        
        # Summary metrics cards (now dynamic based on filter)
        metrics_row = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("📖", className="text-center"),
                        html.H5("Total Books Sold", className="text-center text-muted"),
                        html.H2(id="metric-books-sold", className="text-center text-primary")
                    ])
                ], className="shadow-sm")
            ], lg=3, md=6, xs=12, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("💵", className="text-center"),
                        html.H5("Net Revenue", className="text-center text-muted"),
                        html.H2(id="metric-net-revenue", className="text-center text-info")
                    ])
                ], className="shadow-sm")
            ], lg=3, md=6, xs=12, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("📚", className="text-center"),
                        html.H5("Unique Titles", className="text-center text-muted"),
                        html.H2(id="metric-titles", className="text-center text-secondary")
                    ])
                ], className="shadow-sm")
            ], lg=3, md=6, xs=12, className="mb-3"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("✍️", className="text-center"),
                        html.H5("Contributing Authors", className="text-center text-muted"),
                        html.H2(id="metric-authors", className="text-center text-warning")
                    ])
                ], className="shadow-sm")
            ], lg=3, md=6, xs=12, className="mb-3")
        ], className="mb-4")
        
        # Tabs for different views
        tabs = dbc.Tabs([
            dbc.Tab(label="📊 Sales Overview", tab_id="sales"),
            dbc.Tab(label="📖 Books Analysis", tab_id="books"),
            dbc.Tab(label="✍️ Authors Analysis", tab_id="authors"),
            dbc.Tab(label="🌍 Geographic Distribution", tab_id="geography"),
        ], id="dashboard-tabs", active_tab="sales", className="mb-4")
        
        # Content area that changes based on selected tab
        content = html.Div(id="tab-content", className="mb-4")
        
        # Main layout
        self.app.layout = dbc.Container([
            header,
            filter_section,
            metrics_row,
            tabs,
            content,
            
            # Footer
            html.Hr(),
            html.Footer([
                html.P(
                    "© 2025 Resulam Books. Dashboard built with Dash & Plotly.",
                    className="text-center text-muted"
                )
            ], className="mt-4 mb-4")
        ], fluid=True)
    
    def _register_callbacks(self):
        """Register all dashboard callbacks"""
        
        @self.app.callback(
            Output("metric-books-sold", "children"),
            Output("metric-net-revenue", "children"),
            Output("metric-titles", "children"),
            Output("metric-authors", "children"),
            Input("year-filter", "value")
        )
        def update_metrics(selected_year):
            """Update metrics based on selected year"""
            if selected_year == "all":
                filtered_df = self.royalties
                filtered_exploded = self.royalties_exploded
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'] == selected_year]
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'] == selected_year]
            
            metrics = SummaryMetrics.calculate_metrics(filtered_df, filtered_exploded)
            
            return (
                f"{metrics['total_books_sold']:,}",
                f"${metrics['net_revenue_usd']:,.2f}",
                str(metrics['unique_titles']),
                str(metrics['unique_authors'])
            )
        
        @self.app.callback(
            Output("tab-content", "children"),
            Input("dashboard-tabs", "active_tab"),
            Input("year-filter", "value")
        )
        def render_tab_content(active_tab, selected_year):
            """Render content based on active tab and year filter"""
            
            # Filter data based on selected year
            if selected_year == "all":
                filtered_royalties = self.royalties
                filtered_exploded = self.royalties_exploded
            else:
                filtered_royalties = self.royalties[self.royalties['Year Sold'] == selected_year]
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'] == selected_year]
            
            if active_tab == "sales":
                return self._create_sales_tab(filtered_royalties)
            elif active_tab == "books":
                return self._create_books_tab(filtered_royalties)
            elif active_tab == "authors":
                return self._create_authors_tab(filtered_exploded)
            elif active_tab == "geography":
                return self._create_geography_tab(filtered_royalties)
            
            return html.Div("Select a tab to view content")
    
    def _create_sales_tab(self, data=None):
        """Create sales overview tab content"""
        if data is None:
            data = self.royalties
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📈 Sales Trend by Year")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.books_sold_per_year(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("🌐 Sales by Language")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.sales_by_language_stacked(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ])
        ], fluid=True)
    
    def _create_books_tab(self, data=None):
        """Create books analysis tab content"""
        if data is None:
            data = self.royalties
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📚 Total Sales by Book")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.sales_by_book_horizontal(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📅 Sales by Book (Yearly View)")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.sales_by_book_with_year_filter(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ])
        ], fluid=True)
    
    def _create_authors_tab(self, data=None):
        """Create authors analysis tab content"""
        if data is None:
            data = self.royalties_exploded
        
        # Get the non-exploded data for metrics
        if data.shape[0] == self.royalties_exploded.shape[0]:
            # Data is exploded, use non-exploded for metrics
            metrics_data = self.royalties
        else:
            # Data is filtered exploded, get corresponding non-exploded data
            year = data['Year Sold'].iloc[0] if len(data) > 0 else None
            if year:
                metrics_data = self.royalties[self.royalties['Year Sold'] == year]
            else:
                metrics_data = self.royalties
        
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("💰 Royalties by Author (Top 20)")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=AuthorCharts.royalties_by_author(
                                    data,
                                    top_n=20
                                ),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📖 Books Sold by Author (Top 20)")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=AuthorCharts.books_sold_by_author(
                                    data,
                                    top_n=20
                                ),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📊 Author Statistics")),
                        dbc.CardBody([
                            dbc.Table([
                                html.Thead(html.Tr([
                                    html.Th("Metric"),
                                    html.Th("Value")
                                ])),
                                html.Tbody([
                                    html.Tr([
                                        html.Td("Total Authors"),
                                        html.Td(str(count_unique_normalized_authors(data['Authors_Exploded'])))
                                    ]),
                                    html.Tr([
                                        html.Td("Total Royalties Shared"),
                                        html.Td(f"${(metrics_data['Royalty per Author (USD)'].sum() * 0.8):,.2f}")
                                    ]),
                                    html.Tr([
                                        html.Td("Resulam Share"),
                                        html.Td(f"${((metrics_data['Royalty USD'].sum() * 0.8) - (metrics_data['Royalty per Author (USD)'].sum() * 0.8)):,.2f}")
                                    ])
                                ])
                            ], bordered=True, hover=True, responsive=True, striped=True),
                            html.Hr(),
                            html.H5("Author Names:", className="mt-3 mb-2"),
                            html.Ol([
                                html.Li(author, className="text-muted")
                                for author in get_unique_authors(data['Authors_Exploded'])
                            ], style={"font-size": "0.9em", "line-height": "1.6"})
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ])
        ], fluid=True)
    
    def _create_geography_tab(self, data=None):
        """Create geographic distribution tab content"""
        if data is None:
            data = self.royalties
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("🌍 Sales Distribution by Marketplace")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=GeographicCharts.sales_by_marketplace(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("💵 Revenue by Marketplace")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=GeographicCharts.revenue_by_marketplace(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6)
            ])
        ], fluid=True)
    
    def run(self, debug: bool = None, host: str = None, port: int = None):
        """Run the dashboard server"""
        debug = debug if debug is not None else DASHBOARD_CONFIG['debug']
        host = host if host is not None else DASHBOARD_CONFIG['host']
        port = port if port is not None else DASHBOARD_CONFIG['port']
        
        print(f"\n{'='*60}")
        print(f"🚀 Resulam Royalties Dashboard Starting...")
        print(f"{'='*60}")
        print(f"📊 Dashboard URL: http://localhost:{port}")
        print(f"📈 Data Period: 2015 - {LAST_YEAR}")
        print(f"📚 Total Books: {self.metrics['total_books_sold']:,}")
        print(f"💰 Total Revenue: ${self.metrics['total_revenue_usd']:,.2f}")
        print(f"{'='*60}\n")
        
        self.app.run(debug=debug, host=host, port=port)


def create_dashboard(data: Dict[str, pd.DataFrame]) -> ResulamDashboard:
    """
    Factory function to create dashboard instance
    
    Args:
        data: Dictionary containing processed dataframes
        
    Returns:
        ResulamDashboard instance
    """
    return ResulamDashboard(data)
