"""
Modern Dash Dashboard Application
"""
import dash
from dash import html, dcc, Input, Output, State
import dash_bootstrap_components as dbc
from typing import Dict
from pathlib import Path
import pandas as pd
import math

from ..config import DASHBOARD_CONFIG, CURRENT_YEAR, LAST_YEAR, AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE
from ..visualization import SalesCharts, AuthorCharts, GeographicCharts, SummaryMetrics
from ..visualization.earning_history import EarningHistoryCharts


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
        # EXCLUDE "Resulam" - it's the company, not an author
        if normalized_name not in normalized and normalized_name.lower() != "resulam":
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
        
        # Initialize Dash app with Bootstrap theme (DARKLY for dark mode by default)
        assets_path = Path(__file__).parent.parent.parent / 'assets'
        self.app = dash.Dash(
            __name__,
            external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
            assets_folder=str(assets_path)
        )
        
        # Register webhook blueprint for SNS notifications
        try:
            from ..api import webhooks_bp
            self.app.server.register_blueprint(webhooks_bp)
            print("✅ Webhook endpoints registered: /api/s3-webhook")
        except Exception as e:
            print(f"⚠️  Warning: Could not register webhooks: {e}")
        
        # Add custom CSS for theme switching
        self.app.index_string = '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                {%favicon%}
                {%css%}
                <style>
                    body.light-mode {
                        background-color: #f8f9fa !important;
                        color: #212529 !important;
                    }
                    body.light-mode .card {
                        background-color: #ffffff !important;
                        color: #212529 !important;
                    }
                    body.light-mode h1, body.light-mode h2, body.light-mode h3, 
                    body.light-mode h4, body.light-mode h5 {
                        color: #212529 !important;
                    }
                    body.light-mode .text-white {
                        color: #212529 !important;
                    }
                    body.light-mode .text-light {
                        color: #212529 !important;
                    }
                    body.light-mode .text-muted {
                        color: #6c757d !important;
                    }
                    body.light-mode .bg-dark {
                        background-color: #f8f9fa !important;
                    }
                    body.light-mode .card-header,
                    body.light-mode .card-body {
                        background-color: #ffffff !important;
                        color: #212529 !important;
                    }
                    body.light-mode .card {
                        border-color: #dee2e6 !important;
                    }
                    body.light-mode .card h4,
                    body.light-mode .card h5 {
                        color: #212529 !important;
                    }
                    
                    /* Dropdown styling - target Dash Dropdown component */
                    div.dash-dropdown {
                        width: 100%;
                    }
                    
                    div.dash-dropdown .Select-control {
                        background-color: white !important;
                        border-color: #ddd !important;
                        color: #212529 !important;
                    }
                    
                    div.dash-dropdown .Select-value {
                        color: #212529 !important;
                    }
                    
                    div.dash-dropdown .Select-placeholder {
                        color: #999 !important;
                    }
                    
                    div.dash-dropdown .Select-input input {
                        color: #212529 !important;
                    }
                    
                    div.dash-dropdown .Select-menu-outer {
                        background-color: white !important;
                        color: #212529 !important;
                        border-color: #ddd !important;
                    }
                    
                    div.dash-dropdown .Select-option {
                        color: #212529 !important;
                        background-color: white !important;
                    }
                    
                    div.dash-dropdown .Select-option:hover {
                        background-color: #f0f0f0 !important;
                        color: #212529 !important;
                    }
                    
                    div.dash-dropdown .Select-option.is-selected {
                        background-color: #0066cc !important;
                        color: white !important;
                    }
                    
                    div.dash-dropdown .Select-option.is-focused {
                        background-color: #f0f0f0 !important;
                        color: #212529 !important;
                    }
                </style>
            </head>
            <body>
                {%app_entry%}
                <footer>
                    {%config%}
                    {%scripts%}
                    {%renderer%}
                </footer>
            </body>
        </html>
        '''
        
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
                        className="text-center text-light mb-4"
                    ),
                    html.P(
                        f"Book Sales Analysis: 2015 - {CURRENT_YEAR}",
                        className="text-center text-muted mb-4"
                    )
                ], width=10),
                dbc.Col([
                    dbc.Button(
                        html.I(className="fas fa-sun", id="theme-icon"),
                        id="theme-toggle-btn",
                        color="light",
                        outline=True,
                        size="lg",
                        className="mt-2"
                    )
                ], width=2, className="text-end")
            ]),
            dcc.Store(id="theme-store", data="dark")
        ], fluid=True, className="bg-dark py-4 mb-4", id="header-container")
        
        # Year filter section with dropdown multi-select
        years_reversed = sorted(self.available_years, reverse=True)
        
        # Get unique languages for language filter
        all_languages = sorted(self.royalties['Language'].unique().tolist())
        
        filter_section = dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Label("Filter by Year:", className="fw-bold"),
                    dcc.Dropdown(
                        id="year-filter",
                        options=[{"label": "Life time", "value": "lifetime"}] + 
                                [{"label": str(year), "value": year} for year in years_reversed],
                        value=CURRENT_YEAR,  # Default to current year
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    ),
                    dcc.Store(id="year-filter-store", data=[CURRENT_YEAR])  # Store current year by default
                ], md=6),
                dbc.Col([
                    dbc.Label("Filter by Language:", className="fw-bold"),
                    dcc.Dropdown(
                        id="language-filter",
                        options=[{"label": "All Languages", "value": "all"}] + [
                            {"label": lang, "value": lang} for lang in all_languages
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    )
                ], md=6)
            ], className="mb-3")
        ], fluid=True, className="py-3 mb-4")
        
        # Summary metrics cards (now dynamic based on filter)
        metrics_row = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("📖", className="text-center"),
                        html.H5("Total Books Sold", className="text-center", style={"color": "#ffffff", "fontWeight": "600"}),
                        html.H2(id="metric-books-sold", className="text-center", style={"color": "#00DDFF", "fontWeight": "700", "fontSize": "2.5rem"})
                    ])
                ], className="shadow-sm")
            ], style={"flex": "1 1 20%"}, className="mb-3 ps-1 pe-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("🔄", className="text-center"),
                        html.H5("Return Books", className="text-center", style={"color": "#ffffff", "fontWeight": "600"}),
                        html.H2(id="metric-returns", className="text-center", style={"color": "#FF3333", "fontWeight": "700", "fontSize": "2.5rem"})
                    ])
                ], className="shadow-sm")
            ], style={"flex": "1 1 20%"}, className="mb-3 ps-1 pe-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("💵", className="text-center"),
                        html.H5("Net Revenue", className="text-center", style={"color": "#ffffff", "fontWeight": "600"}),
                        html.H2(id="metric-net-revenue", className="text-center", style={"color": "#00DDFF", "fontWeight": "700", "fontSize": "2.5rem"})
                    ])
                ], className="shadow-sm")
            ], style={"flex": "1 1 20%"}, className="mb-3 ps-1 pe-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("📚", className="text-center"),
                        html.H5("Unique Titles", className="text-center", style={"color": "#ffffff", "fontWeight": "600"}),
                        html.H2(id="metric-titles", className="text-center", style={"color": "#888888", "fontWeight": "700", "fontSize": "2.5rem"})
                    ])
                ], className="shadow-sm")
            ], style={"flex": "1 1 20%"}, className="mb-3 ps-1 pe-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.H4("✍️", className="text-center"),
                        html.H5("Contributing Authors", className="text-center", style={"color": "#ffffff", "fontWeight": "600"}),
                        html.H2(id="metric-authors", className="text-center", style={"color": "#FFDD00", "fontWeight": "700", "fontSize": "2.5rem"})
                    ])
                ], className="shadow-sm")
            ], style={"flex": "1 1 20%"}, className="mb-3 ps-1 pe-1")
        ], className="mb-4 g-0", style={"display": "flex", "flexWrap": "nowrap"})
        
        # Sales Trend Chart (2015-2025)
        sales_trend_section = dbc.Card([
            dbc.CardHeader(html.H5(id="sales-trend-title", className="mb-0")),
            dbc.CardBody([
                dcc.Loading(
                    id="loading-trend-chart",
                    type="default",
                    children=dcc.Graph(id="sales-trend-chart")
                )
            ])
        ], className="shadow-sm mb-4")
        
        # Sales by Language Chart
        language_display_options = (
            [{"label": "All (Stacked)", "value": "all_stacked"},
             {"label": "All (Grouped)", "value": "all_grouped"}] +
            [{"label": lang, "value": f"language::{lang}"} for lang in all_languages]
        )

        sales_by_language_section = dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    dbc.Col(html.H5("🌐 Sales by Language", className="mb-0"), md=8, xs=12),
                    dbc.Col(
                        dcc.Dropdown(
                            id="sales-language-display-mode",
                            options=language_display_options,
                            value="all_stacked",
                            searchable=True,
                            clearable=False,
                            style={"minWidth": "220px", "width": "100%"}
                        ),
                        md=4,
                        xs=12,
                        className="text-md-end"
                    )
                ], align="center", className="g-2"),
                className="py-2"
            ),
            dbc.CardBody([
                dcc.Loading(
                    id="loading-sales-chart",
                    type="default",
                    children=dcc.Graph(id="sales-by-language-chart")
                )
            ])
        ], className="shadow-sm mb-4")
        
        # Returns by Language Chart
        returns_by_language_section = dbc.Card([
            dbc.CardHeader(html.H5(id="returns-title", children="🌐 Returned Books", className="mb-0")),
            dbc.CardBody([
                dcc.Loading(
                    id="loading-returns-chart",
                    type="default",
                    children=dcc.Graph(id="returns-by-language-chart")
                )
            ])
        ], className="shadow-sm mb-4")

        # Group sales overview elements so they can be toggled per tab
        sales_overview_section = html.Div([
            metrics_row,
            sales_trend_section,
            sales_by_language_section,
            returns_by_language_section
        ], id="sales-overview-section")
        
        # Tabs for different views
        tabs = dbc.Tabs([
            dbc.Tab(label="📊 Sales Overview", tab_id="sales"),
            dbc.Tab(label="📖 Books Analysis", tab_id="books"),
            dbc.Tab(label="✍️ Authors Analysis", tab_id="authors"),
            dbc.Tab(label="📈 Earning History", tab_id="trends"),
            dbc.Tab(label="🌍 Geographic Distribution", tab_id="geography"),
        ], id="dashboard-tabs", active_tab="sales", className="mb-4")
        
        # Content area that changes based on selected tab
        content = html.Div(id="tab-content", className="mb-4")
        
        # Main layout
        self.app.layout = dbc.Container([
            header,
            filter_section,
            tabs,
            sales_overview_section,
            content,
            
            # Interval component to check for container restarts (every 10 seconds for faster detection)
            dcc.Interval(
                id='refresh-interval',
                interval=10*1000,  # 10 seconds in milliseconds
                n_intervals=0
            ),
            
            # Store to track if we've already reloaded for this container start
            dcc.Store(id='reload-state', data={'last_start_time': 0, 'has_reloaded': False}),
            
            # Hidden div to trigger page reload via clientside callback
            html.Div(id='reload-trigger', style={'display': 'none'}),
            
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
        
        # Client-side callback to reload page when triggered
        self.app.clientside_callback(
            """
            function(reload_signal) {
                if (reload_signal === true) {
                    console.log('Container restarted, reloading page...');
                    setTimeout(function() {
                        window.location.reload();
                    }, 500);
                }
                return window.dash_clientside.no_update;
            }
            """,
            Output('reload-trigger', 'children'),
            Input('reload-trigger', 'data-reload'),
            prevent_initial_call=True
        )
        
        # Server-side callback to check for container restarts by checking start time
        @self.app.callback(
            [Output('reload-trigger', 'data-reload'),
             Output('reload-state', 'data')],
            Input('refresh-interval', 'n_intervals'),
            State('reload-state', 'data'),
            prevent_initial_call=True
        )
        def check_container_restart(n, reload_state):
            """Check if container recently restarted - trigger reload only once"""
            try:
                import time
                import os
                
                # Check if the startup marker file exists
                marker_file = '/tmp/.container_start_time'
                if os.path.exists(marker_file):
                    with open(marker_file, 'r') as f:
                        start_time = float(f.read().strip())
                    
                    # Check if this is a NEW container start (different from last known start)
                    last_start_time = reload_state.get('last_start_time', 0) if reload_state else 0
                    has_reloaded = reload_state.get('has_reloaded', False) if reload_state else False
                    
                    # If start time is different and we haven't reloaded yet for this instance
                    if start_time != last_start_time:
                        # New container detected
                        current_time = time.time()
                        uptime_seconds = current_time - start_time
                        
                        # Only trigger reload if uptime < 120 seconds (fresh restart)
                        if uptime_seconds < 120:
                            print(f"🔄 Container uptime: {uptime_seconds:.1f}s - Triggering page reload")
                            # Update state: mark this container start as seen and reloaded
                            return True, {'last_start_time': start_time, 'has_reloaded': True}
                        else:
                            # Old container, just update the state without reloading
                            return False, {'last_start_time': start_time, 'has_reloaded': False}
                    
                    # Same container, already processed
                    return False, reload_state
                
                # Normal operation - no reload needed
                return False, reload_state
            except Exception as e:
                print(f"❌ Error checking uptime: {e}")
                return False, reload_state if reload_state else {'last_start_time': 0, 'has_reloaded': False}
        
        # Callback to update the year-filter-store when a year is selected
        @self.app.callback(
            Output("sales-overview-section", "style"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def toggle_sales_overview(active_tab):
            """Show sales overview cards/charts only on the Sales tab."""
            if active_tab == "sales":
                return {}
            return {"display": "none"}

        @self.app.callback(
            Output("year-filter-store", "data"),
            Input("year-filter", "value")
        )
        def update_year_store(selected_value):
            """Update year store based on dropdown selection"""
            if selected_value == "lifetime":
                # Return all years for lifetime view
                return sorted(self.available_years, reverse=True)
            elif isinstance(selected_value, int):
                # Single year selected
                return [selected_value]
            else:
                # Default to all years
                return sorted(self.available_years, reverse=True)
        
        @self.app.callback(
            Output("metric-books-sold", "children"),
            Output("metric-net-revenue", "children"),
            Output("metric-titles", "children"),
            Output("metric-authors", "children"),
            Output("metric-returns", "children"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            prevent_initial_call=False
        )
        def update_metrics(selected_years, selected_language):
            """Update metrics based on selected years and language"""
            if not selected_years:  # If no years selected, show all
                filtered_df = self.royalties
                filtered_exploded = self.royalties_exploded
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'].isin(selected_years)]
            
            # Apply language filter
            if selected_language and selected_language != "all":
                filtered_df = filtered_df[filtered_df['Language'] == selected_language]
                filtered_exploded = filtered_exploded[filtered_exploded['Language'] == selected_language]
            
            metrics = SummaryMetrics.calculate_metrics(filtered_df, filtered_exploded)
            
            # Calculate return books (based on Units Refunded column)
            if 'Units Refunded' in filtered_df.columns:
                total_refunded = filtered_df['Units Refunded'].sum()
            else:
                total_refunded = 0
            
            return (
                f"{metrics['total_books_sold']:,}",
                f"${metrics['net_revenue_usd']:,.2f}",
                str(metrics['unique_titles']),
                str(metrics['unique_authors']),
                f"{int(total_refunded):,}"
            )
        
        @self.app.callback(
            Output("sales-trend-title", "children"),
            Output("sales-trend-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            prevent_initial_call=False
        )
        def update_sales_trend(selected_years, selected_language):
            """Update sales trend chart with dynamic title"""
            trend_data = self.royalties
            if selected_language and selected_language != "all":
                trend_data = self.royalties[self.royalties['Language'] == selected_language]
                total_books = trend_data['Net Units Sold'].sum()
                trend_title = f"📈 Sales Trend: {selected_language} ({min(self.available_years)} - {max(self.available_years)}): {int(total_books):,} books sold"
            else:
                total_books = self.royalties['Net Units Sold'].sum()
                trend_title = f"📈 Sales Trend: {min(self.available_years)} - {max(self.available_years)}: {int(total_books):,} books sold"
            
            from src.visualization.charts import SalesCharts
            fig = SalesCharts.books_sold_per_year(trend_data, title=trend_title)
            return trend_title, fig
        
        @self.app.callback(
            Output("sales-by-language-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("sales-language-display-mode", "value"),
            prevent_initial_call=False
        )
        def update_sales_by_language(selected_years, selected_language, display_mode):
            """Update sales by language stacked chart by year"""
            if not selected_years:
                filtered_df = self.royalties
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
            
            if len(filtered_df) == 0:
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_annotation(text="No sales data available", xref="paper", yref="paper",
                                   x=0.5, y=0.5, showarrow=False)
                fig.update_layout(template="plotly_dark", height=400, title="Sales by Language (All - Grouped)")
                return fig
            
            # Sort by year to ensure proper ordering
            filtered_df = filtered_df.sort_values('Year Sold')
            
            display_mode = display_mode or "all_stacked"
            focus_language = None
            barmode = 'group'
            title_suffix = "All - Grouped"

            if display_mode == "all_stacked":
                barmode = 'stack'
                title_suffix = "All - Stacked"
            elif display_mode == "all_grouped":
                barmode = 'group'
                title_suffix = "All - Grouped"
            elif isinstance(display_mode, str) and display_mode.startswith("language::"):
                focus_language = display_mode.split("::", 1)[1]
                barmode = 'group'
                title_suffix = focus_language

            if focus_language and focus_language not in filtered_df['Language'].unique():
                focus_language = None
                title_suffix = "All - Grouped"
                barmode = 'group'

            chart_title = f"Sales by Language ({title_suffix})"

            from src.visualization.charts import SalesCharts
            fig = SalesCharts.sales_by_language_stacked(
                filtered_df,
                title=chart_title,
                barmode=barmode,
                focus_language=focus_language,
                include_language_label=(focus_language is None)
            )
            return fig
        
        @self.app.callback(
            Output("returns-title", "children"),
            Output("returns-by-language-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            prevent_initial_call=False
        )
        def update_returns_by_language(selected_years, selected_language):
            """Update returns by book (nickname) chart - only show books with returns"""
            if not selected_years:
                filtered_df = self.royalties
                period_text = "Lifetime"
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
                if len(selected_years) == 1:
                    period_text = f"{selected_years[0]}"
                else:
                    period_text = f"{min(selected_years)} - {max(selected_years)}"
            
            # Get returns by book nickname and filter out books with no returns
            returns_by_book = filtered_df[filtered_df['Units Refunded'] > 0].groupby('book_nick_name')['Units Refunded'].sum().sort_values(ascending=False)
            total_refunded = returns_by_book.sum()
            
            # Create dynamic title
            returns_title = f"🌐 Returned Books ({period_text}): {int(total_refunded)} units refunded"
            
            if len(returns_by_book) == 0:
                # Return empty chart
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_annotation(text="No return data available", xref="paper", yref="paper",
                                   x=0.5, y=0.5, showarrow=False)
                fig.update_layout(template="plotly_dark", height=400, title="Returned Books")
                return returns_title, fig
            
            import plotly.express as px
            import plotly.graph_objects as go
            
            fig = px.bar(
                x=returns_by_book.values,
                y=returns_by_book.index,
                orientation="h",
                labels={"x": "Units Refunded", "y": "Book Name"},
                title="Returned Books by Title",
                color=returns_by_book.values,
                color_continuous_scale="Reds"
            )
            
            # Add book names as labels on top of bars
            fig.update_traces(
                textposition="outside",
                text=[f"{val}" for val in returns_by_book.values],
                textangle=0
            )
            
            fig.update_layout(
                template="plotly_dark",
                height=max(400, len(returns_by_book) * 25),
                showlegend=False,
                hovermode="closest",
                yaxis_autorange="reversed",
                margin=dict(l=150, r=100, t=80, b=60)
            )
            return returns_title, fig
        
        @self.app.callback(
            Output("tab-content", "children"),
            Input("dashboard-tabs", "active_tab"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            prevent_initial_call=False
        )
        def render_tab_content(active_tab, selected_years, selected_language):
            """Render content based on active tab, years, and language filter"""
            
            # Filter data based on selected years
            if not selected_years:
                filtered_royalties = self.royalties
                filtered_exploded = self.royalties_exploded
            else:
                filtered_royalties = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'].isin(selected_years)]
            
            # Filter by language if selected in sales tab
            if selected_language and selected_language != "all":
                filtered_royalties = filtered_royalties[filtered_royalties['Language'] == selected_language]
                filtered_exploded = filtered_exploded[filtered_exploded['Language'] == selected_language]
            
            if active_tab == "sales":
                return self._create_sales_tab(filtered_royalties, selected_years, selected_language)
            elif active_tab == "books":
                return self._create_books_tab(filtered_royalties)
            elif active_tab == "authors":
                return self._create_authors_tab(filtered_exploded)
            elif active_tab == "trends":
                return self._create_earning_history_tab(filtered_exploded)
            elif active_tab == "geography":
                return self._create_geography_tab(filtered_royalties)
            
            return html.Div("Select a tab to view content")
        
        @self.app.callback(
            Output('author-selector-dropdown', 'value'),
            [Input('clear-all-btn', 'n_clicks'),
             Input('add-all-btn', 'n_clicks')],
            State('author-selector-dropdown', 'options'),
            prevent_initial_call=True
        )
        def update_author_dropdown(clear_clicks, add_clicks, available_authors):
            """Update dropdown based on Clear All and Add All buttons"""
            from dash import callback_context
            
            if not callback_context.triggered:
                raise dash.exceptions.PreventUpdate
            
            button_id = callback_context.triggered[0]['prop_id'].split('.')[0]
            
            all_authors = [opt['value'] for opt in available_authors]
            
            if button_id == 'clear-all-btn':
                return []
            elif button_id == 'add-all-btn':
                return all_authors
            
            raise dash.exceptions.PreventUpdate
        
        @self.app.callback(
            Output('author-trends-graph', 'figure'),
            Input('author-selector-dropdown', 'value'),
            State('dashboard-tabs', 'active_tab'),
            prevent_initial_call=False
        )
        def update_author_earnings_history(selected_authors, active_tab):
            """Update author earnings history chart based on selected authors"""
            if active_tab != 'trends':
                return EarningHistoryCharts.earnings_trend_all_authors(self.royalties_exploded)
            
            if selected_authors and len(selected_authors) > 0:
                # If specific authors are selected, show only those
                return EarningHistoryCharts.earnings_trend_selected_authors(self.royalties_exploded, selected_authors)
            else:
                # If no authors selected, show all
                return EarningHistoryCharts.earnings_trend_all_authors(self.royalties_exploded)
        
        @self.app.callback(
            Output("download-csv", "data"),
            Input("download-csv-btn", "n_clicks"),
            State('author-selector-dropdown', 'value'),
            prevent_initial_call=True,
        )
        def download_csv(n_clicks, selected_authors):
            """Generate and download author earnings as CSV"""
            df_copy = self.royalties_exploded.copy()
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate earnings per year per author
            yearly_earnings = df_copy.groupby(['Year Sold', 'Authors_Normalized'])['Royalty per Author (USD)'].sum().reset_index()
            yearly_earnings['Earnings USD'] = (yearly_earnings['Royalty per Author (USD)'] * NET_REVENUE_PERCENTAGE).round(2)
            
            # Filter by selected authors if provided
            if selected_authors and len(selected_authors) > 0:
                yearly_earnings = yearly_earnings[yearly_earnings['Authors_Normalized'].isin(selected_authors)]
            
            # Pivot table: Authors as rows, Years as columns
            pivot_data = yearly_earnings.pivot_table(
                index='Authors_Normalized',
                columns='Year Sold',
                values='Earnings USD',
                fill_value=0
            )
            
            # Round all values to 2 decimals
            pivot_data = pivot_data.round(2)
            
            # Add total row
            pivot_data.loc['TOTAL'] = pivot_data.sum().round(2)
            
            # Rename index
            pivot_data.index.name = 'Author'
            
            # Create CSV with UTF-8-sig BOM
            csv_content = pivot_data.reset_index().to_csv(index=False)
            csv_with_bom = '\ufeff' + csv_content  # Add BOM character
            return dict(content=csv_with_bom, filename="author_earnings.csv")
        
        @self.app.callback(
            Output("download-txt", "data"),
            Input("download-txt-btn", "n_clicks"),
            State('author-selector-dropdown', 'value'),
            prevent_initial_call=True,
        )
        def download_txt(n_clicks, selected_authors):
            """Generate and download author earnings as TXT"""
            df_copy = self.royalties_exploded.copy()
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate earnings per year per author
            yearly_earnings = df_copy.groupby(['Year Sold', 'Authors_Normalized'])['Royalty per Author (USD)'].sum().reset_index()
            yearly_earnings['Earnings USD'] = (yearly_earnings['Royalty per Author (USD)'] * NET_REVENUE_PERCENTAGE).round(2)
            
            # Filter by selected authors if provided
            if selected_authors and len(selected_authors) > 0:
                yearly_earnings = yearly_earnings[yearly_earnings['Authors_Normalized'].isin(selected_authors)]
            
            # Pivot table: Authors as rows, Years as columns
            pivot_data = yearly_earnings.pivot_table(
                index='Authors_Normalized',
                columns='Year Sold',
                values='Earnings USD',
                fill_value=0
            )
            
            # Round all values to 2 decimals
            pivot_data = pivot_data.round(2)
            
            # Create formatted text output
            txt_content = "RESULAM ROYALTIES - AUTHOR EARNINGS REPORT\n"
            txt_content += "=" * 80 + "\n\n"
            txt_content += "Author Earnings by Year (USD)\n"
            txt_content += "-" * 80 + "\n\n"
            
            # Format as fixed-width columns
            txt_content += f"{'Author':<50}"
            for year in sorted(pivot_data.columns):
                txt_content += f"{year:>12}"
            txt_content += f"{'TOTAL':>12}\n"
            txt_content += "-" * 80 + "\n"
            
            for author in pivot_data.index:
                txt_content += f"{author:<50}"
                row_total = 0
                for year in sorted(pivot_data.columns):
                    value = pivot_data.loc[author, year] if year in pivot_data.columns else 0
                    txt_content += f"${value:>11,.2f}"
                    row_total += value
                txt_content += f"${round(row_total, 2):>11,.2f}\n"
            
            txt_content += "-" * 80 + "\n"
            txt_content += f"{'TOTAL':<50}"
            grand_total = 0
            for year in sorted(pivot_data.columns):
                col_total = pivot_data[year].sum() if year in pivot_data.columns else 0
                txt_content += f"${col_total:>11,.2f}"
                grand_total += col_total
            txt_content += f"${round(grand_total, 2):>11,.2f}\n"
            txt_content += "=" * 80 + "\n"
            
            # Add UTF-8 BOM character
            txt_with_bom = '\ufeff' + txt_content
            return dict(content=txt_with_bom, filename="author_earnings.txt")
        
        @self.app.callback(
            Output("download-authors-alpha-csv", "data"),
            Input("download-authors-alpha-csv", "n_clicks"),
            prevent_initial_call=True,
        )
        def download_authors_alpha_csv(n_clicks):
            """Download authors list alphabetically as CSV"""
            df_copy = self.royalties_exploded.copy()
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Get unique authors sorted alphabetically
            authors = sorted(df_copy['Authors_Normalized'].unique())
            
            # Create DataFrame
            df_output = pd.DataFrame({
                'Author Name': authors
            })
            
            # Create CSV with UTF-8-sig BOM
            csv_content = df_output.to_csv(index=False)
            csv_with_bom = '\ufeff' + csv_content  # Add BOM character
            return dict(content=csv_with_bom, filename="author_names_alphabetical.csv")
        
        @self.app.callback(
            Output("download-authors-alpha-txt", "data"),
            Input("download-authors-alpha-txt", "n_clicks"),
            prevent_initial_call=True,
        )
        def download_authors_alpha_txt(n_clicks):
            """Download authors list alphabetically as TXT"""
            df_copy = self.royalties_exploded.copy()
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Get unique authors sorted alphabetically
            authors = sorted(df_copy['Authors_Normalized'].unique())
            
            # Create formatted text
            txt_content = "RESULAM ROYALTIES - AUTHOR NAMES (ALPHABETICAL)\n"
            txt_content += "=" * 60 + "\n\n"
            
            for i, author in enumerate(authors, 1):
                txt_content += f"{i:2d}. {author}\n"
            
            txt_content += "\n" + "=" * 60 + "\n"
            txt_content += f"Total Authors: {len(authors)}\n"
            
            # Add UTF-8 BOM character
            txt_with_bom = '\ufeff' + txt_content
            return dict(content=txt_with_bom, filename="author_names_alphabetical.txt")
        
        @self.app.callback(
            Output("download-authors-earnings-csv", "data"),
            Input("download-authors-earnings-csv", "n_clicks"),
            State('year-filter-store', 'data'),
            State('language-filter', 'value'),
            prevent_initial_call=True,
        )
        def download_authors_earnings_csv(n_clicks, selected_years, selected_language):
            """Download authors list by earnings as CSV (USD only)"""
            # Filter data based on selected years and language
            df_copy = self.royalties_exploded.copy()
            
            if selected_years and len(selected_years) > 0:
                df_copy = df_copy[df_copy['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                df_copy = df_copy[df_copy['Language'] == selected_language]
            
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate total earnings per author
            author_earnings_usd = (df_copy.groupby('Authors_Normalized')['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE).round(2)
            author_earnings_usd = author_earnings_usd.sort_values(ascending=True)
            
            # Create DataFrame - USD only
            df_output = pd.DataFrame({
                'Author Name': author_earnings_usd.index,
                'Total Earnings USD': author_earnings_usd.values
            })
            
            # Create CSV with UTF-8-sig BOM
            csv_content = df_output.to_csv(index=False)
            csv_with_bom = '\ufeff' + csv_content  # Add BOM character
            return dict(content=csv_with_bom, filename="author_names_by_earnings.csv")
        
        @self.app.callback(
            Output("download-authors-earnings-txt", "data"),
            Input("download-authors-earnings-txt", "n_clicks"),
            State('year-filter-store', 'data'),
            State('language-filter', 'value'),
            prevent_initial_call=True,
        )
        def download_authors_earnings_txt(n_clicks, selected_years, selected_language):
            """Download authors list by earnings as TXT (USD only)"""
            # Filter data based on selected years and language
            df_copy = self.royalties_exploded.copy()
            
            if selected_years and len(selected_years) > 0:
                df_copy = df_copy[df_copy['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                df_copy = df_copy[df_copy['Language'] == selected_language]
            
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate total earnings per author
            author_earnings = (df_copy.groupby('Authors_Normalized')['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE).round(2)
            author_earnings = author_earnings.sort_values(ascending=True)
            
            # Create formatted text
            txt_content = "RESULAM ROYALTIES - AUTHOR NAMES (BY EARNINGS)\n"
            txt_content += "=" * 70 + "\n\n"
            txt_content += f"{'#':<4}{'Author Name':<50}{'Earnings':>15}\n"
            txt_content += "-" * 70 + "\n"
            
            total_earnings = 0
            for i, (author, earnings) in enumerate(author_earnings.items(), 1):
                txt_content += f"{i:<4}{author:<50}${earnings:>14,.2f}\n"
                total_earnings += earnings
            
            txt_content += "-" * 70 + "\n"
            txt_content += f"{'TOTAL':<54}${round(total_earnings, 2):>14,.2f}\n"
            txt_content += "=" * 70 + "\n"
            
            # Add UTF-8 BOM character
            txt_with_bom = '\ufeff' + txt_content
            return dict(content=txt_with_bom, filename="author_names_by_earnings.txt")
        
        @self.app.callback(
            Output("download-authors-adjustment-csv", "data"),
            Input("download-authors-adjustment-csv", "n_clicks"),
            State('year-filter-store', 'data'),
            State('language-filter', 'value'),
            prevent_initial_call=True,
        )
        def download_authors_adjustment_csv(n_clicks, selected_years, selected_language):
            """Download authors list with adjustment (min $5, rounded FCFA) as CSV"""
            import math
            
            # Filter data based on selected years and language
            df_copy = self.royalties_exploded.copy()
            
            if selected_years and len(selected_years) > 0:
                df_copy = df_copy[df_copy['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                df_copy = df_copy[df_copy['Language'] == selected_language]
            
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate total earnings per author
            author_earnings = (df_copy.groupby('Authors_Normalized')['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE).round(2)
            author_earnings = author_earnings.sort_values(ascending=True)
            
            # Apply adjustment: min $5, convert to FCFA, round to nearest 5
            author_earnings_adjusted = author_earnings.apply(lambda x: max(5.0, x)).round(2)
            author_earnings_fcfa_adjusted = author_earnings_adjusted.apply(
                lambda x: int(math.ceil(x * 655 / 5) * 5)
            )
            
            # Create DataFrame
            df_output = pd.DataFrame({
                'Author Name': author_earnings.index,
                'Original Earnings USD': author_earnings.values,
                'Adjusted Earnings USD': author_earnings_adjusted.values,
                'Adjusted Earnings FCFA': author_earnings_fcfa_adjusted.values
            })
            
            csv_content = df_output.to_csv(index=False)
            csv_with_bom = '\ufeff' + csv_content
            return dict(content=csv_with_bom, filename="author_earnings_adjusted.csv")
        
        @self.app.callback(
            Output("download-authors-adjustment-txt", "data"),
            Input("download-authors-adjustment-txt", "n_clicks"),
            State('year-filter-store', 'data'),
            State('language-filter', 'value'),
            prevent_initial_call=True,
        )
        def download_authors_adjustment_txt(n_clicks, selected_years, selected_language):
            """Download authors list with adjustment as TXT"""
            import math
            
            # Filter data based on selected years and language
            df_copy = self.royalties_exploded.copy()
            
            if selected_years and len(selected_years) > 0:
                df_copy = df_copy[df_copy['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                df_copy = df_copy[df_copy['Language'] == selected_language]
            
            df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
                lambda x: normalize_author_name(x)
            )
            
            # Exclude Resulam
            df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
            
            # Calculate total earnings per author
            author_earnings = (df_copy.groupby('Authors_Normalized')['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE).round(2)
            author_earnings = author_earnings.sort_values(ascending=True)
            
            # Apply adjustment
            author_earnings_adjusted = author_earnings.apply(lambda x: max(5.0, x)).round(2)
            author_earnings_fcfa_adjusted = author_earnings_adjusted.apply(
                lambda x: int(math.ceil(x * 655 / 5) * 5)
            )
            
            # Create formatted text
            txt_content = "RESULAM ROYALTIES - AUTHOR EARNINGS ADJUSTED\n"
            txt_content += "(Minimum $5 USD, FCFA rounded to nearest 5)\n"
            txt_content += "=" * 120 + "\n\n"
            txt_content += f"{'#':<4}{'Author Name':<40}{'Original USD':>18}{'Adjusted USD':>18}{'Adjusted FCFA':>18}\n"
            txt_content += "-" * 120 + "\n"
            
            total_original = 0
            total_adjusted = 0
            total_fcfa = 0
            
            for i, (author, earning) in enumerate(author_earnings.items(), 1):
                adjusted_usd = max(5.0, earning)
                adjusted_fcfa = int(math.ceil(adjusted_usd * 655 / 5) * 5)
                txt_content += f"{i:<4}{author:<40}${earning:>17,.2f}${adjusted_usd:>17,.2f}{adjusted_fcfa:>18,}\n"
                total_original += earning
                total_adjusted += adjusted_usd
                total_fcfa += adjusted_fcfa
            
            txt_content += "-" * 120 + "\n"
            txt_content += f"{'TOTAL':<44}${round(total_original, 2):>17,.2f}${round(total_adjusted, 2):>17,.2f}{total_fcfa:>18,}\n"
            txt_content += "=" * 120 + "\n"
            
            # Add UTF-8 BOM
            txt_with_bom = '\ufeff' + txt_content
            return dict(content=txt_with_bom, filename="author_earnings_adjusted.txt")
    
    def _create_sales_tab(self, data=None, selected_years=None, selected_language=None):
        """Create sales overview tab content"""
        if data is None:
            data = self.royalties
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.P("Summary cards and sales charts are available when the Sales Overview tab is selected.", className="text-muted")
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
        
        # Get the non-exploded data for metrics - match the filtered data's years and languages
        if data.shape[0] > 0:
            # Get unique years and languages from filtered data
            years_in_data = data['Year Sold'].unique().tolist()
            languages_in_data = data['Language'].unique().tolist()
            
            # Filter metrics data to match the exploded data's scope
            metrics_data = self.royalties[
                (self.royalties['Year Sold'].isin(years_in_data)) &
                (self.royalties['Language'].isin(languages_in_data))
            ]
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
                                        html.Td("Total Author Shares"),
                                        # Sum of Royalty per Author USD (authors only, excluding Resulam)
                                        html.Td(f"${(data[data['Authors_Exploded'] != 'Resulam']['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE):,.2f}")
                                    ]),
                                    html.Tr([
                                        html.Td("Resulam Share"),
                                        # Resulam Share = Net Revenue - Total Author Shares
                                        html.Td(f"${(metrics_data['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE - data[data['Authors_Exploded'] != 'Resulam']['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE):,.2f}")
                                    ]),
                                    html.Tr([
                                        html.Td("Total Revenue"),
                                        # Total Revenue = Author Shares + Resulam Share
                                        html.Td(f"${(metrics_data['Royalty USD'].sum() * NET_REVENUE_PERCENTAGE):,.2f}")
                                    ])
                                ])
                            ], bordered=True, hover=True, responsive=True, striped=True)
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            dbc.Row([
                # Calculate author shares for display
                (lambda author_data, year_str: (
                    dbc.Row([
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(
                                    dbc.Row([
                                        dbc.Col([html.H4(f"{year_str} 👥 Author Names (By Earnings)")], md=9),
                                        dbc.Col([
                                            dbc.Button("📥 CSV", id="download-authors-earnings-csv", color="info", size="sm", className="me-2"),
                                            dbc.Button("📥 TXT", id="download-authors-earnings-txt", color="info", size="sm")
                                        ], md=3, className="text-end")
                                    ])
                                ),
                                dbc.CardBody([
                                    html.Ol([
                                        html.Li(f"{author}: ${share:,.2f}", className="mb-2 author-list-item")
                                        for author, share in sorted(author_data.items(), key=lambda x: x[1], reverse=False)
                                    ]),
                                    html.Hr(),
                                    html.H5(f"Total: ${sum(author_data.values()):,.2f}", className="author-list-total font-weight-bold")
                                ])
                            ], className="shadow-sm mb-4")
                        ], md=6),
                        dbc.Col([
                            dbc.Card([
                                dbc.CardHeader(
                                    dbc.Row([
                                        dbc.Col([html.H4(f"{year_str} 💰 Author Earnings Adjusted")], md=9),
                                        dbc.Col([
                                            dbc.Button("📥 CSV", id="download-authors-adjustment-csv", color="warning", size="sm", className="me-2"),
                                            dbc.Button("📥 TXT", id="download-authors-adjustment-txt", color="warning", size="sm")
                                        ], md=3, className="text-end")
                                    ])
                                ),
                                dbc.CardBody([
                                    html.Ol([
                                        html.Li(
                                            f"{author}: ${share:,.2f} → ${max(5, share):,.2f} / {int((max(5, share) * 655 + 2) // 5 * 5):,} FCFA",
                                            className="mb-2 author-list-item"
                                        )
                                        for author, share in sorted(author_data.items(), key=lambda x: x[1], reverse=False)
                                    ]),
                                    html.Hr(),
                                    html.H5(
                                        f"Total: ${sum(max(5, share) for share in author_data.values()):,.2f} / {int(sum((max(5, share) * 655 + 2) // 5 * 5 for share in author_data.values())):,} FCFA",
                                        className="author-list-total font-weight-bold"
                                    )
                                ])
                            ], className="shadow-sm mb-4")
                        ], md=6)
                    ])
                ))({author: data[data['Authors_Exploded'].apply(lambda x: normalize_author_name(x)) == author]['Royalty per Author (USD)'].sum() * NET_REVENUE_PERCENTAGE 
                    for author in get_unique_authors(data['Authors_Exploded']) if author.lower() != "resulam"},
                   ", ".join(map(str, sorted(years_in_data, reverse=True)))),
                dcc.Download(id="download-authors-earnings-csv"),
                dcc.Download(id="download-authors-earnings-txt"),
                dcc.Download(id="download-authors-adjustment-csv"),
                dcc.Download(id="download-authors-adjustment-txt")
            ])
        ], fluid=True)
    
    def _create_earning_history_tab(self, data=None):
        """Create earning history tab with bar chart and vertical checkbox dropdown"""
        if data is None:
            data = self.royalties_exploded
        
        # Get list of all authors
        all_authors = sorted(EarningHistoryCharts.get_all_authors(data))
        
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📊 Author Earnings by Year")),
                        dbc.CardBody([
                            dbc.Row([
                                dbc.Col([
                                    html.P("Select authors to display:", className="fw-bold mb-2"),
                                    # Vertical dropdown menu with checkboxes
                                    html.Div([
                                        dcc.Dropdown(
                                            id='author-selector-dropdown',
                                            options=[{'label': author, 'value': author} for author in all_authors],
                                            value=all_authors,  # Default: all authors selected
                                            multi=True,
                                            placeholder='Click to select authors...',
                                            searchable=True,
                                            clearable=False,
                                            style={'width': '100%'}
                                        )
                                    ], style={
                                        'width': '100%',
                                        'minHeight': '50px',
                                        'marginBottom': '10px'
                                    }),
                                    dbc.Row([
                                        dbc.Col([
                                            dbc.Button("Clear All", id="clear-all-btn", color="danger", size="sm", className="me-2"),
                                            dbc.Button("Add All", id="add-all-btn", color="success", size="sm", className="me-2"),
                                            dbc.Button("📥 Download CSV", id="download-csv-btn", color="info", size="sm", className="me-2"),
                                            dbc.Button("📥 Download TXT", id="download-txt-btn", color="info", size="sm"),
                                        ], md=12)
                                    ], className="mt-2"),
                                    dcc.Download(id="download-csv"),
                                    dcc.Download(id="download-txt")
                                ], md=12)
                            ]),
                            html.Hr(),
                            dcc.Graph(
                                id='author-trends-graph',
                                config={'displayModeBar': False}
                            )
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
        
        # Theme toggle with proper theme switching
        @self.app.callback(
            Output("theme-store", "data"),
            Output("theme-icon", "className"),
            Output("header-container", "className"),
            Input("theme-toggle-btn", "n_clicks"),
            State("theme-store", "data"),
            prevent_initial_call=True
        )
        def toggle_theme(n_clicks, current_theme):
            """Toggle between light and dark mode"""
            new_theme = "light" if current_theme == "dark" else "dark"
            icon_class = "fas fa-moon" if new_theme == "dark" else "fas fa-sun"
            header_class = "bg-light py-4 mb-4" if new_theme == "light" else "bg-dark py-4 mb-4"
            return new_theme, icon_class, header_class
        
        # Apply theme to body element using clientside callback
        self.app.clientside_callback(
            """
            function(theme) {
                if (theme === 'light') {
                    document.body.classList.add('light-mode');
                } else {
                    document.body.classList.remove('light-mode');
                }
                return theme;
            }
            """,
            Output("theme-store", "data", allow_duplicate=True),
            Input("theme-store", "data"),
            prevent_initial_call=True
        )
        
        # Returns modal toggle
        @self.app.callback(
            Output("returns-modal", "is_open"),
            Input("returns-details-btn", "n_clicks"),
            Input("returns-close-btn", "n_clicks"),
            State("returns-modal", "is_open"),
            prevent_initial_call=True
        )
        def toggle_returns_modal(open_clicks, close_clicks, is_open):
            """Toggle returns details modal"""
            return not is_open
        
        # Populate returns table
        @self.app.callback(
            Output("returns-table-content", "children"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            prevent_initial_call=False
        )
        def update_returns_table(selected_years, selected_language):
            """Show books with refunds"""
            if not selected_years:
                filtered_df = self.royalties
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                filtered_df = filtered_df[filtered_df['Language'] == selected_language]
            
            # Get books with refunds
            returns_df = filtered_df[filtered_df['Units Refunded'] > 0][['Title', 'Units Sold', 'Units Refunded', 'Marketplace', 'Royalty Date']].copy()
            returns_df = returns_df.sort_values('Units Refunded', ascending=False)
            
            if len(returns_df) == 0:
                return html.Div([
                    html.P("No returned books in the selected period.", className="text-muted")
                ])
            
            return html.Div([
                html.P(f"Total returned books: {int(returns_df['Units Refunded'].sum())}", className="fw-bold mb-3"),
                dbc.Table.from_dataframe(
                    returns_df.head(50),
                    striped=True,
                    bordered=True,
                    hover=True,
                    responsive=True,
                    size="sm"
                )
            ])
    
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
