"""
Visualization components for Resulam Royalties Dashboard
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Optional

from ..config import VIZ_CONFIG, CURRENT_YEAR, AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE


class SalesCharts:
    """Generate sales-related charts"""
    
    @staticmethod
    def books_sold_per_year(df: pd.DataFrame, title: str = None) -> go.Figure:
        """Create bar chart of books sold per year"""
        # Group by year and sum net units sold
        units_by_year = df.groupby('Year Sold')['Net Units Sold'].sum().reset_index()
        units_by_year = units_by_year.sort_values(by='Net Units Sold', ascending=False)
        
        if title is None:
            title = f'Number of Books Sold by Resulam per Year (2015 to {CURRENT_YEAR - 1})'
        
        fig = px.bar(
            units_by_year,
            x='Year Sold',
            y='Net Units Sold',
            title=title,
            labels={'Year Sold': 'Year', 'Net Units Sold': 'Books Sold'},
            text='Net Units Sold',
            template=VIZ_CONFIG['template']
        )
        
        fig.update_traces(texttemplate='%{text}', textposition='outside', cliponaxis=False)
        fig.update_layout(
            height=400,
            uniformtext_minsize=8,
            uniformtext_mode='hide',
            xaxis=dict(automargin=True)
        )
        
        return fig
    
    @staticmethod
    def sales_by_language_stacked(
        df: pd.DataFrame,
        title: str = None,
        *,
        barmode: str = 'group',
        focus_language: Optional[str] = None,
        include_language_label: bool = True
    ) -> go.Figure:
        """Create interactive stacked/grouped bar chart by language"""
        # Filter out excluded languages
        df_filtered = df[~df['Language'].isin(VIZ_CONFIG['excluded_languages'])]
        
        if title is None:
            title = 'Books Sold by Language per Year (Grouped)'
        
        # Group by year and language, sorted by year
        units_by_year_lang = df_filtered.groupby(
            ['Year Sold', 'Language']
        )['Net Units Sold'].sum().reset_index()
        
        # Optionally focus on a single language if requested and data exists
        if focus_language:
            language_mask = units_by_year_lang['Language'] == focus_language
            if language_mask.any():
                units_by_year_lang = units_by_year_lang[language_mask]
            else:
                focus_language = None  # fallback to all languages if not present

        # Sort by year to ensure proper x-axis ordering
        units_by_year_lang = units_by_year_lang.sort_values('Year Sold')

        if units_by_year_lang.empty:
            fig = go.Figure()
            fig.add_annotation(text='No sales data available', xref='paper', yref='paper',
                               x=0.5, y=0.5, showarrow=False)
            fig.update_layout(
                plot_bgcolor='rgba(255,255,255,1)',
                paper_bgcolor='rgba(255,255,255,1)',
                title=title,
                template=VIZ_CONFIG['template'],
                height=420
            )
            return fig

        # Identify the tallest bar to control its label separately
        tallest_idx = units_by_year_lang['Net Units Sold'].idxmax()
        tallest_point = units_by_year_lang.loc[tallest_idx]
        tallest_language = tallest_point['Language']
        tallest_year = str(tallest_point['Year Sold'])

        def _format_value(val):
            if pd.isna(val):
                return ""
            if isinstance(val, (int, float)):
                if float(val).is_integer():
                    return str(int(val))
                return f"{val:.2f}"
            return str(val)

        def _format_labels(values, language_name):
            formatted_values = [_format_value(val) for val in values]
            if include_language_label:
                return [f"{value}<br>{language_name}" if value else language_name for value in formatted_values]
            return formatted_values

        # Get sorted years
        sorted_years = sorted(units_by_year_lang['Year Sold'].unique())
        # Convert years to strings for proper axis ordering
        sorted_years_str = [str(year) for year in sorted_years]
        
        # Sort languages by total sales (descending) for better visualization
        language_totals = units_by_year_lang.groupby('Language')['Net Units Sold'].sum().sort_values(ascending=False)
        sorted_languages = language_totals.index.tolist()

        if focus_language:
            sorted_languages = [lang for lang in sorted_languages if lang == focus_language]
        
        # Create figure
        fig = go.Figure()
        color_sequence = list(getattr(getattr(fig.layout.template, 'layout', None), 'colorway', []) or px.colors.qualitative.Plotly)
        
        # Add trace for each language (in descending order by total sales)
        for idx, language in enumerate(sorted_languages):
            filtered_data = units_by_year_lang[units_by_year_lang['Language'] == language].sort_values('Year Sold')
            # Convert years to strings for consistency
            filtered_data = filtered_data.copy()
            filtered_data['Year Sold'] = filtered_data['Year Sold'].astype(str)
            bar_color = color_sequence[idx % len(color_sequence)]
            hovertemplate = '<b>%{fullData.name}</b><br>Year: %{x}<br>Units: %{y}<extra></extra>'

            if language == tallest_language:
                tallest_mask = filtered_data['Year Sold'] == tallest_year
                regular_data = filtered_data[~tallest_mask]
                tallest_data = filtered_data[tallest_mask]

                if not regular_data.empty:
                    regular_values = regular_data['Net Units Sold'].tolist()
                    fig.add_trace(go.Bar(
                        x=regular_data['Year Sold'],
                        y=regular_data['Net Units Sold'],
                        name=language,
                        text=_format_labels(regular_values, language),
                        textposition='outside',
                        textangle=-35,
                        cliponaxis=False,
                        hovertemplate=hovertemplate,
                        marker=dict(color=bar_color),
                        legendgroup=language,
                        offsetgroup=language
                    ))

                if not tallest_data.empty:
                    tallest_values = tallest_data['Net Units Sold'].tolist()
                    fig.add_trace(go.Bar(
                        x=tallest_data['Year Sold'],
                        y=tallest_data['Net Units Sold'],
                        name=language,
                        text=_format_labels(tallest_values, language),
                        textposition='outside',
                        textangle=0,
                        cliponaxis=False,
                        hovertemplate=hovertemplate,
                        marker=dict(color=bar_color),
                        legendgroup=language,
                        offsetgroup=language,
                        showlegend=regular_data.empty
                    ))
            else:
                filtered_values = filtered_data['Net Units Sold'].tolist()
                fig.add_trace(go.Bar(
                    x=filtered_data['Year Sold'],
                    y=filtered_data['Net Units Sold'],
                    name=language,
                    text=_format_labels(filtered_values, language),
                    textposition='outside',
                    textangle=-35,
                    cliponaxis=False,
                    hovertemplate=hovertemplate,
                    marker=dict(color=bar_color),
                    legendgroup=language,
                    offsetgroup=language
                ))
        
        # Update layout with proper x-axis ordering
        fig.update_layout(
            plot_bgcolor='rgba(255,255,255,1)',
            paper_bgcolor='rgba(255,255,255,1)',
            title=title if title else 'Books Sold by Language per Year (Grouped)',
            xaxis_title='Year',
            yaxis_title='Net Units Sold',
            barmode='stack' if barmode == 'stack' else 'group',
            template=VIZ_CONFIG['template'],
            xaxis=dict(
                categoryorder='array',
                categoryarray=sorted_years_str
            ),
            margin=dict(t=140, b=120, l=80, r=40)
        )
        
        return fig
    
    @staticmethod
    def sales_by_book_horizontal(df: pd.DataFrame, field: str = 'book_nick_name') -> go.Figure:
        """Create horizontal bar chart of sales by book"""
        # Handle empty data or missing columns
        if len(df) == 0 or field not in df.columns or 'Net Units Sold' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for the selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(
                title=f'Total Books Sold by {field.replace("_", " ").title()}',
                template=VIZ_CONFIG['template'],
                height=400
            )
            return fig
        
        # Group and sort
        units_by_book = df.groupby(field)['Net Units Sold'].sum().reset_index()
        units_by_book = units_by_book.sort_values(by='Net Units Sold', ascending=True)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=units_by_book[field],
            x=units_by_book['Net Units Sold'],
            orientation='h',
            text=units_by_book['Net Units Sold'],
            textposition='outside',
            cliponaxis=False
        ))
        
        fig.update_layout(
            title=f'Total Books Sold by {field.replace("_", " ").title()}',
            yaxis_title=field.replace("_", " ").title(),
            xaxis_title='Net Units Sold',
            height=max(500, len(units_by_book) * 25),  # Dynamic height based on items
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True)
        )
        
        return fig
    
    @staticmethod
    def sales_by_book_with_year_filter(df: pd.DataFrame) -> go.Figure:
        """Create horizontal bar chart with year dropdown filter"""
        # Handle empty data
        if len(df) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for the selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(
                title='Books Sold by Title',
                template=VIZ_CONFIG['template'],
                height=400
            )
            return fig
        
        sorted_years = sorted(df['Year Sold'].unique())
        
        fig = go.Figure()
        
        # Add trace for each year
        for year in sorted_years:
            df_year = df[df['Year Sold'] == year]
            units_by_book = df_year.groupby('book_nick_name')['Net Units Sold'].sum().reset_index()
            units_by_book = units_by_book.sort_values(by='Net Units Sold', ascending=True)
            
            fig.add_trace(go.Bar(
                y=units_by_book['book_nick_name'],
                x=units_by_book['Net Units Sold'],
                orientation='h',
                name=str(year),
                text=units_by_book['Net Units Sold'],
                textposition='outside',
                visible=(year == sorted_years[-1]),  # Show most recent year by default
                cliponaxis=False
            ))
        
        # Create dropdown buttons
        dropdown_buttons = []
        for i, year in enumerate(sorted_years):
            visibility = [False] * len(sorted_years)
            visibility[i] = True
            dropdown_buttons.append({
                'label': str(year),
                'method': 'update',
                'args': [
                    {'visible': visibility},
                    {'title': f'Books Sold by Title in {year}'}
                ]
            })
        
        # Add "Show All" option
        dropdown_buttons.append({
            'label': 'All Years',
            'method': 'update',
            'args': [
                {'visible': [True] * len(sorted_years)},
                {'title': 'Books Sold by Title (All Years)'}
            ]
        })
        
        fig.update_layout(
            updatemenus=[{
                'buttons': dropdown_buttons,
                'direction': 'down',
                'x': 0.5,
                'xanchor': 'center',
                'y': 1.15,
                'yanchor': 'top'
            }],
            title=f'Books Sold by Title in {sorted_years[-1]}',
            yaxis_title='Book',
            xaxis_title='Net Units Sold',
            height=500,
            showlegend=False,
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
        )
        
        return fig

    @staticmethod
    def ebook_vs_physical_pie(df: pd.DataFrame) -> go.Figure:
        """Create pie chart comparing eBook vs Physical book sales"""
        if len(df) == 0 or 'BookType' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(title='eBook vs Physical Sales', template=VIZ_CONFIG['template'], height=350)
            return fig
        
        # Group by BookType
        sales_by_type = df.groupby('BookType')['Net Units Sold'].sum().reset_index()
        # Create a simpler category: eBook vs Physical (Paper + HardCover)
        sales_by_type['Category'] = sales_by_type['BookType'].apply(
            lambda x: '📱 eBook' if x == 'Ebook' else '📖 Physical' if x in ['Paper', 'HardCover'] else 'Unknown'
        )
        category_sales = sales_by_type.groupby('Category')['Net Units Sold'].sum().reset_index()
        category_sales = category_sales[category_sales['Category'] != 'Unknown']
        
        colors = {'📱 eBook': '#3498db', '📖 Physical': '#e74c3c'}
        
        fig = go.Figure(data=[go.Pie(
            labels=category_sales['Category'],
            values=category_sales['Net Units Sold'],
            hole=0.4,
            marker_colors=[colors.get(c, '#95a5a6') for c in category_sales['Category']],
            textinfo='label+percent',
            textposition='outside'
        )])
        
        fig.update_layout(
            title='📊 eBook vs Physical Sales',
            template=VIZ_CONFIG['template'],
            height=350,
            showlegend=False
        )
        
        return fig

    @staticmethod
    def ebook_vs_physical_by_year(df: pd.DataFrame) -> go.Figure:
        """Create stacked bar chart of eBook vs Physical sales by year"""
        if len(df) == 0 or 'BookType' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(title='Sales by Format Over Time', template=VIZ_CONFIG['template'], height=350)
            return fig
        
        # Map to simpler categories
        df = df.copy()
        df['Category'] = df['BookType'].apply(
            lambda x: 'eBook' if x == 'Ebook' else 'Physical' if x in ['Paper', 'HardCover'] else None
        )
        df = df[df['Category'].notna()]
        
        # Group by year and category
        sales_by_year_type = df.groupby(['Year Sold', 'Category'])['Net Units Sold'].sum().reset_index()
        
        fig = go.Figure()
        
        colors = {'eBook': '#3498db', 'Physical': '#e74c3c'}
        
        for category in ['eBook', 'Physical']:
            cat_data = sales_by_year_type[sales_by_year_type['Category'] == category]
            fig.add_trace(go.Bar(
                x=cat_data['Year Sold'],
                y=cat_data['Net Units Sold'],
                name=f'📱 {category}' if category == 'eBook' else f'📖 {category}',
                marker_color=colors[category],
                text=cat_data['Net Units Sold'],
                textposition='auto'
            ))
        
        fig.update_layout(
            title='📈 eBook vs Physical Sales by Year',
            xaxis_title='Year',
            yaxis_title='Units Sold',
            barmode='group',
            template=VIZ_CONFIG['template'],
            height=350,
            legend=dict(orientation='h', yanchor='bottom', y=1.02, xanchor='center', x=0.5)
        )
        
        return fig

    @staticmethod
    def ebook_vs_physical_revenue(df: pd.DataFrame) -> go.Figure:
        """Create bar chart comparing revenue from eBook vs Physical"""
        if len(df) == 0 or 'BookType' not in df.columns:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(title='Revenue by Format', template=VIZ_CONFIG['template'], height=350)
            return fig
        
        # Map to simpler categories
        df = df.copy()
        df['Category'] = df['BookType'].apply(
            lambda x: '📱 eBook' if x == 'Ebook' else '📖 Physical' if x in ['Paper', 'HardCover'] else None
        )
        df = df[df['Category'].notna()]
        
        # Group by category
        revenue_by_type = df.groupby('Category')['Royalty USD'].sum().reset_index()
        revenue_by_type = revenue_by_type.sort_values('Royalty USD', ascending=True)
        
        colors = {'📱 eBook': '#3498db', '📖 Physical': '#e74c3c'}
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=revenue_by_type['Category'],
            x=revenue_by_type['Royalty USD'],
            orientation='h',
            text=revenue_by_type['Royalty USD'].apply(lambda x: f'${x:,.2f}'),
            textposition='auto',
            textfont=dict(color='white', size=14),
            marker_color=[colors.get(c, '#95a5a6') for c in revenue_by_type['Category']]
        ))
        
        max_val = revenue_by_type['Royalty USD'].max()
        fig.update_layout(
            title='💰 Revenue by Format',
            xaxis_title='Revenue (USD)',
            xaxis=dict(range=[0, max_val * 1.15]),  # Add 15% margin for labels
            yaxis_title='',
            template=VIZ_CONFIG['template'],
            height=350
        )
        
        return fig


class AuthorCharts:
    """Generate author-related charts"""
    
    @staticmethod
    def royalties_by_author(df_exploded: pd.DataFrame, top_n: Optional[int] = None) -> go.Figure:
        """Create bar chart of royalties by author"""
        # Handle empty data
        if len(df_exploded) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for the selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(
                title='Royalties by Author',
                template=VIZ_CONFIG['template'],
                height=400
            )
            return fig
            
        # Group by author
        author_royalties = df_exploded.groupby('Authors_Exploded').agg({
            'Units Sold': 'sum',
            'Royalty per Author (USD)': 'sum'
        }).reset_index()
        
        author_royalties = author_royalties.sort_values(
            by='Royalty per Author (USD)',
            ascending=True
        )
        
        if top_n:
            author_royalties = author_royalties.tail(top_n)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=author_royalties['Authors_Exploded'],
            x=author_royalties['Royalty per Author (USD)'],
            orientation='h',
            text=author_royalties['Royalty per Author (USD)'].round(2),
            textposition='outside',
            marker_color='lightblue',
            cliponaxis=False
        ))
        
        fig.update_layout(
            title=f'Royalties by Author{"" if not top_n else f" (Top {top_n})"}',
            yaxis_title='Author',
            xaxis_title='Total Royalties (USD)',
            height=max(400, min(600, len(author_royalties) * 25)),
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
        )
        
        return fig
    
    @staticmethod
    def books_sold_by_author(df_exploded: pd.DataFrame, top_n: Optional[int] = None) -> go.Figure:
        """Create bar chart of books sold by author"""
        # Handle empty data
        if len(df_exploded) == 0:
            fig = go.Figure()
            fig.add_annotation(
                text="No data available for the selected filters",
                xref="paper", yref="paper",
                x=0.5, y=0.5, showarrow=False,
                font=dict(size=16, color="#888")
            )
            fig.update_layout(
                title='Books Sold by Author',
                template=VIZ_CONFIG['template'],
                height=400
            )
            return fig
        
        # Group by author
        author_sales = df_exploded.groupby('Authors_Exploded').agg({
            'Net Units Sold': 'sum'
        }).reset_index()
        
        author_sales = author_sales.sort_values(by='Net Units Sold', ascending=True)
        
        if top_n:
            author_sales = author_sales.tail(top_n)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            y=author_sales['Authors_Exploded'],
            x=author_sales['Net Units Sold'],
            orientation='h',
            text=author_sales['Net Units Sold'],
            textposition='outside',
            marker_color='lightgreen',
            cliponaxis=False
        ))
        
        fig.update_layout(
            title=f'Books Sold by Author{"" if not top_n else f" (Top {top_n})"}',
            yaxis_title='Author',
            xaxis_title='Total Books Sold',
            height=max(400, min(600, len(author_sales) * 25)),
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
        )
        
        return fig


class GeographicCharts:
    """Generate geographic/marketplace charts"""
    
    @staticmethod
    def sales_by_marketplace(df: pd.DataFrame) -> go.Figure:
        """Create pie chart of sales by marketplace"""
        marketplace_sales = df.groupby('Marketplace')['Net Units Sold'].sum().reset_index()
        marketplace_sales = marketplace_sales.sort_values(by='Net Units Sold', ascending=False)
        
        fig = px.pie(
            marketplace_sales,
            values='Net Units Sold',
            names='Marketplace',
            title='Sales Distribution by Marketplace',
            template=VIZ_CONFIG['template']
        )
        
        fig.update_traces(
            textposition='auto',
            textinfo='percent+label',
            textfont=dict(size=11),
            hovertemplate='<b>%{label}</b><br>Units: %{value}<br>Percentage: %{percent}<extra></extra>'
        )
        
        fig.update_layout(
            height=500,
            showlegend=True,
            legend=dict(x=0.02, y=0.98)
        )
        
        return fig
    
    @staticmethod
    def revenue_by_marketplace(df: pd.DataFrame) -> go.Figure:
        """Create bar chart of revenue by marketplace (net revenue = NET_REVENUE_PERCENTAGE of royalty)"""
        marketplace_revenue = df.groupby('Marketplace')['Royalty USD'].sum().reset_index()
        # Calculate net revenue (NET_REVENUE_PERCENTAGE of total royalty)
        marketplace_revenue['Net Revenue'] = marketplace_revenue['Royalty USD'] * NET_REVENUE_PERCENTAGE
        marketplace_revenue = marketplace_revenue.sort_values(by='Net Revenue', ascending=False)
        
        fig = go.Figure()
        fig.add_trace(go.Bar(
            x=marketplace_revenue['Marketplace'],
            y=marketplace_revenue['Net Revenue'],
            text=[f"${val:.2f}" for val in marketplace_revenue['Net Revenue']],
            textposition='outside',
            textfont=dict(size=10),
            hovertemplate=f'<b>%{{x}}</b><br>Net Revenue ({NET_REVENUE_PERCENTAGE:.0%}): $%{{y:.2f}}<extra></extra>',
            cliponaxis=False,
            marker_color='rgba(50, 150, 200, 0.7)'
        ))
        
        fig.update_layout(
            title=f'Net Revenue by Marketplace (USD) - {NET_REVENUE_PERCENTAGE:.0%} of Total',
            xaxis_title='Marketplace',
            yaxis_title='Net Revenue (USD)',
            height=450,
            xaxis=dict(
                tickangle=-45,
                automargin=True,
                tickfont=dict(size=10)
            ),
            yaxis=dict(automargin=True),
            template=VIZ_CONFIG['template'],
            margin=dict(b=100)
        )
        
        return fig


class SummaryMetrics:
    """Calculate summary metrics"""
    
    @staticmethod
    def normalize_author_name(name: str) -> str:
        """Normalize author name using the AUTHOR_NORMALIZATION mapping"""
        if name in AUTHOR_NORMALIZATION:
            return AUTHOR_NORMALIZATION[name]
        return name
    
    @staticmethod
    def calculate_metrics(df: pd.DataFrame, df_exploded: pd.DataFrame = None) -> dict:
        """Calculate key metrics from royalties data
        
        Args:
            df: Non-exploded royalties dataframe
            df_exploded: Exploded royalties dataframe (optional, for accurate author count)
        """
        # Handle empty data or missing columns
        required_cols = ['Net Units Sold', 'Royalty USD', 'Royalty per Author (USD)', 'Title', 'Year Sold']
        if len(df) == 0 or not all(col in df.columns for col in required_cols):
            return {
                'total_books_sold': 0,
                'total_revenue_usd': 0.0,
                'net_revenue_usd': 0.0,
                'total_royalties_shared': 0.0,
                'resulam_share': 0.0,
                'unique_titles': 0,
                'unique_authors': 0,
                'avg_price_per_book': 0.0,
                'years_active': 0
            }
        
        total_books_sold = df['Net Units Sold'].sum()
        total_revenue_usd = df['Royalty USD'].sum()
        # Deduct 20% for transaction fees and taxes
        net_revenue_usd = total_revenue_usd * NET_REVENUE_PERCENTAGE
        
        # Total Royalties Shared: Sum of per-author royalties
        # Each transaction's royalty is divided by author count,
        # so summing gives the actual total shared with authors
        total_royalties_shared = df['Royalty per Author (USD)'].sum()
        # Resulam gets the remainder
        resulam_share = total_revenue_usd - total_royalties_shared
        
        unique_titles = df['Title'].nunique()
        
        # Count unique authors after normalization
        # Use exploded data if available, otherwise use author combinations
        if df_exploded is not None and len(df_exploded) > 0:
            # Use individual authors from exploded data and normalize
            normalized_authors = set()
            for author in df_exploded['Authors_Exploded'].unique():
                normalized_authors.add(SummaryMetrics.normalize_author_name(author))
            unique_authors = len(normalized_authors)
        elif len(df) > 0:
            # Fallback: use author combinations
            normalized_authors = set()
            for author_combo in df['Authors'].unique():
                normalized_authors.add(SummaryMetrics.normalize_author_name(author_combo))
            unique_authors = len(normalized_authors)
        else:
            unique_authors = 0
        
        avg_price_per_book = total_revenue_usd / total_books_sold if total_books_sold > 0 else 0
        
        # Handle empty dataframe case for years_active
        if len(df) > 0:
            years_active = df['Year Sold'].max() - df['Year Sold'].min() + 1
        else:
            years_active = 0
        
        return {
            'total_books_sold': int(total_books_sold),
            'total_revenue_usd': round(total_revenue_usd, 2),
            'net_revenue_usd': round(net_revenue_usd, 2),
            'total_royalties_shared': round(total_royalties_shared, 2),
            'resulam_share': round(resulam_share, 2),
            'unique_titles': int(unique_titles),
            'unique_authors': int(unique_authors),
            'avg_price_per_book': round(avg_price_per_book, 2),
            'years_active': int(years_active)
        }
