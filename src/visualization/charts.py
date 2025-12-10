"""
Visualization components for Resulam Royalties Dashboard
"""
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from typing import List, Optional

from ..config import VIZ_CONFIG, CURRENT_YEAR, AUTHOR_NORMALIZATION


class SalesCharts:
    """Generate sales-related charts"""
    
    @staticmethod
    def books_sold_per_year(df: pd.DataFrame) -> go.Figure:
        """Create bar chart of books sold per year"""
        # Group by year and sum net units sold
        units_by_year = df.groupby('Year Sold')['Net Units Sold'].sum().reset_index()
        units_by_year = units_by_year.sort_values(by='Net Units Sold', ascending=False)
        
        fig = px.bar(
            units_by_year,
            x='Year Sold',
            y='Net Units Sold',
            title=f'Number of Books Sold by Resulam per Year (2015 to {CURRENT_YEAR - 1})',
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
    def sales_by_language_stacked(df: pd.DataFrame) -> go.Figure:
        """Create interactive stacked/grouped bar chart by language"""
        # Filter out excluded languages
        df_filtered = df[~df['Language'].isin(VIZ_CONFIG['excluded_languages'])]
        
        # Group by year and language
        units_by_year_lang = df_filtered.groupby(
            ['Year Sold', 'Language']
        )['Net Units Sold'].sum().reset_index()
        
        # Get sorted languages
        sorted_languages = sorted(units_by_year_lang['Language'].unique())
        
        # Create figure
        fig = go.Figure()
        
        # Add trace for each language
        for language in sorted_languages:
            filtered_data = units_by_year_lang[units_by_year_lang['Language'] == language]
            fig.add_trace(go.Bar(
                x=filtered_data['Year Sold'],
                y=filtered_data['Net Units Sold'],
                name=language,
                text=filtered_data['Net Units Sold'],
                textposition='inside'
            ))
        
        # Create dropdown buttons
        dropdown_buttons = [
            {
                'label': 'All (Stacked)',
                'method': 'update',
                'args': [
                    {'visible': [True] * len(sorted_languages)},
                    {'barmode': 'stack', 'title': 'Books Sold by Language per Year (Stacked)'}
                ]
            },
            {
                'label': 'All (Grouped)',
                'method': 'update',
                'args': [
                    {'visible': [True] * len(sorted_languages)},
                    {'barmode': 'group', 'title': 'Books Sold by Language per Year (Grouped)'}
                ]
            }
        ]
        
        # Add individual language buttons
        for i, language in enumerate(sorted_languages):
            visibility = [False] * len(sorted_languages)
            visibility[i] = True
            dropdown_buttons.append({
                'label': language,
                'method': 'update',
                'args': [
                    {'visible': visibility},
                    {'barmode': 'group', 'title': f'Books Sold in {language}'}
                ]
            })
        
        # Update layout
        fig.update_layout(
            plot_bgcolor='rgba(255,255,255,1)',
            paper_bgcolor='rgba(255,255,255,1)',
            updatemenus=[{
                'buttons': dropdown_buttons,
                'direction': 'down',
                'showactive': True,
                'x': 0.9,
                'xanchor': 'right',
                'y': 1.15,
                'yanchor': 'top'
            }],
            title='Books Sold by Language per Year',
            xaxis_title='Year',
            yaxis_title='Net Units Sold',
            barmode='stack',
            template=VIZ_CONFIG['template']
        )
        
        return fig
    
    @staticmethod
    def sales_by_book_horizontal(df: pd.DataFrame, field: str = 'book_nick_name') -> go.Figure:
        """Create horizontal bar chart of sales by book"""
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
            height=min(700, max(300, len(units_by_book) * 15)),
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True)
        )
        
        return fig
    
    @staticmethod
    def sales_by_book_with_year_filter(df: pd.DataFrame) -> go.Figure:
        """Create horizontal bar chart with year dropdown filter"""
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


class AuthorCharts:
    """Generate author-related charts"""
    
    @staticmethod
    def royalties_by_author(df_exploded: pd.DataFrame, top_n: Optional[int] = None) -> go.Figure:
        """Create bar chart of royalties by author"""
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
            height=min(600, len(author_royalties) * 25),
            template=VIZ_CONFIG['template'],
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
        )
        
        return fig
    
    @staticmethod
    def books_sold_by_author(df_exploded: pd.DataFrame, top_n: Optional[int] = None) -> go.Figure:
        """Create bar chart of books sold by author"""
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
            height=min(600, len(author_sales) * 25),
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
        
        fig.update_traces(textposition='inside', textinfo='percent+label')
        
        return fig
    
    @staticmethod
    def revenue_by_marketplace(df: pd.DataFrame) -> go.Figure:
        """Create bar chart of revenue by marketplace"""
        marketplace_revenue = df.groupby('Marketplace')['Royalty USD'].sum().reset_index()
        marketplace_revenue = marketplace_revenue.sort_values(by='Royalty USD', ascending=False)
        
        fig = px.bar(
            marketplace_revenue,
            x='Marketplace',
            y='Royalty USD',
            title='Revenue by Marketplace (USD)',
            text='Royalty USD',
            template=VIZ_CONFIG['template']
        )
        
        fig.update_traces(texttemplate='$%{text:.2f}', textposition='outside', cliponaxis=False)
        fig.update_layout(
            xaxis_tickangle=-45,
            xaxis=dict(automargin=True),
            yaxis=dict(automargin=True)
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
        total_books_sold = df['Net Units Sold'].sum()
        total_revenue_usd = df['Royalty USD'].sum()
        # Deduct 20% for transaction fees and taxes
        net_revenue_usd = total_revenue_usd * 0.8
        
        # Total Royalties Shared: Sum of per-author royalties
        # Each transaction's royalty is divided by author count,
        # so summing gives the actual total shared with authors
        total_royalties_shared = df['Royalty per Author (USD)'].sum()
        # Resulam gets the remainder
        resulam_share = total_revenue_usd - total_royalties_shared
        
        unique_titles = df['Title'].nunique()
        
        # Count unique authors after normalization
        # Use exploded data if available, otherwise use author combinations
        if df_exploded is not None:
            # Use individual authors from exploded data and normalize
            normalized_authors = set()
            for author in df_exploded['Authors_Exploded'].unique():
                normalized_authors.add(SummaryMetrics.normalize_author_name(author))
            unique_authors = len(normalized_authors)
        else:
            # Fallback: use author combinations
            normalized_authors = set()
            for author_combo in df['Authors'].unique():
                normalized_authors.add(SummaryMetrics.normalize_author_name(author_combo))
            unique_authors = len(normalized_authors)
        
        avg_price_per_book = total_revenue_usd / total_books_sold if total_books_sold > 0 else 0
        
        years_active = df['Year Sold'].max() - df['Year Sold'].min() + 1
        
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
