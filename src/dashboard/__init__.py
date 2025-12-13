"""Dashboard module"""
from .app import ResulamDashboard, create_dashboard
from .public import PublicDashboard, create_dashboard as create_public_dashboard
from .multi_page import MultiPageDashboard, create_multi_page_dashboard

__all__ = ['ResulamDashboard', 'create_dashboard', 'PublicDashboard', 'create_public_dashboard', 'MultiPageDashboard', 'create_multi_page_dashboard']
