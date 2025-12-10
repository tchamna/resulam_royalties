"""
Author trends visualization for earnings over time
"""
import pandas as pd
import plotly.graph_objects as go
from typing import List, Optional

from ..config import VIZ_CONFIG, AUTHOR_NORMALIZATION, NET_REVENUE_PERCENTAGE


class AuthorTrendCharts:
    """Generate author earnings trend charts"""
    
    @staticmethod
    def normalize_author_name(name: str) -> str:
        """Normalize author name using the mapping"""
        return AUTHOR_NORMALIZATION.get(name, name)
    
    @staticmethod
    def earnings_trend_all_authors(df: pd.DataFrame) -> go.Figure:
        """Create bar chart showing earnings per year for all authors"""
        # Group by year and author, sum earnings
        df_copy = df.copy()
        df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
            lambda x: AuthorTrendCharts.normalize_author_name(x)
        )
        
        # Exclude Resulam
        df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
        
        # Calculate earnings per year per author
        yearly_earnings = df_copy.groupby(['Year Sold', 'Authors_Normalized'])['Royalty per Author (USD)'].sum().reset_index()
        yearly_earnings['Earnings USD'] = yearly_earnings['Royalty per Author (USD)'] * NET_REVENUE_PERCENTAGE
        
        # Create grouped bar chart
        fig = go.Figure()
        
        for author in sorted(yearly_earnings['Authors_Normalized'].unique()):
            author_data = yearly_earnings[yearly_earnings['Authors_Normalized'] == author].sort_values('Year Sold')
            fig.add_trace(go.Bar(
                x=author_data['Year Sold'],
                y=author_data['Earnings USD'],
                name=author,
                text=author_data['Earnings USD'],
                textposition='outside',
                texttemplate='$%{text:,.2f}',
                hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Earnings: $%{y:,.2f}<extra></extra>'
            ))
        
        fig.update_layout(
            title='Author Earnings by Year (All Authors)',
            xaxis_title='Year',
            yaxis_title='Earnings (USD)',
            barmode='group',
            hovermode='x unified',
            template=VIZ_CONFIG['template'],
            height=500,
            xaxis=dict(
                tickmode='linear',
                tick0=min(yearly_earnings['Year Sold']),
                dtick=1
            ),
            showlegend=True,
            legend=dict(
                x=1.02,
                y=1,
                xanchor='left',
                yanchor='top'
            )
        )
        
        return fig
    
    @staticmethod
    def earnings_trend_selected_authors(df: pd.DataFrame, selected_authors: Optional[List[str]] = None) -> go.Figure:
        """Create bar chart showing earnings per year for selected authors"""
        df_copy = df.copy()
        df_copy['Authors_Normalized'] = df_copy['Authors_Exploded'].apply(
            lambda x: AuthorTrendCharts.normalize_author_name(x)
        )
        
        # Exclude Resulam
        df_copy = df_copy[df_copy['Authors_Normalized'].str.lower() != 'resulam']
        
        # Calculate earnings per year per author
        yearly_earnings = df_copy.groupby(['Year Sold', 'Authors_Normalized'])['Royalty per Author (USD)'].sum().reset_index()
        yearly_earnings['Earnings USD'] = yearly_earnings['Royalty per Author (USD)'] * NET_REVENUE_PERCENTAGE
        
        # Filter by selected authors if provided
        if selected_authors and len(selected_authors) > 0:
            yearly_earnings = yearly_earnings[yearly_earnings['Authors_Normalized'].isin(selected_authors)]
        
        # Create grouped bar chart
        fig = go.Figure()
        
        for author in sorted(yearly_earnings['Authors_Normalized'].unique()):
            author_data = yearly_earnings[yearly_earnings['Authors_Normalized'] == author].sort_values('Year Sold')
            fig.add_trace(go.Bar(
                x=author_data['Year Sold'],
                y=author_data['Earnings USD'],
                name=author,
                text=author_data['Earnings USD'],
                textposition='outside',
                texttemplate='$%{text:,.2f}',
                hovertemplate='<b>%{fullData.name}</b><br>Year: %{x}<br>Earnings: $%{y:,.2f}<extra></extra>'
            ))
        
        fig.update_layout(
            title='Author Earnings by Year',
            xaxis_title='Year',
            yaxis_title='Earnings (USD)',
            barmode='group',
            hovermode='x unified',
            template=VIZ_CONFIG['template'],
            height=500,
            xaxis=dict(
                tickmode='linear',
                tick0=min(yearly_earnings['Year Sold']) if len(yearly_earnings) > 0 else 2015,
                dtick=1
            ),
            showlegend=True,
            legend=dict(
                x=1.02,
                y=1,
                xanchor='left',
                yanchor='top'
            )
        )
        
        return fig
    
    @staticmethod
    def get_all_authors(df: pd.DataFrame) -> List[str]:
        """Get list of all unique authors"""
        authors_normalized = df['Authors_Exploded'].apply(
            lambda x: AuthorTrendCharts.normalize_author_name(x)
        ).unique()
        
        # Exclude Resulam
        authors = [a for a in authors_normalized if a.lower() != 'resulam']
        return sorted(authors)
