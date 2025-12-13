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
import unicodedata
import plotly.graph_objects as go

from ..config import DASHBOARD_CONFIG, CURRENT_YEAR, LAST_YEAR, AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE, BOOKS_DATABASE_PATH
from ..visualization import SalesCharts, AuthorCharts, GeographicCharts, SummaryMetrics
from ..visualization.earning_history import EarningHistoryCharts


def sort_with_accents(items: list) -> list:
    """Sort items with accent-aware collation (Éwé sorts near Ewondo, not at the end)"""
    def sort_key(s):
        # Normalize accented characters to their base form for sorting
        normalized = unicodedata.normalize('NFD', s)
        # Remove combining characters (accents) for the sort key
        return ''.join(c for c in normalized if not unicodedata.combining(c))
    return sorted(items, key=sort_key)


def format_years_compact(years: list) -> str:
    """Format a list of years into a compact string representation.
    
    Examples:
        [2025, 2024, 2023, 2022, 2021, 2020, 2019, 2018, 2017, 2016] -> "2016-2025"
        [2024, 2023] -> "2023, 2024"
        [2024] -> "2024"
        [2025, 2023, 2021] -> "2021, 2023, 2025"
    """
    if not years:
        return "No Data"
    
    sorted_years = sorted(years)
    
    if len(sorted_years) == 1:
        return str(sorted_years[0])
    
    if len(sorted_years) == 2:
        return f"{sorted_years[0]}, {sorted_years[1]}"
    
    # Check if years are consecutive
    is_consecutive = all(
        sorted_years[i] + 1 == sorted_years[i + 1] 
        for i in range(len(sorted_years) - 1)
    )
    
    if is_consecutive:
        return f"{sorted_years[0]}-{sorted_years[-1]}"
    else:
        # Not consecutive - show range with gaps indicator or just min-max
        if len(sorted_years) <= 3:
            return ", ".join(map(str, sorted_years))
        else:
            return f"{sorted_years[0]}-{sorted_years[-1]}"


def normalize_author_name(name: str) -> str:
    """Normalize author name using the AUTHOR_NORMALIZATION mapping"""
    if name in AUTHOR_NORMALIZATION:
        return AUTHOR_NORMALIZATION[name]
    return name


def filter_by_author(df: pd.DataFrame, selected_author: str, authors_column: str = 'Authors') -> pd.DataFrame:
    """Filter dataframe by author, handling normalization properly.
    
    This function checks if any author in the Authors column (which may contain
    multiple authors separated by commas) normalizes to the selected author.
    """
    if not selected_author or selected_author == "all":
        return df
    
    def row_has_author(authors_str):
        if pd.isna(authors_str):
            return False
        # Split by common separators and check each author
        for sep in [',', ';', '&', ' and ']:
            if sep in str(authors_str):
                for author in str(authors_str).split(sep):
                    if normalize_author_name(author.strip()) == selected_author:
                        return True
        # Also check the whole string
        return normalize_author_name(str(authors_str).strip()) == selected_author
    
    return df[df[authors_column].apply(row_has_author)]


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


class PublicDashboard:
    """Public dashboard application class - customized for external audiences"""
    
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
        
        # Set secret key for session persistence across restarts
        import os
        self.app.server.secret_key = os.getenv('FLASK_SECRET_KEY', 'resulam-royalties-secret-key-2025')
        
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
                <meta property="og:title" content="African Languages Books - Resulam" />
                <meta name="twitter:title" content="African Languages Books - Resulam" />
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
        
        # Set page title for public site (fallback, multi-page router overrides per path)
        self.app.title = "African Languages Books - Resulam"
        
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
                        "African Languages Libraries - By Resulam",
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
        
        # Get unique languages for language filter (exclude African Names and Bamileke)
        all_languages = sort_with_accents([
            lang for lang in self.royalties['Language'].unique().tolist()
            if lang not in ['African Names', 'Bamileke']
        ])
        
        # Get unique authors for author filter
        all_authors_for_filter = get_unique_authors(self.royalties_exploded['Authors_Exploded'])
        
        # Get unique book types for book type filter
        all_book_types = sorted(self.royalties['BookType'].dropna().unique().tolist())
        
        # Get unique book nicknames for book filter
        all_book_nicknames = sorted(self.royalties['book_nick_name'].dropna().unique().tolist())
        
        # Get unique categories from books database for category filter
        try:
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
            all_categories = sorted(books_df['category'].dropna().unique().tolist())
        except Exception:
            all_categories = []
        
        filter_section = dbc.Container([
            # First row: Year, Language, Author
            dbc.Row([
                dbc.Col([
                    dbc.Label("Year:", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="year-filter",
                        options=[{"label": "Lifetime", "value": "lifetime"}] + 
                                [{"label": str(year), "value": year} for year in years_reversed],
                        value="lifetime",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    ),
                    dcc.Store(id="year-filter-store", data=[])
                ], md=2, sm=4, xs=6),
                dbc.Col([
                    dbc.Label(id="language-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="language-filter",
                        options=[{"label": f"All Languages ({len(all_languages)})", "value": "all"}] + [
                            {"label": lang, "value": lang} for lang in all_languages
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    )
                ], md=2, sm=4, xs=6),
                dbc.Col([
                    dbc.Label(id="author-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="author-filter",
                        options=[{"label": f"All Authors ({len(all_authors_for_filter)})", "value": "all"}] + [
                            {"label": author, "value": author} for author in all_authors_for_filter
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    )
                ], md=2, sm=4, xs=6),
                dbc.Col([
                    dbc.Label(id="booktype-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="booktype-filter",
                        options=[{"label": f"All Types ({len(all_book_types)})", "value": "all"}] + [
                            {"label": "📱 eBook" if bt == "Ebook" else "📖 Paperback" if bt == "Paper" else "📚 Hardcover" if bt == "HardCover" else bt, "value": bt} for bt in all_book_types
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"}
                    )
                ], md=2, sm=4, xs=6),
                dbc.Col([
                    dbc.Label(id="book-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="book-filter",
                        options=[{"label": f"All Books ({len(all_book_nicknames)})", "value": "all"}] + [
                            {"label": nickname, "value": nickname} for nickname in all_book_nicknames
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"},
                        placeholder="Search..."
                    )
                ], md=2, sm=4, xs=6),
                dbc.Col([
                    dbc.Label(id="category-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="category-filter",
                        options=[{"label": f"All Categories ({len(all_categories)})", "value": "all"}] + [
                            {"label": cat, "value": cat} for cat in all_categories
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"},
                        placeholder="Select..."
                    )
                ], md=2, sm=4, xs=6),
            ], className="g-2 align-items-end mb-2"),
            # Second row: Reset button centered
            dbc.Row([
                dbc.Col([
                    dbc.Button(
                        "🔄 Reset All Filters",
                        id="reset-all-filters",
                        color="danger",
                        className="w-100",
                        style={"fontWeight": "bold", "fontSize": "0.85rem"}
                    )
                ], md={"size": 2, "offset": 5}, sm={"size": 4, "offset": 4}, xs={"size": 6, "offset": 3})
            ], className="g-2")
        ], fluid=True, className="py-2 mb-3")
        
        # Summary metrics cards (now dynamic based on filter)
        # Common card style for consistent sizing
        metric_card_style = {
            "minHeight": "130px",
            "height": "100%"
        }
        metric_card_body_style = {
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center",
            "alignItems": "center",
            "padding": "0.75rem 0.25rem"
        }
        metric_title_style = {"color": "#ffffff", "fontWeight": "600", "fontSize": "0.85rem", "marginBottom": "0.25rem", "whiteSpace": "nowrap"}
        metric_value_style_base = {"fontWeight": "700", "fontSize": "2.5rem", "marginBottom": "0", "whiteSpace": "nowrap"}
        
        metrics_row = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("📖", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Total Books Sold", className="text-center", style=metric_title_style),
                        html.Div(id="metric-books-sold", className="text-center", style={**metric_value_style_base, "color": "#00DDFF"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm", style=metric_card_style)
            ], width=True, className="mb-2 px-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("📚", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Unique Titles", className="text-center", style=metric_title_style),
                        html.Div(id="metric-titles", className="text-center", style={**metric_value_style_base, "color": "#888888"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm", style=metric_card_style)
            ], width=True, className="mb-2 px-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("🧑🏿‍💼", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Authors", className="text-center", style=metric_title_style),
                        html.Div(id="metric-authors", className="text-center", style={**metric_value_style_base, "color": "#FFDD00"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm", style=metric_card_style)
            ], width=True, className="mb-2 px-1")
        ], className="mb-3 g-2 flex-nowrap", style={"overflowX": "auto"})
        
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

        # Group sales overview elements so they can be toggled per tab
        sales_overview_section = html.Div([
            metrics_row,
            sales_trend_section,
            sales_by_language_section
        ], id="sales-overview-section")
        
        # Tabs for different views - PUBLIC VERSION (removed Authors Analysis and Earning History)
        tabs = dbc.Tabs([
            dbc.Tab(label="🛒 Purchase the Book", tab_id="purchase"),
            dbc.Tab(label="📊 Sales Overview", tab_id="sales"),
            dbc.Tab(label="📖 Books Analysis", tab_id="books"),
            dbc.Tab(label="🌍 Geographic Distribution", tab_id="geography"),
        ], id="dashboard-tabs", active_tab="purchase", className="mb-4")
        
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
            dcc.Store(id='reload-state', storage_type='local', data={'last_start_time': 0, 'has_reloaded': False}),
            
            # Store to signal data refresh without full reload
            dcc.Store(id='data-refresh-signal', storage_type='memory'),
            
            # Toast notification for data updates
            dbc.Toast(
                "New data available! Dashboard updated.",
                id="data-update-toast",
                header="Data Synced",
                is_open=False,
                dismissable=True,
                duration=5000,
                icon="success",
                style={"position": "fixed", "top": 66, "right": 10, "width": 350, "zIndex": 9999},
            ),
            # Hidden placeholders to satisfy callbacks registered on the shared app
            html.Div(id="metric-net-revenue", style={"display": "none"}),
            html.Div(id="metric-returns", style={"display": "none"}),
            
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
        
        # Server-side callback to check for container restarts by checking start time
        @self.app.callback(
            [Output('data-refresh-signal', 'data'),
             Output('reload-state', 'data')],
            Input('refresh-interval', 'n_intervals'),
            State('reload-state', 'data'),
            prevent_initial_call=True
        )
        def check_container_restart(n, reload_state):
            """Check if container recently restarted - trigger data refresh only once"""
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
                    
                    # Only process if this is a different container instance
                    if start_time != last_start_time:
                        # New container detected
                        current_time = time.time()
                        uptime_seconds = current_time - start_time
                        
                        # Only trigger refresh if uptime < 600 seconds (10 minutes)
                        if uptime_seconds < 600:
                            print(f"🔄 New container detected - uptime: {uptime_seconds:.1f}s - Triggering data refresh")
                            # Trigger data refresh and update state
                            return {'timestamp': current_time}, {'last_start_time': start_time, 'has_reloaded': True}
                        else:
                            # Too old - just update state without refreshing
                            return dash.no_update, {'last_start_time': start_time, 'has_reloaded': False}
                    
                    # Same container instance - no action needed
                    return dash.no_update, reload_state
                
                # Normal operation - no action needed
                return dash.no_update, reload_state
            except Exception as e:
                print(f"❌ Error checking uptime: {e}")
                return dash.no_update, reload_state if reload_state else {'last_start_time': 0, 'has_reloaded': False}
        
        # Callback to show toast when data is refreshed
        @self.app.callback(
            Output("data-update-toast", "is_open"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=True
        )
        def show_update_toast(signal_data):
            """Show toast notification when data is refreshed"""
            if signal_data:
                return True
            return False

        # Callback to update filter options when data is refreshed
        # Helper function to filter data based on current selections
        def _get_filtered_data(selected_years=None, selected_language=None, selected_author=None, 
                               selected_booktype=None, selected_book=None, selected_category=None):
            """Get filtered data based on current filter selections"""
            df = self.royalties.copy()
            df_exploded = self.royalties_exploded.copy()
            
            if selected_years and selected_years != "lifetime":
                if isinstance(selected_years, list):
                    df = df[df['Year Sold'].isin(selected_years)]
                    df_exploded = df_exploded[df_exploded['Year Sold'].isin(selected_years)]
            
            # Apply category filter first (if applicable)
            if selected_category and selected_category != "all":
                books_df = pd.read_csv(BOOKS_DATABASE_PATH)
                category_books = books_df[books_df['category'] == selected_category]
                
                from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY
                category_nicknames = set()
                
                # Get all database nicknames for this category
                db_nicknames = category_books['book_nick_name'].dropna().tolist()
                
                for db_nick in db_nicknames:
                    # First, check if this DB nickname maps to royalty nicknames
                    if db_nick in DB_NICKNAME_TO_ROYALTY:
                        category_nicknames.update(DB_NICKNAME_TO_ROYALTY[db_nick])
                    else:
                        # Add the DB nickname itself (might match directly)
                        category_nicknames.add(db_nick)
                
                if category_nicknames:
                    df = df[df['book_nick_name'].isin(category_nicknames)]
                    df_exploded = df_exploded[df_exploded['book_nick_name'].isin(category_nicknames)]
            
            if selected_language and selected_language != "all":
                df = df[df['Language'] == selected_language]
                df_exploded = df_exploded[df_exploded['Language'] == selected_language]
            
            if selected_author and selected_author != "all":
                df = filter_by_author(df, selected_author, 'Authors')
                df_exploded = df_exploded[df_exploded['Authors_Exploded'].apply(lambda x: normalize_author_name(x)) == selected_author]
            
            if selected_booktype and selected_booktype != "all":
                df = df[df['BookType'] == selected_booktype]
                df_exploded = df_exploded[df_exploded['BookType'] == selected_booktype]
            
            if selected_book and selected_book != "all":
                df = df[df['book_nick_name'] == selected_book]
                df_exploded = df_exploded[df_exploded['book_nick_name'] == selected_book]
            
            return df, df_exploded

        @self.app.callback(
            Output("language-filter", "options"),
            Input("year-filter", "value"),
            Input("category-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_language_options(selected_year, selected_category, selected_author, selected_booktype, selected_book, refresh_signal):
            """Update language filter options based on other filters"""
            # Convert year selection to list for filtering
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year
            
            df, _ = _get_filtered_data(years, None, selected_author, selected_booktype, selected_book, selected_category)
            available_languages = sort_with_accents([
                lang for lang in df['Language'].dropna().unique().tolist()
                if lang not in ['African Names', 'Bamileke']
            ])
            
            return [{"label": f"All Languages ({len(available_languages)})", "value": "all"}] + [
                {"label": lang, "value": lang} for lang in available_languages
            ]

        @self.app.callback(
            Output("language-label", "children"),
            Input("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_language_label(selected_year):
            """Update language label based on selected year"""
            if selected_year == "lifetime" or not selected_year:
                return "Languages (Lifetime):"
            else:
                return f"Languages (With a sell in {selected_year}):"

        @self.app.callback(
            Output("author-label", "children"),
            Input("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_author_label(selected_year):
            """Update author label based on selected year"""
            if selected_year == "lifetime" or not selected_year:
                return "Authors (Lifetime):"
            else:
                return f"Authors (With a sell in {selected_year}):"

        @self.app.callback(
            Output("booktype-label", "children"),
            Input("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_booktype_label(selected_year):
            """Update book type label based on selected year"""
            if selected_year == "lifetime" or not selected_year:
                return "Type (Lifetime):"
            else:
                return f"Type (With a sell in {selected_year}):"

        @self.app.callback(
            Output("category-label", "children"),
            Input("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_category_label(selected_year):
            """Update category label based on selected year"""
            if selected_year == "lifetime" or not selected_year:
                return "Category (Lifetime):"
            else:
                return f"Category (With a sell in {selected_year}):"

        @self.app.callback(
            Output("book-label", "children"),
            Input("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_book_label(selected_year):
            """Update book label based on selected year"""
            if selected_year == "lifetime" or not selected_year:
                return "Books (Lifetime):"
            else:
                return f"Books (With a sell in {selected_year}):"

        @self.app.callback(
            Output("author-filter", "options"),
            Input("year-filter", "value"),
            Input("category-filter", "value"),
            Input("language-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_author_options(selected_year, selected_category, selected_language, selected_booktype, selected_book, refresh_signal):
            """Update author filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year
            
            _, df_exploded = _get_filtered_data(years, selected_language, None, selected_booktype, selected_book, selected_category)
            available_authors = get_unique_authors(df_exploded['Authors_Exploded'])
            
            return [{"label": f"All Authors ({len(available_authors)})", "value": "all"}] + [
                {"label": author, "value": author} for author in available_authors
            ]

        @self.app.callback(
            Output("booktype-filter", "options"),
            Input("year-filter", "value"),
            Input("category-filter", "value"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("book-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_booktype_options(selected_year, selected_category, selected_language, selected_author, selected_book, refresh_signal):
            """Update book type filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year
            
            df, _ = _get_filtered_data(years, selected_language, selected_author, None, selected_book, selected_category)
            available_types = sorted(df['BookType'].dropna().unique().tolist())
            
            type_labels = {"Ebook": "📱 eBook", "Paper": "📖 Paperback", "HardCover": "📚 Hardcover"}
            return [{"label": f"All Types ({len(available_types)})", "value": "all"}] + [
                {"label": type_labels.get(bt, bt), "value": bt} for bt in available_types
            ]

        @self.app.callback(
            Output("book-filter", "options"),
            Input("year-filter", "value"),
            Input("category-filter", "value"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_book_options(selected_year, selected_category, selected_language, selected_author, selected_booktype, refresh_signal):
            """Update book filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year
            
            df, _ = _get_filtered_data(years, selected_language, selected_author, selected_booktype, None, selected_category)
            available_books = sorted(df['book_nick_name'].dropna().unique().tolist())
            
            return [{"label": f"All Books ({len(available_books)})", "value": "all"}] + [
                {"label": book, "value": book} for book in available_books
            ]

        @self.app.callback(
            Output("category-filter", "options"),
            Input("year-filter", "value"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_category_options(selected_year, selected_language, selected_author, selected_booktype, selected_book, refresh_signal):
            """Update category filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year
            
            # Get filtered royalties data (without category filter)
            df, _ = _get_filtered_data(years, selected_language, selected_author, selected_booktype, selected_book, None)
            
            # Map nicknames back to categories from books database
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
            nickname_to_category = dict(zip(books_df['book_nick_name'], books_df['category']))
            
            available_categories = set()
            for nick in df['book_nick_name'].dropna().unique():
                if nick in nickname_to_category and nickname_to_category[nick]:
                    available_categories.add(nickname_to_category[nick])
            
            available_categories = sorted(list(available_categories))
            
            return [{"label": f"All Categories ({len(available_categories)})", "value": "all"}] + [
                {"label": cat, "value": cat} for cat in available_categories
            ]

        @self.app.callback(
            Output("year-filter", "value"),
            Output("language-filter", "value"),
            Output("author-filter", "value"),
            Output("booktype-filter", "value"),
            Output("book-filter", "value"),
            Output("category-filter", "value"),
            Input("reset-all-filters", "n_clicks"),
            prevent_initial_call=True
        )
        def reset_all_filters(n_clicks):
            """Reset all filters to their default values"""
            return CURRENT_YEAR, "all", "all", "all", "all", "all"

        @self.app.callback(
            Output("year-filter", "options"),
            Output("sales-language-display-mode", "options"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=True
        )
        def update_year_and_display_options(refresh_signal):
            """Update year filter and display mode options when new data is available"""
            # Get updated years
            years_reversed = sorted(self.available_years, reverse=True)
            year_options = [{"label": "Lifetime", "value": "lifetime"}] + \
                           [{"label": str(year), "value": year} for year in years_reversed]
            
            # Get updated languages for display mode
            all_languages = sort_with_accents([
                lang for lang in self.royalties['Language'].unique().tolist()
                if lang not in ['African Names', 'Bamileke']
            ])
            display_mode_options = (
                [{"label": "All (Stacked)", "value": "all_stacked"},
                 {"label": "All (Grouped)", "value": "all_grouped"}] +
                [{"label": lang, "value": f"language::{lang}"} for lang in all_languages]
            )
            
            return year_options, display_mode_options

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
            Input("year-filter", "value"),
            Input("data-refresh-signal", "data")
        )
        def update_year_store(selected_value, refresh_signal):
            """Update year store based on dropdown selection or data refresh"""
            # Note: refresh_signal is just a trigger to re-run this callback
            # which will pick up the new self.available_years from the new container instance
            
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
            Output("metric-titles", "children"),
            Output("metric-authors", "children"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_metrics(selected_years, selected_language, selected_author, selected_booktype, selected_book, selected_category, refresh_signal):
            """Update metrics based on selected years, language, author, book type, book, and category"""
            # refresh_signal is just a trigger to ensure metrics update when data changes
            
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
            
            # Apply author filter
            if selected_author and selected_author != "all":
                filtered_df = filter_by_author(filtered_df, selected_author, 'Authors')
                filtered_exploded = filtered_exploded[filtered_exploded['Authors_Exploded'].apply(lambda x: normalize_author_name(x)) == selected_author]
            
            # Apply book type filter
            if selected_booktype and selected_booktype != "all":
                filtered_df = filtered_df[filtered_df['BookType'] == selected_booktype]
                filtered_exploded = filtered_exploded[filtered_exploded['BookType'] == selected_booktype]
            
            # Apply book filter
            if selected_book and selected_book != "all":
                filtered_df = filtered_df[filtered_df['book_nick_name'] == selected_book]
                filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'] == selected_book]
            
            # Apply category filter
            if selected_category and selected_category != "all":
                try:
                    books_df = pd.read_csv(BOOKS_DATABASE_PATH)
                    category_books = books_df[books_df['category'] == selected_category]
                    
                    from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES, DB_NICKNAME_TO_ROYALTY
                    category_nicknames = set()
                    
                    # Get all database nicknames for this category
                    db_nicknames = category_books['book_nick_name'].dropna().tolist()
                    
                    for db_nick in db_nicknames:
                        # First, check if this DB nickname maps to royalty nicknames
                        if db_nick in DB_NICKNAME_TO_ROYALTY:
                            category_nicknames.update(DB_NICKNAME_TO_ROYALTY[db_nick])
                        else:
                            # Add the DB nickname itself (might match directly)
                            category_nicknames.add(db_nick)
                    
                    # Also try to match via title -> hardcoded nicknames
                    category_titles = category_books['title'].tolist()
                    for title in category_titles:
                        if title:
                            for hc_title, nickname in HARDCODED_TITLE_NICKNAMES.items():
                                if (title in hc_title or hc_title in str(title) or 
                                    title.split(':')[0].strip() == hc_title.split(':')[0].strip()):
                                    category_nicknames.add(nickname)
                                    break
                    
                    if category_nicknames:
                        filtered_df = filtered_df[filtered_df['book_nick_name'].isin(category_nicknames)]
                        filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'].isin(category_nicknames)]
                except Exception as e:
                    print(f"Error in category filter: {e}")
            
            metrics = SummaryMetrics.calculate_metrics(filtered_df, filtered_exploded)
            
            return (
                f"{metrics['total_books_sold']:,}",
                str(metrics['unique_titles']),
                str(metrics['unique_authors'])
            )
        
        @self.app.callback(
            Output("sales-trend-title", "children"),
            Output("sales-trend-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_sales_trend(selected_years, selected_language, selected_author, selected_booktype, selected_book, selected_category, refresh_signal):
            """Update sales trend chart with dynamic title"""
            trend_data = self.royalties
            filter_parts = []
            
            if selected_language and selected_language != "all":
                trend_data = trend_data[trend_data['Language'] == selected_language]
                filter_parts.append(selected_language)
            
            if selected_author and selected_author != "all":
                trend_data = filter_by_author(trend_data, selected_author, 'Authors')
                filter_parts.append(selected_author)
            
            if selected_booktype and selected_booktype != "all":
                trend_data = trend_data[trend_data['BookType'] == selected_booktype]
                filter_parts.append("📱 eBook" if selected_booktype == "Ebook" else "📖 Physical")
            
            if selected_book and selected_book != "all":
                trend_data = trend_data[trend_data['book_nick_name'] == selected_book]
                filter_parts.append(selected_book)
            
            # Apply category filter
            if selected_category and selected_category != "all":
                try:
                    books_df = pd.read_csv(BOOKS_DATABASE_PATH)
                    category_books = books_df[books_df['category'] == selected_category]
                    
                    from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES, DB_NICKNAME_TO_ROYALTY
                    category_nicknames = set()
                    
                    # Get all database nicknames for this category
                    db_nicknames = category_books['book_nick_name'].dropna().tolist()
                    
                    for db_nick in db_nicknames:
                        if db_nick in DB_NICKNAME_TO_ROYALTY:
                            category_nicknames.update(DB_NICKNAME_TO_ROYALTY[db_nick])
                        else:
                            category_nicknames.add(db_nick)
                    
                    # Also match via title -> hardcoded nicknames
                    category_titles = category_books['title'].tolist()
                    for title in category_titles:
                        if title:
                            for hc_title, nickname in HARDCODED_TITLE_NICKNAMES.items():
                                if (title in hc_title or hc_title in str(title) or 
                                    title.split(':')[0].strip() == hc_title.split(':')[0].strip()):
                                    category_nicknames.add(nickname)
                                    break
                    
                    if category_nicknames:
                        trend_data = trend_data[trend_data['book_nick_name'].isin(category_nicknames)]
                    filter_parts.append(f"📚 {selected_category}")
                except Exception:
                    pass
            
            total_books = trend_data['Net Units Sold'].sum()
            filter_text = " | ".join(filter_parts) if filter_parts else "All"
            trend_title = f"📈 Sales Trend: {filter_text} ({min(self.available_years)} - {max(self.available_years)}): {int(total_books):,} books sold"
            
            from src.visualization.charts import SalesCharts
            fig = SalesCharts.books_sold_per_year(trend_data, title=trend_title)
            return trend_title, fig
        
        @self.app.callback(
            Output("sales-by-language-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("sales-language-display-mode", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_sales_by_language(selected_years, selected_language, selected_author, selected_booktype, selected_book, display_mode, refresh_signal):
            """Update sales by language stacked chart by year"""
            if not selected_years:
                filtered_df = self.royalties
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
            
            # Apply language filter
            if selected_language and selected_language != "all":
                filtered_df = filtered_df[filtered_df['Language'] == selected_language]
            
            # Apply author filter
            if selected_author and selected_author != "all":
                filtered_df = filter_by_author(filtered_df, selected_author, 'Authors')
            
            # Apply book type filter
            if selected_booktype and selected_booktype != "all":
                filtered_df = filtered_df[filtered_df['BookType'] == selected_booktype]
            
            # Apply book filter
            if selected_book and selected_book != "all":
                filtered_df = filtered_df[filtered_df['book_nick_name'] == selected_book]
            
            # Build filter text for title
            filter_parts = []
            if selected_years and len(selected_years) == 1:
                filter_parts.append(str(selected_years[0]))
            elif selected_years and len(selected_years) > 1:
                filter_parts.append(f"{min(selected_years)}-{max(selected_years)}")
            if selected_language and selected_language != "all":
                filter_parts.append(selected_language)
            if selected_author and selected_author != "all":
                filter_parts.append(selected_author)
            if selected_booktype and selected_booktype != "all":
                filter_parts.append("📱 eBook" if selected_booktype == "Ebook" else "📖 Physical")
            if selected_book and selected_book != "all":
                filter_parts.append(selected_book)
            filter_text = " | ".join(filter_parts) if filter_parts else ""
            
            if len(filtered_df) == 0:
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_annotation(text="No sales data available", xref="paper", yref="paper",
                                   x=0.5, y=0.5, showarrow=False)
                title_with_filters = "Sales by Language (No Data)"
                if filter_text:
                    title_with_filters = f"Sales by Language - {filter_text} (No Data)"
                fig.update_layout(template="plotly_dark", height=400, title=title_with_filters)
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

            # Build chart title with filters
            if filter_text:
                chart_title = f"Sales by Language - {filter_text} ({title_suffix})"
            else:
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
            Output("tab-content", "children"),
            Input("dashboard-tabs", "active_tab"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            prevent_initial_call=False
        )
        def render_tab_content(active_tab, selected_years, selected_language, selected_author, selected_booktype, selected_book, selected_category):
            """Render content based on active tab, years, language, author, book type, book, and category filter"""
            
            # Filter data based on selected years
            if not selected_years:
                filtered_royalties = self.royalties
                filtered_exploded = self.royalties_exploded
            else:
                filtered_royalties = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'].isin(selected_years)]
            
            # Filter by language if selected
            if selected_language and selected_language != "all":
                filtered_royalties = filtered_royalties[filtered_royalties['Language'] == selected_language]
                filtered_exploded = filtered_exploded[filtered_exploded['Language'] == selected_language]
            
            # Filter by author if selected
            if selected_author and selected_author != "all":
                filtered_royalties = filter_by_author(filtered_royalties, selected_author, 'Authors')
                filtered_exploded = filtered_exploded[filtered_exploded['Authors_Exploded'].apply(lambda x: normalize_author_name(x)) == selected_author]
            
            # Filter by book type if selected
            if selected_booktype and selected_booktype != "all":
                filtered_royalties = filtered_royalties[filtered_royalties['BookType'] == selected_booktype]
                filtered_exploded = filtered_exploded[filtered_exploded['BookType'] == selected_booktype]
            
            # Filter by book if selected
            if selected_book and selected_book != "all":
                filtered_royalties = filtered_royalties[filtered_royalties['book_nick_name'] == selected_book]
                filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'] == selected_book]
            
            # Filter by category if selected (applies to all tabs)
            if selected_category and selected_category != "all":
                try:
                    # Load books database to get title -> category mapping
                    books_df = pd.read_csv(BOOKS_DATABASE_PATH)
                    category_books = books_df[books_df['category'] == selected_category]
                    
                    from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES, DB_NICKNAME_TO_ROYALTY
                    category_nicknames = set()
                    
                    # Get all database nicknames for this category and map to royalty nicknames
                    db_nicknames = category_books['book_nick_name'].dropna().tolist()
                    for db_nick in db_nicknames:
                        if db_nick in DB_NICKNAME_TO_ROYALTY:
                            category_nicknames.update(DB_NICKNAME_TO_ROYALTY[db_nick])
                        else:
                            category_nicknames.add(db_nick)
                    
                    # Also match via title -> hardcoded nicknames
                    category_titles = category_books['title'].tolist()
                    for title in category_titles:
                        if title:
                            for hc_title, nickname in HARDCODED_TITLE_NICKNAMES.items():
                                if (title in hc_title or hc_title in str(title) or 
                                    title.split(':')[0].strip() == hc_title.split(':')[0].strip()):
                                    category_nicknames.add(nickname)
                                    break
                    
                    # Filter royalties to only include books in this category
                    if category_nicknames:
                        filtered_royalties = filtered_royalties[filtered_royalties['book_nick_name'].isin(category_nicknames)]
                        filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'].isin(category_nicknames)]
                except Exception as e:
                    print(f"Category filter error: {e}")
                    pass  # If books database can't be loaded, skip category filter
            
            # Build filter text for dynamic titles
            filter_parts = []
            if selected_years and len(selected_years) == 1:
                filter_parts.append(str(selected_years[0]))
            elif selected_years and len(selected_years) > 1:
                filter_parts.append(f"{min(selected_years)} - {max(selected_years)}")
            else:
                filter_parts.append("Lifetime")
            if selected_language and selected_language != "all":
                filter_parts.append(selected_language)
            if selected_author and selected_author != "all":
                filter_parts.append(selected_author)
            if selected_booktype and selected_booktype != "all":
                filter_parts.append("📱 eBook" if selected_booktype == "Ebook" else "📖 Physical")
            if selected_book and selected_book != "all":
                filter_parts.append(selected_book)
            if selected_category and selected_category != "all":
                filter_parts.append(f"📚 {selected_category}")
            filter_text = " | ".join(filter_parts)
            
            if active_tab == "purchase":
                return self._create_purchase_tab(filtered_royalties, selected_language, selected_author, selected_booktype, selected_book, selected_category)
            elif active_tab == "sales":
                return self._create_sales_tab(filtered_royalties, selected_years, selected_language)
            elif active_tab == "books":
                return self._create_books_tab(filtered_royalties)
            elif active_tab == "geography":
                return self._create_geography_tab(filtered_royalties, filter_text)
            
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
            [Input('author-selector-dropdown', 'value'),
             Input('year-filter-store', 'data'),
             Input('language-filter', 'value'),
             Input('author-filter', 'value')],
            State('dashboard-tabs', 'active_tab'),
            prevent_initial_call=False
        )
        def update_author_earnings_history(selected_authors, selected_years, selected_language, selected_author, active_tab):
            """Update author earnings history chart based on selected authors and filters"""
            import plotly.graph_objects as go
            
            # Apply filters to get filtered data
            if not selected_years:
                filtered_exploded = self.royalties_exploded
            else:
                filtered_exploded = self.royalties_exploded[self.royalties_exploded['Year Sold'].isin(selected_years)]
            
            # Filter by language if selected
            if selected_language and selected_language != "all":
                filtered_exploded = filtered_exploded[filtered_exploded['Language'] == selected_language]
            
            # Filter by author if selected
            if selected_author and selected_author != "all":
                filtered_exploded = filtered_exploded[filtered_exploded['Authors_Exploded'].apply(lambda x: normalize_author_name(x)) == selected_author]
            
            # Handle empty data
            if len(filtered_exploded) == 0:
                fig = go.Figure()
                fig.add_annotation(
                    text="No data available for the selected filters",
                    xref="paper", yref="paper",
                    x=0.5, y=0.5, showarrow=False,
                    font=dict(size=16, color="#888")
                )
                fig.update_layout(
                    title='Author Earnings by Year',
                    template="plotly_dark",
                    height=400
                )
                return fig
            
            if active_tab != 'trends':
                return EarningHistoryCharts.earnings_trend_all_authors(filtered_exploded)
            
            if selected_authors and len(selected_authors) > 0:
                # If specific authors are selected, show only those
                return EarningHistoryCharts.earnings_trend_selected_authors(filtered_exploded, selected_authors)
            else:
                # If no authors selected, show all
                return EarningHistoryCharts.earnings_trend_all_authors(filtered_exploded)
        
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
        
        # Purchase tab download callbacks
        @self.app.callback(
            Output("download-purchase-csv", "data"),
            Input("download-purchase-csv-btn", "n_clicks"),
            State("purchase-download-data", "data"),
            prevent_initial_call=True,
        )
        def download_purchase_csv(n_clicks, download_data_str):
            """Download filtered books data as CSV"""
            if not download_data_str:
                return None
            
            import io
            import json
            download_data = json.loads(download_data_str)
            df = pd.read_json(io.StringIO(download_data['data']), orient='split')
            filename_suffix = download_data.get('filename_suffix', 'all_books')
            
            # Create CSV with UTF-8-sig BOM
            csv_content = df.to_csv(index=False)
            csv_with_bom = '\ufeff' + csv_content
            return dict(content=csv_with_bom, filename=f"resulam_books_{filename_suffix}.csv")
        
        @self.app.callback(
            Output("download-purchase-excel", "data"),
            Input("download-purchase-excel-btn", "n_clicks"),
            State("purchase-download-data", "data"),
            prevent_initial_call=True,
        )
        def download_purchase_excel(n_clicks, download_data_str):
            """Download filtered books data as Excel"""
            if not download_data_str:
                return None
            
            import io
            import json
            download_data = json.loads(download_data_str)
            df = pd.read_json(io.StringIO(download_data['data']), orient='split')
            filename_suffix = download_data.get('filename_suffix', 'all_books')
            
            # Create Excel file in memory
            output = io.BytesIO()
            with pd.ExcelWriter(output, engine='openpyxl') as writer:
                df.to_excel(writer, index=False, sheet_name='Books')
            output.seek(0)
            
            return dcc.send_bytes(output.getvalue(), f"resulam_books_{filename_suffix}.xlsx")
        
        @self.app.callback(
            Output("download-purchase-txt", "data"),
            Input("download-purchase-txt-btn", "n_clicks"),
            State("purchase-download-data", "data"),
            prevent_initial_call=True,
        )
        def download_purchase_txt(n_clicks, download_data_str):
            """Download filtered books data as plain text"""
            if not download_data_str:
                return None
            
            import io
            import json
            download_data = json.loads(download_data_str)
            df = pd.read_json(io.StringIO(download_data['data']), orient='split')
            filter_text = download_data.get('filter_text', 'All Books')
            filter_info = download_data.get('filters', {})
            
            # Build detailed title with filter info
            title_parts = ["RESULAM BOOKS - AMAZON PURCHASE LINKS"]
            filter_details = []
            if filter_info.get('category'):
                filter_details.append(f"Category: {filter_info['category']}")
            if filter_info.get('language'):
                filter_details.append(f"Language: {filter_info['language']}")
            if filter_info.get('author'):
                filter_details.append(f"Author: {filter_info['author']}")
            if filter_info.get('booktype'):
                format_labels = {"Ebook": "eBook", "Paper": "Paperback", "HardCover": "Hardcover"}
                filter_details.append(f"Format: {format_labels.get(filter_info['booktype'], filter_info['booktype'])}")
            if filter_info.get('book'):
                filter_details.append(f"Book: {filter_info['book']}")
            
            # Create formatted plain text
            txt_content = "=" * 100 + "\n"
            txt_content += "RESULAM BOOKS - AMAZON PURCHASE LINKS\n"
            if filter_details:
                txt_content += f"Filtered by: {' | '.join(filter_details)}\n"
            txt_content += "=" * 100 + "\n\n"
            txt_content += f"Total Books: {len(df)}\n"
            txt_content += f"Generated: {pd.Timestamp.now().strftime('%Y-%m-%d %H:%M:%S')}\n"
            txt_content += "=" * 100 + "\n\n"
            
            for i, row in df.iterrows():
                txt_content += f"Book #{i+1}\n"
                txt_content += "-" * 50 + "\n"
                txt_content += f"Title:    {row['Title']}\n"
                txt_content += f"Language: {row['Language']}\n"
                txt_content += f"Authors:  {row['Authors']}\n"
                txt_content += f"Book ID:  {row['Book ID']}\n"
                txt_content += "\nPurchase Links:\n"
                
                if pd.notna(row['Paperback Link']) and row['Paperback Link']:
                    txt_content += f"  📖 Paperback: {row['Paperback Link']}\n"
                if pd.notna(row['eBook Link']) and row['eBook Link']:
                    txt_content += f"  📱 eBook:     {row['eBook Link']}\n"
                if pd.notna(row['Hardcover Link']) and row['Hardcover Link']:
                    txt_content += f"  📚 Hardcover: {row['Hardcover Link']}\n"
                
                txt_content += "\n"
            
            txt_content += "=" * 100 + "\n"
            txt_content += "End of Report\n"
            
            # Build dynamic filename based on filters
            filename_parts = ["resulam_books"]
            if filter_info:
                if filter_info.get('category'):
                    cat_name = filter_info['category'].lower().replace(' ', '_').replace('-', '_')[:20]
                    filename_parts.append(cat_name)
                if filter_info.get('author'):
                    author_name = filter_info['author'].lower().replace(' ', '_')[:15]
                    filename_parts.append(author_name)
                if filter_info.get('language'):
                    filename_parts.append(filter_info['language'].lower())
                if filter_info.get('year'):
                    filename_parts.append(str(filter_info['year']))
            filename_parts.append("purchase_links")
            filename = "_".join(filename_parts) + ".txt"
            
            # Add UTF-8 BOM
            txt_with_bom = '\ufeff' + txt_content
            return dict(content=txt_with_bom, filename=filename)
    
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
            # Total Sales by Book section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4("📚 Total Sales by Book")),
                        dbc.CardBody([
                            html.Div([
                                dcc.Graph(
                                    figure=SalesCharts.sales_by_book_horizontal(data),
                                    config={'displayModeBar': False}
                                )
                            ], style={"maxHeight": "400px", "overflowY": "auto"})
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            # eBook vs Physical Books Analysis section
            dbc.Row([
                dbc.Col([
                    html.H4("📱 eBook vs 📖 Physical Books Analysis", className="mb-3 mt-2")
                ])
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.ebook_vs_physical_pie(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.ebook_vs_physical_by_year(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=4),
                dbc.Col([
                    dbc.Card([
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.ebook_vs_physical_revenue(data),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=4)
            ]),
            # Summary statistics
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5("📊 Format Statistics")),
                        dbc.CardBody([
                            self._create_format_stats_table(data)
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ])
        ], fluid=True)
    
    def _create_format_stats_table(self, data):
        """Create statistics table for eBook vs Physical"""
        if len(data) == 0 or 'BookType' not in data.columns:
            return html.P("No data available")
        
        # Calculate stats
        ebook_data = data[data['BookType'] == 'Ebook']
        physical_data = data[data['BookType'].isin(['Paper', 'HardCover'])]
        paper_data = data[data['BookType'] == 'Paper']
        hardcover_data = data[data['BookType'] == 'HardCover']
        
        ebook_units = ebook_data['Net Units Sold'].sum()
        physical_units = physical_data['Net Units Sold'].sum()
        paper_units = paper_data['Net Units Sold'].sum()
        hardcover_units = hardcover_data['Net Units Sold'].sum()
        total_units = ebook_units + physical_units
        
        ebook_revenue = ebook_data['Royalty USD'].sum()
        physical_revenue = physical_data['Royalty USD'].sum()
        paper_revenue = paper_data['Royalty USD'].sum()
        hardcover_revenue = hardcover_data['Royalty USD'].sum()
        
        return dbc.Table([
            html.Thead(html.Tr([
                html.Th("Format"),
                html.Th("Units Sold"),
                html.Th("% of Sales"),
                html.Th("Revenue (USD)"),
                html.Th("Avg Price/Unit")
            ])),
            html.Tbody([
                html.Tr([
                    html.Td("📱 eBook"),
                    html.Td(f"{ebook_units:,}"),
                    html.Td(f"{(ebook_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${ebook_revenue:,.2f}"),
                    html.Td(f"${(ebook_revenue/ebook_units) if ebook_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td("📖 Paperback"),
                    html.Td(f"{paper_units:,}"),
                    html.Td(f"{(paper_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${paper_revenue:,.2f}"),
                    html.Td(f"${(paper_revenue/paper_units) if paper_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td("📕 Hardcover"),
                    html.Td(f"{hardcover_units:,}"),
                    html.Td(f"{(hardcover_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${hardcover_revenue:,.2f}"),
                    html.Td(f"${(hardcover_revenue/hardcover_units) if hardcover_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td(html.Strong("Total")),
                    html.Td(html.Strong(f"{total_units:,}")),
                    html.Td(html.Strong("100%")),
                    html.Td(html.Strong(f"${ebook_revenue + physical_revenue:,.2f}")),
                    html.Td("")
                ], style={"backgroundColor": "#f8f9fa"})
            ])
        ], bordered=True, hover=True, striped=True, size="sm")
    
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
            years_in_data = []
            languages_in_data = []
        
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
                                        dbc.Col([html.H4(f"{year_str} 👨🏿‍👩🏿‍👧🏿 African Authors (By Earnings)")], md=9),
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
                   format_years_compact(years_in_data)),
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
    
    def _create_geography_tab(self, data=None, filter_text="Lifetime"):
        """Create geographic distribution tab content"""
        if data is None:
            data = self.royalties
        
        # Calculate totals for titles
        total_sales = int(data['Net Units Sold'].sum()) if len(data) > 0 else 0
        total_revenue = data['Royalty USD'].sum() if len(data) > 0 else 0.0
        
        # Create empty figure for when there's no data
        if len(data) == 0:
            empty_fig = go.Figure()
            empty_fig.update_layout(
                template="plotly_dark",
                annotations=[{
                    "text": "No data available for the selected filters",
                    "xref": "paper",
                    "yref": "paper",
                    "x": 0.5,
                    "y": 0.5,
                    "showarrow": False,
                    "font": {"size": 16, "color": "#888"}
                }],
                height=400
            )
            sales_fig = empty_fig
            revenue_fig = empty_fig
        else:
            sales_fig = GeographicCharts.sales_by_marketplace(data)
            revenue_fig = GeographicCharts.revenue_by_marketplace(data)
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(f"🌍 Sales Distribution by Marketplace ({filter_text}): {total_sales:,} books")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=sales_fig,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6),
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(f"💵 Revenue by Marketplace ({filter_text}): ${total_revenue:,.2f}")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=revenue_fig,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=6)
            ])
        ], fluid=True)
    
    def _create_purchase_tab(self, data=None, selected_language=None, selected_author=None, selected_booktype=None, selected_book=None, selected_category=None):
        """Create purchase the book tab content with Amazon links"""
        import unicodedata
        
        def normalize_text(text):
            """Remove accents and normalize text for comparison"""
            if pd.isna(text) or not text:
                return ""
            # Normalize unicode and remove accents
            normalized = unicodedata.normalize('NFD', str(text))
            return ''.join(c for c in normalized if unicodedata.category(c) != 'Mn').lower()
        
        try:
            # Load the books database
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
        except Exception as e:
            return dbc.Container([
                dbc.Alert(f"Unable to load books database: {str(e)}", color="warning")
            ], fluid=True)
        
        # Start with all books - don't filter by royalties data
        filtered_books = books_df.copy()
        
        # Apply language filter if selected
        if selected_language and selected_language != "all":
            lang_filtered = filtered_books[filtered_books['language_name'].str.lower() == selected_language.lower()]
            if len(lang_filtered) > 0:
                filtered_books = lang_filtered
        
        # Apply author filter if selected
        if selected_author and selected_author != "all":
            # Use fuzzy matching with accent normalization
            # This handles variations like "Joséphine" vs "Josephine" and name order variations
            author_parts = [normalize_text(p) for p in selected_author.split() if len(p.strip()) > 2]
            
            def author_matches(book_authors):
                if pd.isna(book_authors) or not book_authors:
                    return False
                book_authors_normalized = normalize_text(book_authors)
                # Check if at least 2 significant parts match (for names like "Claude Lionel Mvondo Edzoa")
                # Or all parts for shorter names
                min_matches = min(2, len(author_parts))
                matches = sum(1 for part in author_parts if part in book_authors_normalized)
                return matches >= min_matches
            
            author_filtered = filtered_books[filtered_books['authors'].apply(author_matches)]
            if len(author_filtered) > 0:
                filtered_books = author_filtered
        
        # Apply book filter if selected (by nickname)
        # Use flexible matching since nicknames differ between royalties data and books database
        if selected_book and selected_book != "all":
            selected_book_normalized = normalize_text(selected_book).replace('_', ' ')
            
            def book_matches(book_nickname):
                if pd.isna(book_nickname) or not book_nickname:
                    return False
                book_nickname_normalized = normalize_text(book_nickname).replace('_', ' ')
                # Check for exact match first
                if book_nickname_normalized == selected_book_normalized:
                    return True
                # Check if one contains the other (handles partial matches)
                if selected_book_normalized in book_nickname_normalized or book_nickname_normalized in selected_book_normalized:
                    return True
                # Check word overlap - if most words match
                selected_words = set(selected_book_normalized.split())
                book_words = set(book_nickname_normalized.split())
                common = selected_words & book_words
                # At least 2 significant words match
                return len(common) >= 2
            
            book_filtered = filtered_books[filtered_books['book_nick_name'].apply(book_matches)]
            if len(book_filtered) > 0:
                filtered_books = book_filtered
        
        # Apply book type filter if selected (show books that have that format available)
        if selected_booktype and selected_booktype != "all":
            if selected_booktype == "Ebook":
                booktype_filtered = filtered_books[filtered_books['ebook'].notna() & (filtered_books['ebook'] != '')]
            elif selected_booktype == "Paper":
                booktype_filtered = filtered_books[filtered_books['paperback'].notna() & (filtered_books['paperback'] != '')]
            elif selected_booktype == "HardCover":
                booktype_filtered = filtered_books[filtered_books['hard_cover'].notna() & (filtered_books['hard_cover'] != '')]
            else:
                booktype_filtered = filtered_books
            if len(booktype_filtered) > 0:
                filtered_books = booktype_filtered
        
        # Apply category filter if selected (strict filter - must match exactly)
        if selected_category and selected_category != "all":
            filtered_books = filtered_books[filtered_books['category'] == selected_category]
        
        if len(filtered_books) == 0:
            return dbc.Container([
                dbc.Alert("No books found matching your filters.", color="info")
            ], fluid=True)
        
        # Determine if we're using S3 (online) or local assets
        import os
        use_s3_images = os.getenv('USE_S3_DATA', 'false').lower() == 'true'
        s3_base_url = "https://resulam-images.s3.amazonaws.com/ResulamBookCoversQRCode_Compressed"
        
        # Build a mapping of book covers (book_id -> image_url)
        available_covers = {}
        
        if use_s3_images:
            # Online version - use public S3 URLs
            try:
                import boto3
                from urllib.parse import quote
                s3 = boto3.client('s3')
                bucket_name = 'resulam-images'
                prefix = 'ResulamBookCoversQRCode_Compressed/Book'
                
                resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
                for obj in resp.get('Contents', []):
                    key = obj['Key']
                    filename = key.split('/')[-1]  # e.g., "Book1__nufi_contes....PNG"
                    if filename.lower().startswith('book'):
                        # Extract book number from filename
                        name_part = filename[4:]  # After "Book"
                        parts = name_part.split('_', 1)
                        if parts:
                            num_str = parts[0].strip('_')
                            if num_str.isdigit():
                                book_num = int(num_str)
                                # Use public URL (bucket policy allows public read)
                                available_covers[book_num] = f"{s3_base_url}/{quote(filename)}"
            except Exception as e:
                print(f"Warning: Could not fetch S3 cover list: {e}")
        else:
            # Local version - scan assets/book_covers folder
            book_covers_path = Path(__file__).parent.parent.parent / 'assets' / 'book_covers'
            if book_covers_path.exists():
                for img_file in book_covers_path.glob('book*.*'):
                    # Extract book number from filename like "book1_nickname.png"
                    name = img_file.stem.lower()  # e.g., "book1_nufi_contes..."
                    if name.startswith('book'):
                        # Extract the book number (handle both book1_ and book1__ patterns)
                        parts = name[4:].split('_', 1)  # After "book"
                        if parts:
                            # Handle patterns like "book1__" or "book1_"
                            num_str = parts[0].strip('_')
                            if num_str.isdigit():
                                book_num = int(num_str)
                                # Store with relative path for web serving
                                available_covers[book_num] = f"assets/book_covers/{img_file.name}"
        
        # Create book cards
        book_cards = []
        for _, book in filtered_books.iterrows():
            title = book.get('title', 'Unknown Title')
            # Clean title by removing date suffix
            if ' – ' in str(title):
                title = str(title).split(' – ')[0].strip()
            
            language = book.get('language_name', 'Unknown')
            authors = book.get('authors', 'Unknown')
            book_id = book.get('id', 0)
            
            # Get book cover image from pre-built mapping
            cover_image = available_covers.get(book_id, None)
            
            # Get links
            paperback_link = book.get('paperback', '')
            ebook_link = book.get('ebook', '')
            hardcover_link = book.get('hard_cover', '')
            
            # Create link buttons
            link_buttons = []
            if pd.notna(paperback_link) and paperback_link:
                link_buttons.append(
                    dbc.Button(
                        [html.I(className="fas fa-book me-2"), "📖 Paperback"],
                        href=paperback_link,
                        target="_blank",
                        color="primary",
                        size="sm",
                        className="me-2 mb-2"
                    )
                )
            if pd.notna(ebook_link) and ebook_link:
                link_buttons.append(
                    dbc.Button(
                        [html.I(className="fas fa-tablet-alt me-2"), "📱 eBook"],
                        href=ebook_link,
                        target="_blank",
                        color="success",
                        size="sm",
                        className="me-2 mb-2"
                    )
                )
            if pd.notna(hardcover_link) and hardcover_link:
                link_buttons.append(
                    dbc.Button(
                        [html.I(className="fas fa-book-open me-2"), "📚 Hardcover"],
                        href=hardcover_link,
                        target="_blank",
                        color="warning",
                        size="sm",
                        className="me-2 mb-2"
                    )
                )
            
            if not link_buttons:
                link_buttons.append(html.Span("No purchase links available", className="text-muted"))
            
            # Determine the best link for the cover image (prefer paperback, then ebook, then hardcover)
            image_link = None
            if pd.notna(paperback_link) and paperback_link:
                image_link = paperback_link
            elif pd.notna(ebook_link) and ebook_link:
                image_link = ebook_link
            elif pd.notna(hardcover_link) and hardcover_link:
                image_link = hardcover_link
            
            # Build card with or without cover image
            card_children = []
            
            # Add cover image if available (make it clickable)
            if cover_image:
                cover_img = dbc.CardImg(
                    src=cover_image,
                    top=True,
                    style={"height": "250px", "objectFit": "contain", "backgroundColor": "#f8f9fa", "cursor": "pointer" if image_link else "default"}
                )
                # Wrap image in a link if we have a purchase link
                if image_link:
                    card_children.append(
                        html.A(cover_img, href=image_link, target="_blank")
                    )
                else:
                    card_children.append(cover_img)
            
            # Add card body
            card_children.append(
                dbc.CardBody([
                    html.H6(title[:70] + "..." if len(str(title)) > 70 else title, className="card-title", style={"fontSize": "0.9rem", "fontWeight": "600"}),
                    html.P([
                        html.Span(f"🌐 {language}", className="me-2"),
                        html.Br(),
                        html.Span(f"✍🏿 {authors}", style={"fontSize": "0.8rem"})
                    ], className="card-text text-muted small mb-2"),
                    html.Div(link_buttons, className="mt-auto")
                ], className="d-flex flex-column")
            )
            
            card = dbc.Card(card_children, className="shadow-sm mb-3 h-100")
            
            book_cards.append(dbc.Col(card, xs=12, sm=6, md=4, lg=3, className="mb-3"))
        
        # Build filter summary
        filter_parts = []
        if selected_language and selected_language != "all":
            filter_parts.append(f"Language: {selected_language}")
        if selected_author and selected_author != "all":
            filter_parts.append(f"Author: {selected_author}")
        if selected_booktype and selected_booktype != "all":
            format_labels = {"Ebook": "📱 eBook", "Paper": "📖 Paperback", "HardCover": "📚 Hardcover"}
            filter_parts.append(f"Format: {format_labels.get(selected_booktype, selected_booktype)}")
        if selected_book and selected_book != "all":
            filter_parts.append(f"Book: {selected_book}")
        if selected_category and selected_category != "all":
            filter_parts.append(f"Category: {selected_category}")
        filter_text = " | ".join(filter_parts) if filter_parts else "All Books"
        
        # Build filename-safe filter text
        filename_parts = []
        if selected_category and selected_category != "all":
            filename_parts.append(selected_category.replace(' - ', '_').replace(' ', '_'))
        if selected_language and selected_language != "all":
            filename_parts.append(selected_language)
        if selected_author and selected_author != "all":
            filename_parts.append(selected_author.replace(' ', '_'))
        if selected_booktype and selected_booktype != "all":
            filename_parts.append(selected_booktype)
        filename_suffix = "_".join(filename_parts) if filename_parts else "all_books"
        # Clean filename
        filename_suffix = "".join(c if c.isalnum() or c in '_-' else '_' for c in filename_suffix)
        
        # Prepare download data - clean columns for export
        download_df = filtered_books[['title', 'language_name', 'authors', 'book_nick_name', 'paperback', 'ebook', 'hard_cover']].copy()
        download_df.columns = ['Title', 'Language', 'Authors', 'Book ID', 'Paperback Link', 'eBook Link', 'Hardcover Link']
        # Clean title by removing date suffix
        download_df['Title'] = download_df['Title'].apply(lambda x: str(x).split(' – ')[0].strip() if ' – ' in str(x) else x)
        
        # Store the filtered data with metadata for download callbacks
        import json
        download_data = {
            'data': download_df.to_json(date_format='iso', orient='split'),
            'filter_text': filter_text,
            'filename_suffix': filename_suffix,
            'filters': {
                'category': selected_category if selected_category and selected_category != "all" else None,
                'language': selected_language if selected_language and selected_language != "all" else None,
                'author': selected_author if selected_author and selected_author != "all" else None,
                'booktype': selected_booktype if selected_booktype and selected_booktype != "all" else None,
                'book': selected_book if selected_book and selected_book != "all" else None
            }
        }
        download_data_json = json.dumps(download_data)
        
        return dbc.Container([
            # Hidden store for download data
            dcc.Store(id='purchase-download-data', data=download_data_json),
            dbc.Row([
                dbc.Col([
                    html.H3(f"🛒 Purchase Our Books on Amazon ({filter_text})", className="mb-3"),
                    html.Div([
                        html.Span(f"Showing {len(filtered_books)} books. Click on the format to purchase.", className="text-muted me-4"),
                        dbc.Button("📥 CSV", id="download-purchase-csv-btn", color="info", size="sm", className="me-2"),
                        dbc.Button("📥 Excel", id="download-purchase-excel-btn", color="success", size="sm", className="me-2"),
                        dbc.Button("📥 Text", id="download-purchase-txt-btn", color="secondary", size="sm"),
                    ], className="mb-4 d-flex align-items-center"),
                    dcc.Download(id="download-purchase-csv"),
                    dcc.Download(id="download-purchase-excel"),
                    dcc.Download(id="download-purchase-txt"),
                ])
            ]),
            dbc.Row(book_cards)
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
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_returns_table(selected_years, selected_language, selected_booktype, selected_book, refresh_signal):
            """Show books with refunds"""
            if not selected_years:
                filtered_df = self.royalties
            else:
                filtered_df = self.royalties[self.royalties['Year Sold'].isin(selected_years)]
            
            if selected_language and selected_language != "all":
                filtered_df = filtered_df[filtered_df['Language'] == selected_language]
            
            if selected_booktype and selected_booktype != "all":
                filtered_df = filtered_df[filtered_df['BookType'] == selected_booktype]
            
            if selected_book and selected_book != "all":
                filtered_df = filtered_df[filtered_df['book_nick_name'] == selected_book]
            
            # Get books with refunds - use book_nick_name (nickname) instead of full Title
            returns_df = filtered_df[filtered_df['Units Refunded'] > 0][['book_nick_name', 'Units Sold', 'Units Refunded', 'Marketplace', 'Royalty Date']].copy()
            returns_df = returns_df.rename(columns={'book_nick_name': 'Book'})
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


def create_dashboard(data: Dict[str, pd.DataFrame]) -> PublicDashboard:
    """
    Factory function to create public dashboard instance
    
    Args:
        data: Dictionary containing processed dataframes
        
    Returns:
        PublicDashboard instance
    """
    return PublicDashboard(data)
