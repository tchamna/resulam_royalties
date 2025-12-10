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
from ..visualization.author_trends import AuthorTrendCharts


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
                        f"Book Sales Analysis: 2015 - {CURRENT_YEAR}",
                        className="text-center text-muted mb-4"
                    )
                ])
            ])
        ], fluid=True, className="bg-light py-4 mb-4")
        
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
            dbc.Tab(label="📈 Author Trends", tab_id="trends"),
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
        
        # Callback to update the year-filter-store when a year is selected
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
            
            return (
                f"{metrics['total_books_sold']:,}",
                f"${metrics['net_revenue_usd']:,.2f}",
                str(metrics['unique_titles']),
                str(metrics['unique_authors'])
            )
        
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
                return self._create_trends_tab(filtered_exploded)
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
        def update_author_trends(selected_authors, active_tab):
            """Update author trends chart based on selected authors"""
            if active_tab != 'trends':
                return AuthorTrendCharts.earnings_trend_all_authors(self.royalties_exploded)
            
            if selected_authors and len(selected_authors) > 0:
                # If specific authors are selected, show only those
                return AuthorTrendCharts.earnings_trend_selected_authors(self.royalties_exploded, selected_authors)
            else:
                # If no authors selected, show all
                return AuthorTrendCharts.earnings_trend_all_authors(self.royalties_exploded)
        
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
        
        # Trend chart shows historical data (2015-2025) but respects language filter
        trend_data = self.royalties
        if selected_language and selected_language != "all":
            trend_data = self.royalties[self.royalties['Language'] == selected_language]
            total_books = trend_data['Net Units Sold'].sum()
            trend_title = f"📈 Sales Trend: {selected_language} ({min(self.available_years)} - {max(self.available_years)}): {int(total_books):,} books sold"
        else:
            total_books = self.royalties['Net Units Sold'].sum()
            trend_title = f"📈 Sales Trend: {min(self.available_years)} - {max(self.available_years)}: {int(total_books):,} books sold"
        
        # Create title for language chart (respects language filter)
        if selected_language and selected_language != "all":
            language_title = f"🌐 Sales by Language: {selected_language}"
        else:
            language_title = "🌐 Sales by Language (All - Grouped)"
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(trend_title)),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.books_sold_per_year(trend_data, title=trend_title),
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(language_title)),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=SalesCharts.sales_by_language_stacked(data, title=language_title),
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
                                        html.Li(f"{author}: ${share:,.2f}", className="text-muted mb-2")
                                        for author, share in sorted(author_data.items(), key=lambda x: x[1], reverse=False)
                                    ]),
                                    html.Hr(),
                                    html.H5(f"Total: ${sum(author_data.values()):,.2f}", className="text-primary font-weight-bold")
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
                                            className="text-muted mb-2"
                                        )
                                        for author, share in sorted(author_data.items(), key=lambda x: x[1], reverse=False)
                                    ]),
                                    html.Hr(),
                                    html.H5(
                                        f"Total: ${sum(max(5, share) for share in author_data.values()):,.2f} / {int(sum((max(5, share) * 655 + 2) // 5 * 5 for share in author_data.values())):,} FCFA",
                                        className="text-primary font-weight-bold"
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
    
    def _create_trends_tab(self, data=None):
        """Create author trends tab with bar chart and vertical checkbox dropdown"""
        if data is None:
            data = self.royalties_exploded
        
        # Get list of all authors
        all_authors = sorted(AuthorTrendCharts.get_all_authors(data))
        
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
