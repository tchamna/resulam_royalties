"""
Modern Dash Dashboard Application
"""
import dash
import os
import re
from urllib.parse import parse_qs, urlencode, quote

from dash import html, dcc, Input, Output, State, ClientsideFunction
import dash_bootstrap_components as dbc
from typing import Dict, List
from pathlib import Path
import pandas as pd
import math
import unicodedata
import plotly.graph_objects as go
import requests

from ..config import (
    DASHBOARD_CONFIG,
    CURRENT_YEAR,
    LAST_YEAR,
    AUTHOR_NORMALIZATION,
    NET_REVENUE_PERCENTAGE,
    BOOKS_DATABASE_PATH,
    RESOURCES_DATABASE_PATH,
    UNIVERSAL_LANGUAGE_VALUES,
    LANGUAGE_FILTERED_RESOURCE_CATEGORIES,
    LANGUAGE_RESOURCE_NAME_ALIASES,
)
from ..visualization import SalesCharts, AuthorCharts, GeographicCharts, SummaryMetrics
from ..visualization.earning_history import EarningHistoryCharts
from ..utils.chatbot import ChatbotEngine
from ..utils.chatbot_llm import LLMChatbotEngine


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


_UNIVERSAL_LANGUAGE_LOOKUP = {value.casefold() for value in UNIVERSAL_LANGUAGE_VALUES}


def _normalize_language_value(language) -> str:
    if language is None or (isinstance(language, float) and pd.isna(language)):
        return ""
    return str(language).strip()


def is_universal_language(language) -> bool:
    """Return True when a language value is universal (e.g. Polyglot, All)."""
    normalized = _normalize_language_value(language).casefold()
    return bool(normalized) and normalized in _UNIVERSAL_LANGUAGE_LOOKUP


def matches_language_filter(language, selected_language: str) -> bool:
    """Return True when a row/item language matches the selected language filter."""
    if not selected_language or selected_language == "all":
        return True

    row_language = _normalize_language_value(language)
    if not row_language:
        return False
    selected_normalized = _normalize_language_value(selected_language)
    if row_language.casefold() == selected_normalized.casefold():
        return True

    selected_is_universal = selected_normalized.casefold() in _UNIVERSAL_LANGUAGE_LOOKUP
    return not selected_is_universal and is_universal_language(row_language)


def filter_by_language(
    df: pd.DataFrame,
    selected_language: str,
    column: str = "Language",
) -> pd.DataFrame:
    """Filter a dataframe by language, keeping universal languages for any specific filter."""
    if not selected_language or selected_language == "all":
        return df
    return df[df[column].apply(lambda value: matches_language_filter(value, selected_language))]


def _resource_name_matches_language_aliases(item: dict, selected_language: str) -> bool:
    """Match resource items by configured name patterns when language metadata is missing."""
    aliases = LANGUAGE_RESOURCE_NAME_ALIASES.get(selected_language)
    if not aliases:
        return False

    searchable = " ".join(
        str(item.get(field, "") or "")
        for field in ("name", "description", "category")
    ).casefold()
    return any(alias.casefold() in searchable for alias in aliases)


def matches_resource_item_filter(
    item: dict,
    selected_language: str,
    selected_category: str = None,
) -> bool:
    """Return True when a resource matches the selected language and category."""
    return matches_resource_filters(
        item,
        selected_language=selected_language,
        selected_category=selected_category,
    )


def _resource_values(value) -> list:
    """Normalize scalar or multi-valued resource metadata into trimmed values."""
    if value is None:
        return []
    if isinstance(value, (list, tuple, set, frozenset)):
        return [str(part).strip() for part in value if str(part).strip()]
    text = str(value).strip()
    if not text:
        return []
    separator = ";" if ";" in text else ("|" if "|" in text else None)
    return [part.strip() for part in text.split(separator) if part.strip()] if separator else [text]


def _same_filter_value(left, right) -> bool:
    return str(left or "").strip().casefold() == str(right or "").strip().casefold()


def _active_filter(value) -> bool:
    return value is not None and str(value).strip().casefold() not in {"", "all", "lifetime"}


def resource_year_filter(selected_year):
    """Translate the visible year selection without treating Lifetime as all explicit years."""
    return [selected_year] if isinstance(selected_year, int) else None


def matches_resource_filters(
    item: dict,
    selected_years=None,
    selected_language=None,
    selected_author=None,
    selected_booktype=None,
    selected_book=None,
    selected_category=None,
    ignore=frozenset(),
) -> bool:
    """Apply shared dashboard filters to one resource with AND semantics."""
    if "category" not in ignore and _active_filter(selected_category):
        if not _same_filter_value(item.get("category"), selected_category):
            return False

    if "language" not in ignore and _active_filter(selected_language):
        languages = _resource_values(item.get("languages") or item.get("language"))
        if not any(matches_language_filter(language, selected_language) for language in languages):
            if not _resource_name_matches_language_aliases(item, selected_language):
                return False

    if "author" not in ignore and _active_filter(selected_author):
        selected_normalized = normalize_author_name(str(selected_author).strip()).casefold()
        authors = {
            normalize_author_name(author).casefold()
            for author in _resource_values(item.get("authors"))
        }
        if selected_normalized not in authors:
            return False

    if "booktype" not in ignore and _active_filter(selected_booktype):
        if not any(
            _same_filter_value(value, selected_booktype)
            for value in _resource_values(item.get("book_types"))
        ):
            return False

    if "book" not in ignore and _active_filter(selected_book):
        if not any(
            _same_filter_value(value, selected_book)
            for value in _resource_values(item.get("books"))
        ):
            return False

    if "year" not in ignore and selected_years and selected_years != "lifetime":
        wanted_years = selected_years if isinstance(selected_years, (list, tuple, set)) else [selected_years]
        publication_date = pd.to_datetime(item.get("publication_date"), errors="coerce")
        if pd.isna(publication_date) or publication_date.year not in {int(year) for year in wanted_years}:
            return False

    return True


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


DEFAULT_DASHBOARD_TAB = "purchase"
DEFAULT_CHART_DISPLAY = "all_stacked"
VALID_DASHBOARD_TABS = frozenset(
    {"purchase", "resources", "chatbot", "sales", "books", "geography"}
)


def _first_query_value(params: dict, key: str):
    """Return the first value for a query parameter key, or None."""
    values = params.get(key)
    if not values:
        return None
    return values[0]


def _normalize_url_search(search) -> str:
    """Normalize a URL search string for comparison (empty or leading '?')."""
    if not search:
        return ""
    return search if str(search).startswith("?") else f"?{search}"


def _resolve_query_choice(raw_value, choices, normalize=None):
    """Return the canonical choice matching a decoded query value."""
    if raw_value is None:
        return None
    normalizer = normalize or (lambda value: str(value).strip().casefold())
    wanted = normalizer(raw_value)
    return next((choice for choice in choices if normalizer(choice) == wanted), None)


def build_filter_search_string(
    year,
    lang,
    category,
    book,
    author,
    booktype,
    tab,
    chart,
) -> str:
    """Build a bookmarkable query string from dashboard filter state."""
    params = {}
    if year and year != "lifetime":
        params["year"] = str(year)
    if lang and lang != "all":
        params["lang"] = lang
    if category and category != "all":
        params["category"] = category
    if book and book != "all":
        params["book"] = book
    if author and author != "all":
        params["author"] = author
    if booktype and booktype != "all":
        params["type"] = booktype
    if tab and tab != DEFAULT_DASHBOARD_TAB:
        params["tab"] = tab
    if chart and chart != DEFAULT_CHART_DISPLAY:
        params["chart"] = chart
    if not params:
        return ""
    return "?" + urlencode(params, quote_via=quote)


def parse_filter_search_string(search, ctx: dict) -> dict:
    """Parse and validate URL query params into dashboard filter values."""
    params = parse_qs(_normalize_url_search(search).lstrip("?"), keep_blank_values=False)

    year = "lifetime"
    raw_year = _first_query_value(params, "year")
    if raw_year:
        if raw_year == "lifetime":
            year = "lifetime"
        else:
            try:
                year_int = int(raw_year)
                if year_int in ctx["years"]:
                    year = year_int
            except (TypeError, ValueError):
                pass

    lang = "all"
    raw_lang = _first_query_value(params, "lang")
    matched_lang = _resolve_query_choice(raw_lang, ctx["languages"])
    if matched_lang:
        lang = matched_lang

    category = "all"
    raw_category = _first_query_value(params, "category")
    matched_category = _resolve_query_choice(raw_category, ctx["categories"])
    if matched_category:
        category = matched_category

    book = "all"
    raw_book = _first_query_value(params, "book")
    matched_book = _resolve_query_choice(raw_book, ctx["books"])
    if matched_book:
        book = matched_book

    author = "all"
    raw_author = _first_query_value(params, "author")
    matched_author = _resolve_query_choice(
        raw_author,
        ctx["authors"],
        lambda value: normalize_author_name(str(value).strip()).casefold(),
    )
    if matched_author:
        author = matched_author

    booktype = "all"
    raw_type = _first_query_value(params, "type")
    matched_type = _resolve_query_choice(raw_type, ctx["book_types"])
    if matched_type:
        booktype = matched_type

    tab = DEFAULT_DASHBOARD_TAB
    raw_tab = _first_query_value(params, "tab")
    matched_tab = _resolve_query_choice(raw_tab, ctx["tabs"])
    if matched_tab:
        tab = matched_tab

    chart = DEFAULT_CHART_DISPLAY
    raw_chart = _first_query_value(params, "chart")
    matched_chart = _resolve_query_choice(raw_chart, ctx["chart_modes"])
    if matched_chart:
        chart = matched_chart

    return {
        "year": year,
        "lang": lang,
        "category": category,
        "book": book,
        "author": author,
        "booktype": booktype,
        "tab": tab,
        "chart": chart,
    }


def get_category_royalty_nicknames(category: str) -> set[str]:
    """Return the royalty nicknames represented by a books-database category.

    The catalogue and royalty reports do not always use the same nickname.  Keep
    that translation in one place so cards, charts, tabs, and faceted dropdowns
    cannot disagree about what a category contains.
    """
    if not category or category == "all":
        return set()

    try:
        books_df = pd.read_csv(BOOKS_DATABASE_PATH)
        category_books = books_df[books_df["category"] == category]
        from src.hardcoded_nicknames import HARDCODED_TITLE_NICKNAMES, DB_NICKNAME_TO_ROYALTY
    except Exception:
        return set()

    nicknames = set()
    for db_nickname in category_books["book_nick_name"].dropna():
        nicknames.update(DB_NICKNAME_TO_ROYALTY.get(db_nickname, [db_nickname]))

    # Some older database rows only line up with the royalty report by title.
    # Include those aliases for every consumer of the category filter.
    for title in category_books.get("title", pd.Series(dtype=str)).dropna():
        title = str(title).strip()
        if not title:
            continue
        title_prefix = title.split(":", 1)[0].strip().casefold()
        for hardcoded_title, nickname in HARDCODED_TITLE_NICKNAMES.items():
            hardcoded_prefix = hardcoded_title.split(":", 1)[0].strip().casefold()
            if title.casefold() in hardcoded_title.casefold() or hardcoded_title.casefold() in title.casefold() or title_prefix == hardcoded_prefix:
                nicknames.add(nickname)
                break

    return nicknames


class PublicDashboard:
    """Public dashboard application class - customized for external audiences"""
    
    def __init__(self, data: Dict[str, pd.DataFrame], server=None, prefix: str = "/"):
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

        # When mounting multiple Dash apps on the same Flask server, give the assets
        # a unique URL path per prefix to avoid blueprint name collisions.
        assets_url_path = "/assets"
        if server is not None and prefix != "/":
            assets_url_path = f"{prefix.rstrip('/')}/assets"

        dash_name = "public_dashboard"
        self.app = dash.Dash(
            dash_name,
            server=(True if server is None else server),
            requests_pathname_prefix=prefix,
            external_stylesheets=[dbc.themes.DARKLY, dbc.icons.FONT_AWESOME],
            suppress_callback_exceptions=True,
            assets_folder=str(assets_path),
            assets_url_path=assets_url_path,
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
        
        # Link-preview metadata (WhatsApp, etc.) works best with absolute URLs.
        canonical_base_url = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")
        if not canonical_base_url:
            canonical_base_url = "https://africanlanguagelibrary.tchamna.com"

        assets_prefix = f"{prefix.rstrip('/')}/assets"
        favicon_png_path = f"{assets_prefix}/resulam_logo_egg.png"
        favicon_ico_path = f"{assets_prefix}/favicon.ico"
        og_image_url = f"{canonical_base_url}{favicon_png_path}"
        og_url = f"{canonical_base_url}{prefix}"

        # Add custom CSS for theme switching
        self.app.index_string = '''
        <!DOCTYPE html>
        <html>
            <head>
                {%metas%}
                <title>{%title%}</title>
                <link rel="icon" href="__FAVICON_ICO__" />
                <link rel="icon" type="image/png" href="__FAVICON_PNG__" />
                <link rel="apple-touch-icon" href="__FAVICON_PNG__" />
                {%css%}
                <meta property="og:title" content="African Languages Books - Resulam" />
                <meta property="og:site_name" content="Resulam" />
                <meta property="og:type" content="website" />
                <meta property="og:description" content="African Languages Library by Resulam: explore books, sales trends, and geographic distribution." />
                <meta property="og:url" content="__OG_URL__" />
                <meta property="og:image" content="__OG_IMAGE__" />
                <meta property="og:image:secure_url" content="__OG_IMAGE__" />
                <meta property="og:image:alt" content="Resulam" />
                <meta name="twitter:title" content="African Languages Books - Resulam" />
                <meta name="twitter:card" content="summary" />
                <meta name="twitter:image" content="__OG_IMAGE__" />
                <style>
                    body.light-mode {
                        /* Bootstrap variable overrides for DARKLY -> light look */
                        --bs-body-bg: #f8f9fa;
                        --bs-body-color: #212529;
                        --bs-emphasis-color: #212529;
                        --bs-secondary-color: #6c757d;
                        --bs-tertiary-color: #6c757d;
                        --bs-border-color: #dee2e6;
                        --bs-card-bg: #ffffff;
                        --bs-card-color: #212529;
                        --bs-link-color: #0d6efd;
                        --bs-link-hover-color: #0a58ca;
                        --bs-nav-link-color: #212529;
                        --bs-nav-link-hover-color: #0a58ca;

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

                    body.light-mode a,
                    body.light-mode a:visited {
                        color: #0d6efd !important;
                    }

                    body.light-mode .nav-tabs {
                        border-bottom-color: #dee2e6 !important;
                    }
                    body.light-mode .nav-tabs .nav-link {
                        color: #212529 !important;
                    }
                    body.light-mode .nav-tabs .nav-link.active {
                        color: #212529 !important;
                        background-color: #ffffff !important;
                        border-color: #dee2e6 #dee2e6 #ffffff !important;
                    }

                    body.light-mode .table {
                        --bs-table-bg: #ffffff;
                        --bs-table-color: #212529;
                        --bs-table-border-color: #dee2e6;
                        --bs-table-striped-bg: rgba(0, 0, 0, 0.03);
                        --bs-table-striped-color: #212529;
                        --bs-table-hover-bg: rgba(0, 0, 0, 0.06);
                        --bs-table-hover-color: #212529;
                    }

                    body.light-mode .modal-content {
                        background-color: #ffffff !important;
                        color: #212529 !important;
                    }
                    body.light-mode .modal-header,
                    body.light-mode .modal-footer {
                        border-color: #dee2e6 !important;
                    }

                    body.light-mode .toast,
                    body.light-mode .toast-header {
                        background-color: #ffffff !important;
                        color: #212529 !important;
                        border-color: #dee2e6 !important;
                    }
                    body.light-mode .toast-header {
                        background-color: #f8f9fa !important;
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

                    /* Category dropdown: keep selected value compact; make menu readable for long labels */
                    #category-filter .Select-control {
                        min-height: 38px !important;
                    }
                    #category-filter .Select-value-label {
                        white-space: nowrap !important;
                        overflow: hidden !important;
                        text-overflow: ellipsis !important;
                        display: block !important;
                    }

                    /* Dash dcc.Dropdown uses a virtualized menu; allow the menu to grow and/or scroll horizontally */
                    #category-filter .Select-menu-outer {
                        width: max-content !important;
                        min-width: 100% !important;
                        max-width: 90vw !important;
                        overflow-x: auto !important;
                    }
                    #category-filter .Select-menu {
                        width: max-content !important;
                        min-width: 100% !important;
                    }
                    #category-filter .VirtualizedSelectOption,
                    #category-filter .Select-option {
                        white-space: nowrap !important;
                        overflow: visible !important;
                        text-overflow: clip !important;
                    }

                    /* Header hero */
                    #header-container {
                        position: relative;
                        overflow: hidden;
                        border-radius: 18px;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        background: linear-gradient(135deg, #0b1220, #111827);
                    }
                    #header-container::before {
                        content: "";
                        position: absolute;
                        inset: -2px;
                        pointer-events: none;
                        background:
                            radial-gradient(600px circle at 20% 35%, rgba(0, 221, 255, 0.16), transparent 55%),
                            radial-gradient(520px circle at 85% 30%, rgba(255, 221, 0, 0.10), transparent 60%),
                            radial-gradient(700px circle at 60% 110%, rgba(99, 102, 241, 0.14), transparent 60%);
                        opacity: 0.95;
                        /* Keep the glow inside the frame so the border pattern stays crisp on all sides. */
                        clip-path: inset(14px round 18px);
                    }
                    #header-container::after {
                        content: "";
                        position: absolute;
                        inset: 0;
                        pointer-events: none;
                        border-radius: 18px;
                        /* Frame thickness: make the top edge thicker so the pattern reads clearly. */
                        padding: 24px 14px 14px 14px;
                        background-image: url("assets/border_pattern.svg");
                        background-repeat: repeat;
                        background-size: 220px 140px;
                        opacity: 0.34;
                        filter: contrast(1.18) brightness(1.06);
                        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
                        -webkit-mask-composite: xor;
                        mask-composite: exclude;
                    }
                    #header-container > * {
                        position: relative;
                    }
                    #header-container h1 {
                        font-weight: 800;
                        letter-spacing: -0.02em;
                    }
                    #header-container p {
                        font-size: 1.05rem;
                    }
                    .header-social-links .btn {
                        border-radius: 999px;
                        padding: 0.45rem 0.85rem;
                        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.25);
                        transition: transform 120ms ease, box-shadow 120ms ease;
                    }
                    .header-social-links .btn:hover {
                        transform: translateY(-1px);
                        box-shadow: 0 14px 30px rgba(0, 0, 0, 0.32);
                    }

                    /* Theme toggle button: pin top-right and match hero style */
                    #theme-toggle-btn {
                        position: static;
                        z-index: 2;
                        width: 44px;
                        height: 44px;
                        padding: 0 !important;
                        border-radius: 999px;
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        background: transparent !important;
                        border: none !important;
                        color: #f8fafc !important;
                        box-shadow: none !important;
                        transition: transform 120ms ease, box-shadow 120ms ease, background-color 120ms ease, border-color 120ms ease;
                    }
                    #theme-toggle-btn:hover {
                        transform: translateY(-1px);
                        background: rgba(255, 255, 255, 0.08) !important;
                        border: 1px solid rgba(255, 255, 255, 0.22) !important;
                        box-shadow: 0 12px 26px rgba(0, 0, 0, 0.32) !important;
                    }
                    #theme-toggle-btn:focus {
                        /* Avoid persistent focus ring after clicking (mouse users). */
                        box-shadow: none !important;
                        outline: none !important;
                        border: none !important;
                        background: transparent !important;
                    }
                    #theme-toggle-btn:focus-visible {
                        /* Keep an accessible focus indicator for keyboard users. */
                        box-shadow: 0 0 0 0.25rem rgba(0, 221, 255, 0.22) !important;
                    }
                    #theme-icon {
                        font-size: 1.35rem;
                        line-height: 1;
                    }
                    @media (max-width: 768px) {
                        #theme-toggle-btn {
                            width: 40px;
                            height: 40px;
                        }
                        #theme-icon {
                            font-size: 1.2rem;
                        }
                    }

                    body.light-mode #header-container {
                        border-color: #dee2e6 !important;
                        background: linear-gradient(135deg, #ffffff, #f8f9fa) !important;
                    }
                    body.light-mode #header-container::before {
                        opacity: 0.35;
                    }
                    body.light-mode #header-container::after {
                        opacity: 0.18;
                        filter: invert(1) brightness(0.55);
                    }
                    body.light-mode .header-social-links .btn {
                        box-shadow: 0 10px 18px rgba(0, 0, 0, 0.10);
                    }
                    body.light-mode .header-social-links .btn:hover {
                        box-shadow: 0 14px 22px rgba(0, 0, 0, 0.14);
                    }

                    /* Light-mode contact buttons: higher contrast + brand outline */
                    body.light-mode #theme-toggle-btn {
                        color: #212529 !important;
                        box-shadow: none !important;
                    }
                    body.light-mode #theme-toggle-btn:hover {
                        background: rgba(33, 37, 41, 0.06) !important;
                        border: 1px solid rgba(33, 37, 41, 0.18) !important;
                        box-shadow: 0 10px 18px rgba(0, 0, 0, 0.10) !important;
                    }
                    body.light-mode #theme-toggle-btn:focus {
                        box-shadow: none !important;
                        outline: none !important;
                        border: none !important;
                        background: transparent !important;
                    }
                    body.light-mode #theme-toggle-btn:focus-visible {
                        box-shadow: 0 0 0 0.25rem rgba(0, 221, 255, 0.22) !important;
                    }

                    .header-logo-row {
                        display: inline-flex;
                        align-items: center;
                        justify-content: center;
                        gap: 12px;
                    }
                    @media (max-width: 768px) {
                        .header-logo-row {
                            gap: 10px;
                        }
                    }

                    body.light-mode .header-social-links .contact-btn {
                        background-color: #ffffff !important;
                        border: 1px solid #ced4da !important;
                        color: #212529 !important;
                        font-weight: 600;
                    }
                    body.light-mode .header-social-links .contact-btn:hover {
                        color: #ffffff !important;
                    }

                    body.light-mode .header-social-links .contact-web {
                        border-color: #0d6efd !important;
                        color: #0d6efd !important;
                    }
                    body.light-mode .header-social-links .contact-web:hover {
                        background-color: #0d6efd !important;
                    }

                    body.light-mode .header-social-links .contact-youtube,
                    body.light-mode .header-social-links .contact-youtube-nufi {
                        border-color: #dc3545 !important;
                        color: #dc3545 !important;
                    }
                    body.light-mode .header-social-links .contact-youtube:hover,
                    body.light-mode .header-social-links .contact-youtube-nufi:hover {
                        background-color: #dc3545 !important;
                    }

                    body.light-mode .header-social-links .contact-facebook {
                        border-color: #0d6efd !important;
                        color: #0d6efd !important;
                    }
                    body.light-mode .header-social-links .contact-facebook:hover {
                        background-color: #0d6efd !important;
                    }

                    body.light-mode .header-social-links .contact-linkedin {
                        border-color: #0a66c2 !important;
                        color: #0a66c2 !important;
                    }
                    body.light-mode .header-social-links .contact-linkedin:hover {
                        background-color: #0a66c2 !important;
                    }

                    /* KPI metric cards */
                    .metric-card {
                        position: relative;
                        overflow: hidden;
                        border-radius: 16px;
                        border: 1px solid rgba(255, 255, 255, 0.08);
                        background: linear-gradient(180deg, rgba(255, 255, 255, 0.06), rgba(255, 255, 255, 0.02));
                        transition: transform 120ms ease, box-shadow 120ms ease, border-color 120ms ease;
                    }
                    .metric-card::before {
                        content: "";
                        position: absolute;
                        inset: 0;
                        pointer-events: none;
                        border-radius: 16px;
                        padding: 10px;
                        background-image: url("assets/border_pattern.svg");
                        background-repeat: repeat;
                        background-size: 220px 140px;
                        opacity: 0.14;
                        -webkit-mask: linear-gradient(#000 0 0) content-box, linear-gradient(#000 0 0);
                        -webkit-mask-composite: xor;
                        mask-composite: exclude;
                    }
                    .metric-card::after {
                        content: "";
                        position: absolute;
                        inset: 0;
                        pointer-events: none;
                        opacity: 0.9;
                    }
                    .metric-card.metric-books::after {
                        background: radial-gradient(180px circle at 18% 22%, rgba(0, 221, 255, 0.20), transparent 60%);
                    }
                    .metric-card.metric-titles::after {
                        background: radial-gradient(180px circle at 18% 22%, rgba(173, 181, 189, 0.22), transparent 60%);
                    }
                    .metric-card.metric-authors::after {
                        background: radial-gradient(180px circle at 18% 22%, rgba(255, 221, 0, 0.20), transparent 60%);
                    }
                    .metric-card:hover {
                        transform: translateY(-2px);
                        border-color: rgba(255, 255, 255, 0.14);
                        box-shadow: 0 18px 38px rgba(0, 0, 0, 0.35);
                    }
                    .metric-card .card-body {
                        position: relative;
                        z-index: 1;
                    }
                    .metric-card .card-body > div:nth-child(1) {
                        width: 44px !important;
                        height: 44px !important;
                        border-radius: 999px !important;
                        display: inline-flex !important;
                        align-items: center !important;
                        justify-content: center !important;
                        margin-bottom: 0.35rem !important;
                        background: rgba(255, 255, 255, 0.07) !important;
                        border: 1px solid rgba(255, 255, 255, 0.10) !important;
                        box-shadow: 0 10px 24px rgba(0, 0, 0, 0.22) !important;
                    }
                    .metric-title {
                        font-weight: 600;
                        letter-spacing: 0.02em;
                        text-transform: uppercase;
                        opacity: 0.88;
                    }
                    .metric-value {
                        letter-spacing: -0.02em;
                        font-weight: 800;
                    }

                    body.light-mode .metric-card {
                        border-color: #dee2e6 !important;
                        background: #ffffff !important;
                    }
                    body.light-mode .metric-card::before {
                        opacity: 0.18;
                        filter: invert(1) brightness(0.55);
                    }
                    body.light-mode .metric-card:hover {
                        box-shadow: 0 16px 28px rgba(0, 0, 0, 0.14);
                    }
                    body.light-mode .metric-card .card-body > div:nth-child(1) {
                        background: rgba(13, 110, 253, 0.07) !important;
                        border-color: rgba(13, 110, 253, 0.14) !important;
                        box-shadow: 0 10px 18px rgba(0, 0, 0, 0.10) !important;
                    }
                    body.light-mode .metric-title {
                        color: #495057 !important;
                        opacity: 1;
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

        self.app.index_string = (
            self.app.index_string
            .replace("__FAVICON_ICO__", favicon_ico_path)
            .replace("__FAVICON_PNG__", favicon_png_path)
            .replace("__OG_IMAGE__", og_image_url)
            .replace("__OG_URL__", og_url)
        )
        
        # Set page title for public site (fallback, multi-page router overrides per path)
        self.app.title = "African Languages Books - Resulam"
        
        # Calculate metrics
        self.metrics = SummaryMetrics.calculate_metrics(self.royalties)
        
        # Get available years for filtering
        self.available_years = sorted(self.royalties['Year Sold'].unique().tolist())

        # Cache for book cover lookup (local or S3)
        self._available_covers = None
        self._available_covers_source = None

        # Chatbot engine (optional, falls back to keyword search on failure)
        self.chatbot_engine_rules = None
        self.chatbot_engine_llm = None
        self.chatbot_init_error = None
        self.chatbot_llm_error = None
        try:
            self.chatbot_engine_rules = ChatbotEngine.from_csv(
                BOOKS_DATABASE_PATH,
                royalties_df=self.royalties,
            )
        except Exception as e:
            self.chatbot_init_error = str(e)
            print(f"Warning: Chatbot disabled: {e}")

        try:
            self.chatbot_engine_llm = LLMChatbotEngine.from_csv(
                BOOKS_DATABASE_PATH,
                royalties_df=self.royalties,
            )
        except Exception as e:
            self.chatbot_llm_error = str(e)
            print(f"Warning: LLM chatbot disabled: {e}")
        
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
                            style={"height": "80px"}
                        ),
                        dbc.Button(
                            html.I(className="fas fa-sun", id="theme-icon"),
                            id="theme-toggle-btn",
                            color="light",
                            outline=True,
                            size="lg",
                            title="Toggle light/dark mode",
                        )
                    ], className="header-logo-row mb-2")
                ], width="auto", className="mx-auto")
            ], className="justify-content-center mb-2"),
            dbc.Row([
                dbc.Col([
                    html.H1(
                        "African Languages Library - By Resulam",
                        className="text-center text-light mb-4"
                    ),
                    html.P(
                        f"Book Sales Analysis: 2015 - {CURRENT_YEAR}",
                        className="text-center text-muted mb-4"
                    )
                ], width=12),
            ]),
            dbc.Row([
                dbc.Col(
                    html.Div(
                        [
                            dbc.Button(
                                [html.I(className="fas fa-globe me-2"), "www.resulam.com"],
                                href="https://www.resulam.com",
                                target="_blank",
                                rel="noopener noreferrer",
                                color="light",
                                size="sm",
                                className="contact-btn contact-web",
                            ),
                            dbc.Button(
                                [html.I(className="fab fa-youtube me-2"), "YouTube Resulam"],
                                href="https://www.youtube.com/@Resulam",
                                target="_blank",
                                rel="noopener noreferrer",
                                color="danger",
                                size="sm",
                                className="contact-btn contact-youtube",
                            ),
                            dbc.Button(
                                [html.I(className="fab fa-youtube me-2"), "YouTube Nufi"],
                                href="https://www.youtube.com/@nufifeefeelanguage-resulam722",
                                target="_blank",
                                rel="noopener noreferrer",
                                color="danger",
                                size="sm",
                                className="contact-btn contact-youtube-nufi",
                            ),
                            dbc.Button(
                                [html.I(className="fab fa-facebook me-2"), "Facebook"],
                                href="https://www.facebook.com/resulam",
                                target="_blank",
                                rel="noopener noreferrer",
                                color="primary",
                                size="sm",
                                className="contact-btn contact-facebook",
                            ),
                            dbc.Button(
                                [html.I(className="fab fa-linkedin me-2"), "LinkedIn"],
                                href="https://www.linkedin.com/company/67290371/admin/dashboard/",
                                target="_blank",
                                rel="noopener noreferrer",
                                color="info",
                                size="sm",
                                className="contact-btn contact-linkedin",
                            ),
                        ],
                        className="header-social-links d-flex flex-wrap justify-content-center gap-2 mb-2",
                    ),
                    width=12,
                )
            ]),
            dbc.Alert(
                "💻 For the best experience, please use a laptop or desktop computer.",
                id="device-warning-banner",
                is_open=True,
                color="info",
                className="d-md-none text-center mx-auto mt-2 mb-0",
                style={
                    "maxWidth": "720px",
                    "color": "#ffc107",
                    "backgroundColor": "rgba(0, 0, 0, 0.35)",
                    "border": "1px solid #ffc107",
                },
            ),
            dcc.Interval(
                id="device-warning-timer",
                interval=5 * 1000,
                n_intervals=0,
                max_intervals=1,
            ),
            dcc.Store(id="theme-store", data="dark"),
            dcc.Store(id="theme-apply-signal", data=0),
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
        resource_items = self._load_resource_items(purchase_only=False)
        all_languages = sorted(set(all_languages).union(
            language
            for item in resource_items
            for language in _resource_values(item.get("languages") or item.get("language"))
            if not is_universal_language(language)
        ))
        all_categories = sorted(set(all_categories).union(
            item["category"] for item in resource_items if item.get("category")
        ))
        all_authors_for_filter = sorted(set(all_authors_for_filter).union(
            author for item in resource_items for author in _resource_values(item.get("authors"))
        ))
        all_book_types = sorted(set(all_book_types).union(
            value for item in resource_items for value in _resource_values(item.get("book_types"))
        ))
        all_book_nicknames = sorted(set(all_book_nicknames).union(
            value for item in resource_items for value in _resource_values(item.get("books"))
        ))

        category_label_overrides = {
            "Phrasebook - Guide de Conversations": "Phrasebooks-Guide de conversation",
        }
        
        filter_section = dbc.Container([
            # Filter order: Year, Languages, Category, Books, Authors, Type
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
                    dbc.Label(id="category-label", className="fw-bold text-light mb-1", style={"fontSize": "0.85rem"}),
                    dcc.Dropdown(
                        id="category-filter",
                        options=[{"label": f"All Categories ({len(all_categories)})", "value": "all"}] + [
                            {"label": category_label_overrides.get(cat, cat), "value": cat} for cat in all_categories
                        ],
                        value="all",
                        multi=False,
                        searchable=True,
                        clearable=False,
                        style={"width": "100%"},
                        placeholder="Select..."
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
            "minWidth": "220px",
            "height": "100%"
        }
        metric_card_body_style = {
            "display": "flex",
            "flexDirection": "column",
            "justifyContent": "center",
            "alignItems": "center",
            "padding": "0.75rem 0.25rem"
        }
        metric_title_style = {"fontWeight": "600", "fontSize": "0.85rem", "marginBottom": "0.25rem", "whiteSpace": "nowrap"}
        metric_value_style_base = {"fontWeight": "700", "fontSize": "2.5rem", "marginBottom": "0", "whiteSpace": "nowrap"}
        
        metrics_row = dbc.Row([
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("📖", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Total Books Sold", className="text-center metric-title", style=metric_title_style),
                        html.Div(id="metric-books-sold", className="text-center metric-value", style={**metric_value_style_base, "color": "#00DDFF"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm metric-card metric-books", style=metric_card_style)
            ], width=True, className="mb-2 px-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("📚", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Unique Titles", className="text-center metric-title", style=metric_title_style),
                        html.Div(id="metric-titles", className="text-center metric-value", style={**metric_value_style_base, "color": "#888888"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm metric-card metric-titles", style=metric_card_style)
            ], width=True, className="mb-2 px-1"),
            dbc.Col([
                dbc.Card([
                    dbc.CardBody([
                        html.Div("🧑🏿‍💼", className="text-center", style={"fontSize": "1.5rem"}),
                        html.Div("Authors", className="text-center metric-title", style=metric_title_style),
                        html.Div(id="metric-authors", className="text-center metric-value", style={**metric_value_style_base, "color": "#FFDD00"})
                    ], style=metric_card_body_style)
                ], className="shadow-sm metric-card metric-authors", style=metric_card_style)
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
                    dbc.Col(html.H5("🌐 Sales by Language", id="sales-by-language-title", className="mb-0"), md=8, xs=12),
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

        # KPI cards (shown on Purchase + Sales tabs)
        kpi_section = html.Div(metrics_row, id="kpi-section")

        # Sales overview charts (shown only on Sales tab)
        sales_overview_section = html.Div([
            sales_trend_section,
            sales_by_language_section
        ], id="sales-overview-section")
        
        # Tabs for different views - PUBLIC VERSION (removed Authors Analysis and Earning History)
        tabs = dbc.Tabs([
            dbc.Tab(label="🛒 African Languages Books", tab_id="purchase"),
            dbc.Tab(label="🎧 Other Resources", tab_id="resources"),
            dbc.Tab(label="Book Chatbot", tab_id="chatbot"),
            dbc.Tab(label="📊 Sales Overview", tab_id="sales"),
            dbc.Tab(label="📖 Books Analysis", tab_id="books"),
            dbc.Tab(label="🌍 Geographic Distribution", tab_id="geography"),
        ], id="dashboard-tabs", active_tab="purchase", className="mb-4")

        # Anchor + signal used for smooth-scroll on small screens when tabs change
        view_anchor = html.Div(id="tab-view-anchor")
        tab_scroll_signal = dcc.Store(id="tab-scroll-signal", data=0)
        filter_scroll_signal = dcc.Store(id="filter-scroll-signal", data=0)
        
        # Content area that changes based on selected tab
        content = html.Div(id="tab-content", className="mb-4")
        
        # Main layout
        self.app.layout = dbc.Container([
            dcc.Location(id="url", refresh=False),
            dcc.Store(id="url-sync-flag", data=None),
            header,
            filter_section,
            tabs,
            view_anchor,
            tab_scroll_signal,
            filter_scroll_signal,
            kpi_section,
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

            # Chatbot stores
            dcc.Store(id="chat-history-store", storage_type="session"),
            dcc.Store(id="chat-session-store", storage_type="session", data={"filters": {}}),
            
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

            # Presence / online users
            dcc.Store(id="client-id-store", storage_type="local"),
            dcc.Interval(id="presence-heartbeat", interval=20 * 1000, n_intervals=0),
            
            # Footer
            html.Hr(),
            html.Footer([
                html.P(id="online-users-summary", className="text-center text-muted small mb-1"),
                html.P(id="online-users-countries", className="text-center text-muted small mb-2"),
                html.P(
                    "© 2025 Resulam Books. Dashboard built with Dash & Plotly.",
                    className="text-center text-muted"
                )
            ], className="mt-4 mb-4")
        ], fluid=True)

    def _get_url_filter_context(self) -> dict:
        """Build validation sets for URL filter parsing."""
        all_languages = sort_with_accents([
            lang for lang in self.royalties['Language'].unique().tolist()
            if lang not in ['African Names', 'Bamileke']
        ])
        all_authors = get_unique_authors(self.royalties_exploded['Authors_Exploded'])
        all_book_types = sorted(self.royalties['BookType'].dropna().unique().tolist())
        all_book_nicknames = sorted(self.royalties['book_nick_name'].dropna().unique().tolist())
        try:
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
            all_categories = sorted(books_df['category'].dropna().unique().tolist())
        except Exception:
            all_categories = []
        resource_items = self._load_resource_items(purchase_only=False)
        all_languages = sorted(set(all_languages).union(
            language
            for item in resource_items
            for language in _resource_values(item.get("languages") or item.get("language"))
            if not is_universal_language(language)
        ))
        all_categories = sorted(set(all_categories).union(
            item["category"] for item in resource_items if item.get("category")
        ))
        all_authors = sorted(set(all_authors).union(
            author for item in resource_items for author in _resource_values(item.get("authors"))
        ))
        all_book_types = sorted(set(all_book_types).union(
            value for item in resource_items for value in _resource_values(item.get("book_types"))
        ))
        all_book_nicknames = sorted(set(all_book_nicknames).union(
            value for item in resource_items for value in _resource_values(item.get("books"))
        ))

        chart_modes = {"all_stacked", "all_grouped"}
        chart_modes.update(f"language::{lang}" for lang in all_languages)

        return {
            "years": set(self.available_years),
            "languages": set(all_languages),
            "categories": set(all_categories),
            "books": set(all_book_nicknames),
            "authors": set(all_authors),
            "book_types": set(all_book_types) | {"all"},
            "tabs": VALID_DASHBOARD_TABS,
            "chart_modes": chart_modes,
        }
    
    def _register_url_callbacks(self):
        """Sync dashboard filters/tabs with URL query params for shareable views."""

        @self.app.callback(
            Output("year-filter", "value"),
            Output("language-filter", "value"),
            Output("author-filter", "value"),
            Output("booktype-filter", "value"),
            Output("book-filter", "value"),
            Output("category-filter", "value"),
            Output("dashboard-tabs", "active_tab"),
            Output("sales-language-display-mode", "value"),
            Output("url", "search"),
            Output("url-sync-flag", "data"),
            Input("reset-all-filters", "n_clicks"),
            prevent_initial_call=True,
        )
        def reset_all_filters(n_clicks):
            """Reset all filters to their default values and clear the URL."""
            return (
                "lifetime", "all", "all", "all", "all", "all",
                DEFAULT_DASHBOARD_TAB, DEFAULT_CHART_DISPLAY,
                "", "from_filters",
            )

        @self.app.callback(
            Output("year-filter", "value", allow_duplicate=True),
            Output("language-filter", "value", allow_duplicate=True),
            Output("author-filter", "value", allow_duplicate=True),
            Output("booktype-filter", "value", allow_duplicate=True),
            Output("book-filter", "value", allow_duplicate=True),
            Output("category-filter", "value", allow_duplicate=True),
            Output("dashboard-tabs", "active_tab", allow_duplicate=True),
            Output("sales-language-display-mode", "value", allow_duplicate=True),
            Output("url-sync-flag", "data", allow_duplicate=True),
            Input("url", "search"),
            State("year-filter", "value"),
            State("language-filter", "value"),
            State("author-filter", "value"),
            State("booktype-filter", "value"),
            State("book-filter", "value"),
            State("category-filter", "value"),
            State("dashboard-tabs", "active_tab"),
            State("sales-language-display-mode", "value"),
            State("url-sync-flag", "data"),
            prevent_initial_call="initial_duplicate",
        )
        def apply_url_to_filters(
            search,
            year,
            lang,
            author,
            booktype,
            book,
            category,
            tab,
            chart,
            sync_flag,
        ):
            """Apply bookmarked URL query params to dashboard filters."""
            if sync_flag == "from_filters":
                return (
                    dash.no_update, dash.no_update, dash.no_update, dash.no_update,
                    dash.no_update, dash.no_update, dash.no_update, dash.no_update,
                    None,
                )

            parsed = parse_filter_search_string(search, self._get_url_filter_context())
            return (
                parsed["year"] if parsed["year"] != year else dash.no_update,
                parsed["lang"] if parsed["lang"] != lang else dash.no_update,
                parsed["author"] if parsed["author"] != author else dash.no_update,
                parsed["booktype"] if parsed["booktype"] != booktype else dash.no_update,
                parsed["book"] if parsed["book"] != book else dash.no_update,
                parsed["category"] if parsed["category"] != category else dash.no_update,
                parsed["tab"] if parsed["tab"] != tab else dash.no_update,
                parsed["chart"] if parsed["chart"] != chart else dash.no_update,
                None,
            )

        self.app.clientside_callback(
            ClientsideFunction(namespace="url_sync", function_name="filters_to_search"),
            Output("url", "search", allow_duplicate=True),
            Input("year-filter", "value"),
            Input("language-filter", "value"),
            Input("category-filter", "value"),
            Input("book-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("dashboard-tabs", "active_tab"),
            Input("sales-language-display-mode", "value"),
            State("url", "search"),
            prevent_initial_call=True,
        )

    def _register_callbacks(self):
        """Register all dashboard callbacks"""
        self._register_url_callbacks()

        @self.app.callback(
            Output("device-warning-banner", "is_open"),
            Input("device-warning-timer", "n_intervals"),
            prevent_initial_call=False,
        )
        def _hide_device_warning(n_intervals):
            return not bool(n_intervals)

        @self.app.callback(
            Output("theme-store", "data"),
            Output("theme-icon", "className"),
            Output("header-container", "className"),
            Input("theme-toggle-btn", "n_clicks"),
            State("theme-store", "data"),
            prevent_initial_call=True,
        )
        def toggle_theme(_n_clicks, current_theme):
            """Toggle between light and dark mode."""
            current_theme = current_theme or "dark"
            new_theme = "light" if current_theme == "dark" else "dark"
            icon_class = "fas fa-sun" if new_theme == "dark" else "fas fa-moon"
            header_class = "bg-light py-4 mb-4" if new_theme == "light" else "bg-dark py-4 mb-4"
            return new_theme, icon_class, header_class

        self.app.clientside_callback(
            """
            function(theme) {
                try {
                    if (theme === 'light') {
                        document.body.classList.add('light-mode');
                    } else {
                        document.body.classList.remove('light-mode');
                    }
                } catch (e) {}
                return Date.now();
            }
            """,
            Output("theme-apply-signal", "data"),
            Input("theme-store", "data"),
            prevent_initial_call=False,
        )

        # Client-side: ensure a stable per-browser user id (stored locally).
        self.app.clientside_callback(
            """
            function(n, existing) {
                var key = 'resulam_client_id';
                try {
                    if (existing) {
                        try { window.localStorage.setItem(key, existing); } catch (e) {}
                        return existing;
                    }
                    var saved = null;
                    try { saved = window.localStorage.getItem(key); } catch (e) {}
                    if (saved) { return saved; }
                    var id = null;
                    try { id = crypto.randomUUID(); } catch(e) {}
                    if (!id) { id = 'cid-' + Math.random().toString(16).slice(2) + '-' + Date.now(); }
                    try { window.localStorage.setItem(key, id); } catch (e) {}
                    return id;
                } catch (e) {
                    return existing || ('cid-' + Math.random().toString(16).slice(2) + '-' + Date.now());
                }
            }
            """,
            Output("client-id-store", "data"),
            Input("presence-heartbeat", "n_intervals"),
            State("client-id-store", "data"),
            prevent_initial_call=False,
        )

        # Server-side: update presence + footer summary.
        @self.app.callback(
            Output("online-users-summary", "children"),
            Output("online-users-countries", "children"),
            Input("presence-heartbeat", "n_intervals"),
            Input("client-id-store", "data"),
            prevent_initial_call=False,
        )
        def update_online_users(_n, client_id):
            from flask import request
            from src.dashboard.presence import active_summary, get_client_ip, get_country, touch

            if not client_id:
                return dash.no_update, dash.no_update

            ip = get_client_ip(request.headers, request.remote_addr)
            country = get_country(request.headers, request.remote_addr)
            touch(client_id, ip, country)

            count, countries = active_summary()
            top = countries.most_common(5)
            top_total = sum(n for _c, n in top)
            others = max(0, sum(countries.values()) - top_total)

            countries_parts = [f"{c} ({n})" for c, n in top if c]
            if others:
                countries_parts.append(f"Other ({others})")

            summary = f"👥 Online now: {count} • You: {country}"
            countries_line = "🌍 Countries: " + (", ".join(countries_parts) if countries_parts else "—")
            return summary, countries_line

        # Smooth-scroll to the content when switching tabs on small screens
        self.app.clientside_callback(
            """
            function(activeTab) {
                try {
                    if (!window.matchMedia('(max-width: 768px)').matches) {
                        return window.dash_clientside.no_update;
                    }
                    var el = document.getElementById('tab-view-anchor');
                    if (el) {
                        el.scrollIntoView({behavior: 'smooth', block: 'start'});
                    }
                } catch (e) {}
                return Date.now();
            }
            """,
            Output("tab-scroll-signal", "data"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=True,
        )

        # Smooth-scroll to the content when changing filters on small screens
        self.app.clientside_callback(
            """
            function(year, language, author, bookType, book, category) {
                try {
                    var el = document.getElementById('tab-view-anchor');
                    if (el) {
                        var rect = el.getBoundingClientRect();
                        var anchorTop = rect.top + (window.pageYOffset || document.documentElement.scrollTop || 0);
                        var y = window.pageYOffset || document.documentElement.scrollTop || 0;
                        // Only scroll down when the user is above the content area.
                        if (y + 10 < anchorTop) {
                            el.scrollIntoView({behavior: 'smooth', block: 'start'});
                        } else {
                            return window.dash_clientside.no_update;
                        }
                    }
                } catch (e) {}
                return Date.now();
            }
            """,
            Output("filter-scroll-signal", "data"),
            Input("year-filter", "value"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            prevent_initial_call=True,
        )
        
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
                category_nicknames = get_category_royalty_nicknames(selected_category)
                # An empty mapping must produce no sales, never silently show all sales.
                df = df[df['book_nick_name'].isin(category_nicknames)]
                df_exploded = df_exploded[df_exploded['book_nick_name'].isin(category_nicknames)]
            
            if selected_language and selected_language != "all":
                df = filter_by_language(df, selected_language)
                df_exploded = filter_by_language(df_exploded, selected_language)
            
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
            Input("dashboard-tabs", "active_tab"),
            State("language-filter", "value"),
            prevent_initial_call=False
        )
        def update_language_options(selected_year, selected_category, selected_author, selected_booktype, selected_book, refresh_signal, active_tab, current_language):
            """Update language filter options based on other filters"""
            # Convert year selection to list for filtering
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year

            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_years=years,
                    selected_author=selected_author,
                    selected_booktype=selected_booktype,
                    selected_book=selected_book,
                    selected_category=selected_category,
                    ignore={"language"},
                )
                languages = [
                    language
                    for item in items
                    for language in _resource_values(item.get("languages") or item.get("language"))
                ]
                return self._resource_filter_options(
                    languages,
                    current_language,
                    "All Languages",
                )
            
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
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def update_language_label(selected_year, active_tab):
            """Update language label based on selected year"""
            if active_tab == "resources":
                return "Languages (Resources):"
            if selected_year == "lifetime" or not selected_year:
                return "Languages (Lifetime):"
            else:
                return f"Languages (With a sell in {selected_year}):"

        @self.app.callback(
            Output("author-label", "children"),
            Input("year-filter", "value"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def update_author_label(selected_year, active_tab):
            """Update author label based on selected year"""
            if active_tab == "resources":
                return "Authors (Resources):"
            if selected_year == "lifetime" or not selected_year:
                return "Authors (Lifetime):"
            else:
                return f"Authors (With a sell in {selected_year}):"

        @self.app.callback(
            Output("booktype-label", "children"),
            Input("year-filter", "value"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def update_booktype_label(selected_year, active_tab):
            """Update book type label based on selected year"""
            if active_tab == "resources":
                return "Type (Resources):"
            if selected_year == "lifetime" or not selected_year:
                return "Type (Lifetime):"
            else:
                return f"Type (With a sell in {selected_year}):"

        @self.app.callback(
            Output("category-label", "children"),
            Input("year-filter", "value"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def update_category_label(selected_year, active_tab):
            """Update category label based on selected year"""
            if active_tab == "resources":
                return "Category (Resources):"
            if selected_year == "lifetime" or not selected_year:
                return "Category (Lifetime):"
            else:
                return f"Category (With a sell in {selected_year}):"

        @self.app.callback(
            Output("book-label", "children"),
            Input("year-filter", "value"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def update_book_label(selected_year, active_tab):
            """Update book label based on selected year"""
            if active_tab == "resources":
                return "Books (Resources):"
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
            Input("dashboard-tabs", "active_tab"),
            State("author-filter", "value"),
            prevent_initial_call=False
        )
        def update_author_options(selected_year, selected_category, selected_language, selected_booktype, selected_book, refresh_signal, active_tab, current_author):
            """Update author filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year

            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_years=years,
                    selected_language=selected_language,
                    selected_booktype=selected_booktype,
                    selected_book=selected_book,
                    selected_category=selected_category,
                    ignore={"author"},
                )
                authors = [
                    author
                    for item in items
                    for author in _resource_values(item.get("authors"))
                ]
                return self._resource_filter_options(authors, current_author, "All Authors")
            
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
            Input("dashboard-tabs", "active_tab"),
            State("booktype-filter", "value"),
            prevent_initial_call=False
        )
        def update_booktype_options(selected_year, selected_category, selected_language, selected_author, selected_book, refresh_signal, active_tab, current_booktype):
            """Update book type filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year

            type_labels = {"Ebook": "📱 eBook", "Paper": "📖 Paperback", "HardCover": "📚 Hardcover"}
            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_years=years,
                    selected_language=selected_language,
                    selected_author=selected_author,
                    selected_book=selected_book,
                    selected_category=selected_category,
                    ignore={"booktype"},
                )
                book_types = [
                    value
                    for item in items
                    for value in _resource_values(item.get("book_types"))
                ]
                return self._resource_filter_options(
                    book_types,
                    current_booktype,
                    "All Types",
                    type_labels,
                )
            
            df, _ = _get_filtered_data(years, selected_language, selected_author, None, selected_book, selected_category)
            available_types = sorted(df['BookType'].dropna().unique().tolist())
            
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
            Input("dashboard-tabs", "active_tab"),
            State("book-filter", "value"),
            prevent_initial_call=False
        )
        def update_book_options(selected_year, selected_category, selected_language, selected_author, selected_booktype, refresh_signal, active_tab, current_book):
            """Update book filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year

            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_years=years,
                    selected_language=selected_language,
                    selected_author=selected_author,
                    selected_booktype=selected_booktype,
                    selected_category=selected_category,
                    ignore={"book"},
                )
                books = [
                    value
                    for item in items
                    for value in _resource_values(item.get("books"))
                ]
                return self._resource_filter_options(books, current_book, "All Books")
            
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
            Input("dashboard-tabs", "active_tab"),
            State("category-filter", "value"),
            prevent_initial_call=False
        )
        def update_category_options(selected_year, selected_language, selected_author, selected_booktype, selected_book, refresh_signal, active_tab, current_category):
            """Update category filter options based on other filters"""
            if selected_year == "lifetime" or not selected_year:
                years = None
            elif isinstance(selected_year, int):
                years = [selected_year]
            else:
                years = selected_year

            category_label_overrides = {
                "Phrasebook - Guide de Conversations": "Phrasebooks-Guide de conversation",
            }
            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_years=years,
                    selected_language=selected_language,
                    selected_author=selected_author,
                    selected_booktype=selected_booktype,
                    selected_book=selected_book,
                    ignore={"category"},
                )
                return self._resource_filter_options(
                    [item.get("category") for item in items],
                    current_category,
                    "All Categories",
                    category_label_overrides,
                )
            
            # Get filtered royalties data (without category filter)
            df, _ = _get_filtered_data(years, selected_language, selected_author, selected_booktype, selected_book, None)
            
            # Use the same category-to-royalty mapping as the actual data views.
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
            available_nicknames = set(df["book_nick_name"].dropna())
            available_categories = {
                category
                for category in books_df["category"].dropna().unique()
                if available_nicknames.intersection(get_category_royalty_nicknames(category))
            }
            available_categories.update(self._get_resource_categories(purchase_only=True))
            
            available_categories = sorted(list(available_categories))
            
            return [{"label": f"All Categories ({len(available_categories)})", "value": "all"}] + [
                {"label": category_label_overrides.get(cat, cat), "value": cat} for cat in available_categories
            ]

        @self.app.callback(
            Output("year-filter", "options"),
            Output("sales-language-display-mode", "options"),
            Input("data-refresh-signal", "data"),
            Input("dashboard-tabs", "active_tab"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            State("year-filter", "value"),
            prevent_initial_call=False
        )
        def update_year_and_display_options(
            refresh_signal,
            active_tab,
            selected_language,
            selected_author,
            selected_booktype,
            selected_book,
            selected_category,
            current_year,
        ):
            """Update year filter and display mode options when new data is available"""
            # Get updated years
            years_reversed = sorted(self.available_years, reverse=True)
            year_options = [{"label": "Lifetime", "value": "lifetime"}] + \
                           [{"label": str(year), "value": year} for year in years_reversed]

            if active_tab == "resources":
                items = self._get_filtered_resource_items(
                    selected_language=selected_language,
                    selected_author=selected_author,
                    selected_booktype=selected_booktype,
                    selected_book=selected_book,
                    selected_category=selected_category,
                    ignore={"year"},
                )
                resource_years = {
                    date.year
                    for item in items
                    for date in [pd.to_datetime(item.get("publication_date"), errors="coerce")]
                    if not pd.isna(date)
                }
                if isinstance(current_year, int):
                    resource_years.add(current_year)
                year_options = [{"label": "Lifetime", "value": "lifetime"}] + [
                    {"label": str(year), "value": year}
                    for year in sorted(resource_years, reverse=True)
                ]
            
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
            Output("kpi-section", "style"),
            Input("dashboard-tabs", "active_tab"),
            prevent_initial_call=False
        )
        def toggle_sales_overview(active_tab):
            """Show KPI cards on Purchase+Sales, charts only on Sales."""
            if active_tab == "sales":
                return {}, {}
            if active_tab == "purchase":
                return {"display": "none"}, {}
            return {"display": "none"}, {"display": "none"}

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
                filtered_df = filter_by_language(filtered_df, selected_language)
                filtered_exploded = filter_by_language(filtered_exploded, selected_language)
            
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
                category_nicknames = get_category_royalty_nicknames(selected_category)
                filtered_df = filtered_df[filtered_df['book_nick_name'].isin(category_nicknames)]
                filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'].isin(category_nicknames)]
            
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
                trend_data = filter_by_language(trend_data, selected_language)
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
                category_nicknames = get_category_royalty_nicknames(selected_category)
                trend_data = trend_data[trend_data['book_nick_name'].isin(category_nicknames)]
                filter_parts.append(f"📚 {selected_category}")
            
            total_books = trend_data['Net Units Sold'].sum()
            filter_text = " | ".join(filter_parts) if filter_parts else "All"
            trend_title = f"📈 Sales Trend: {filter_text} ({min(self.available_years)} - {max(self.available_years)}): {int(total_books):,} books sold"
            
            from src.visualization.charts import SalesCharts
            fig = SalesCharts.books_sold_per_year(trend_data, title=trend_title)
            return trend_title, fig
        
        @self.app.callback(
            Output("sales-by-language-title", "children"),
            Output("sales-by-language-chart", "figure"),
            Input("year-filter-store", "data"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            Input("sales-language-display-mode", "value"),
            Input("data-refresh-signal", "data"),
            prevent_initial_call=False
        )
        def update_sales_by_language(selected_years, selected_language, selected_author, selected_booktype, selected_book, selected_category, display_mode, refresh_signal):
            """Update sales by language stacked chart by year"""
            filtered_df, _ = _get_filtered_data(
                selected_years,
                selected_language,
                selected_author,
                selected_booktype,
                selected_book,
                selected_category,
            )
            
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
            if selected_category and selected_category != "all":
                filter_parts.append(f"📚 {selected_category}")
            filter_text = " | ".join(filter_parts) if filter_parts else ""

            header_title = "🌐 Sales by Language"
            if filter_text:
                header_title = f"🌐 Sales by Language ({filter_text})"
            
            if len(filtered_df) == 0:
                import plotly.graph_objects as go
                fig = go.Figure()
                fig.add_annotation(text="No sales data available", xref="paper", yref="paper",
                                   x=0.5, y=0.5, showarrow=False)
                title_with_filters = "Sales by Language (No Data)"
                if filter_text:
                    title_with_filters = f"Sales by Language - {filter_text} (No Data)"
                fig.update_layout(template="plotly_dark", height=400, title=title_with_filters)
                return header_title, fig
            
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
            return header_title, fig
        
        
        @self.app.callback(
            Output("tab-content", "children"),
            Input("dashboard-tabs", "active_tab"),
            Input("year-filter-store", "data"),
            Input("year-filter", "value"),
            Input("language-filter", "value"),
            Input("author-filter", "value"),
            Input("booktype-filter", "value"),
            Input("book-filter", "value"),
            Input("category-filter", "value"),
            prevent_initial_call=False
        )
        def render_tab_content(active_tab, selected_years, selected_year, selected_language, selected_author, selected_booktype, selected_book, selected_category):
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
                filtered_royalties = filter_by_language(filtered_royalties, selected_language)
                filtered_exploded = filter_by_language(filtered_exploded, selected_language)
            
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
                category_nicknames = get_category_royalty_nicknames(selected_category)
                filtered_royalties = filtered_royalties[filtered_royalties['book_nick_name'].isin(category_nicknames)]
                filtered_exploded = filtered_exploded[filtered_exploded['book_nick_name'].isin(category_nicknames)]
            
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
            elif active_tab == "resources":
                return self._create_resources_tab(
                    selected_language=selected_language,
                    selected_category=selected_category,
                    selected_author=selected_author,
                    selected_booktype=selected_booktype,
                    selected_book=selected_book,
                    selected_years=resource_year_filter(selected_year),
                )
            elif active_tab == "chatbot":
                return self._create_chatbot_tab()
            elif active_tab == "sales":
                return self._create_sales_tab(filtered_royalties, selected_years, selected_language)
            elif active_tab == "books":
                return self._create_books_tab(filtered_royalties, filter_text)
            elif active_tab == "geography":
                return self._create_geography_tab(filtered_royalties, filter_text)
            
            return html.Div("Select a tab to view content")
        
        @self.app.callback(
            Output("chat-history-store", "data"),
            Output("chat-session-store", "data"),
            Output("chat-history-view", "children"),
            Output("chatbot-results", "children"),
            Output("chat-input", "value"),
            Output("chat-engine-label", "children"),
            Input("chat-send-btn", "n_clicks"),
            Input("chat-clear-btn", "n_clicks"),
            State("chat-input", "value"),
            State("chat-history-store", "data"),
            State("chat-session-store", "data"),
            State("chat-engine-toggle", "value"),
            State("chat-model-dropdown", "value"),
            prevent_initial_call=True
        )
        def handle_chat(send_clicks, clear_clicks, message, history, session, use_llm, model_name):
            """Handle chat input and update results."""
            ctx = dash.callback_context
            if not ctx.triggered:
                raise dash.exceptions.PreventUpdate

            trigger = ctx.triggered[0]['prop_id'].split('.')[0]
            history = history or []
            session = session or {"filters": {}}
            engine_label = "LLM" if use_llm else "Rules"

            if trigger == "chat-clear-btn":
                empty_history = []
                empty_session = {"filters": {}}
                return (
                    empty_history,
                    empty_session,
                    self._render_chat_history(empty_history),
                    self._render_chat_results(None),
                    "",
                    engine_label
                )

            if not message or not message.strip():
                raise dash.exceptions.PreventUpdate

            user_message = message.strip()
            history.append({"role": "user", "content": user_message})

            engine_mode = "llm" if use_llm else "rules"
            engine_notice = ""
            engine = self.chatbot_engine_llm if engine_mode == "llm" else self.chatbot_engine_rules
            if engine is None and self.chatbot_engine_rules is not None:
                engine = self.chatbot_engine_rules
                engine_notice = "LLM engine unavailable; using rules."
                engine_label = "Rules"
            if use_llm and model_name and engine is self.chatbot_engine_llm:
                engine.ollama_model = model_name

            if engine is None:
                response_text = (
                    f"Chatbot unavailable: {self.chatbot_init_error or 'Missing books database.'}"
                )
                history.append({"role": "assistant", "content": response_text})
                return (
                    history,
                    session,
                    self._render_chat_history(history),
                    self._render_chat_results(None),
                    "",
                    engine_label
                )

            response = engine.respond(
                user_message,
                session.get("filters", {}),
                history
            )
            if engine_notice:
                if response.note:
                    response.note = f"{engine_notice} {response.note}"
                else:
                    response.note = engine_notice
            history.append({"role": "assistant", "content": response.message})
            session["filters"] = response.filters

            return (
                history,
                session,
                self._render_chat_history(history),
                self._render_chat_results(response),
                "",
                engine_label
            )

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
                filtered_exploded = filter_by_language(filtered_exploded, selected_language)
            
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
                df_copy = filter_by_language(df_copy, selected_language)
            
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
                df_copy = filter_by_language(df_copy, selected_language)
            
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
                df_copy = filter_by_language(df_copy, selected_language)
            
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
                df_copy = filter_by_language(df_copy, selected_language)
            
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
    
    def _create_books_tab(self, data=None, filter_text: str = ""):
        """Create books analysis tab content"""
        if data is None:
            data = self.royalties

        context = f" ({filter_text})" if filter_text else ""

        def _auto_md_cols(n: int) -> int:
            if n <= 1:
                return 12
            if n == 2:
                return 6
            if n == 3:
                return 4
            if n == 4:
                return 3
            return 3

        ebook_vs_physical_cards = [
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(
                        figure=SalesCharts.ebook_vs_physical_pie(data),
                        config={'displayModeBar': False}
                    )
                ]),
                className="shadow-sm mb-4",
            ),
            dbc.Card(
                dbc.CardBody([
                    dcc.Graph(
                        figure=SalesCharts.ebook_vs_physical_by_year(data),
                        config={'displayModeBar': False}
                    )
                ]),
                className="shadow-sm mb-4",
            ),
            # dbc.Card(
            #     dbc.CardBody([
            #         dcc.Graph(
            #             figure=SalesCharts.ebook_vs_physical_revenue(data),
            #             config={'displayModeBar': False}
            #         )
            #     ]),
            #     className="shadow-sm mb-4",
            # ),
        ]
        ebook_vs_physical_md = _auto_md_cols(len(ebook_vs_physical_cards))

        return dbc.Container([
            # Total Sales by Book section
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(f"📚 Total Sales by Book{context}")),
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
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5(f"Top 20 Books by Net Units Sold{context}")),
                        dbc.CardBody([
                            self._create_top_books_table(data, limit=20)
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ]),
            # eBook vs Physical Books Analysis section
            dbc.Row([
                dbc.Col([
                    html.H4(f"📱 eBook vs 📖 Physical Books Analysis{context}", className="mb-3 mt-2")
                ])
            ]),
            dbc.Row(
                [dbc.Col(card, md=ebook_vs_physical_md) for card in ebook_vs_physical_cards],
                className="g-4",
            ),
            # Summary statistics
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H5(f"📊 Format Statistics{context}")),
                        dbc.CardBody([
                            self._create_format_stats_table(data)
                        ])
                    ], className="shadow-sm mb-4")
                ])
            ])
        ], fluid=True)
    
    def _create_top_books_table(self, data, limit: int = 20):
        """Create a table of top books by units sold."""
        if len(data) == 0 or 'book_nick_name' not in data.columns or 'Net Units Sold' not in data.columns:
            return html.P("No data available")

        units_by_book = (
            data.groupby('book_nick_name')['Net Units Sold']
            .sum()
            .sort_values(ascending=False)
            .head(limit)
        )

        title_map = {}
        date_map = {}
        try:
            books_df = pd.read_csv(BOOKS_DATABASE_PATH)
            if 'book_nick_name' in books_df.columns and 'title' in books_df.columns:
                title_map = books_df.set_index('book_nick_name')['title'].to_dict()
            if 'book_nick_name' in books_df.columns and 'publication_date' in books_df.columns:
                date_map = books_df.set_index('book_nick_name')['publication_date'].to_dict()
        except Exception as e:
            print(f"Warning: Could not load books database for table: {e}")

        royalty_to_db = {}
        try:
            from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY
            for db_nick, royalty_nicks in DB_NICKNAME_TO_ROYALTY.items():
                for royalty_nick in royalty_nicks:
                    royalty_to_db[royalty_nick] = db_nick
        except Exception:
            pass

        def _strip_date_suffix(text: str) -> str:
            if not text:
                return text
            pattern = (
                r"\s*(?:\u2013|\u2014|-)\s*"
                r"(January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},\s+\d{4}\.?\s*$"
            )
            match = re.search(pattern, text)
            if match:
                return text[: match.start()].rstrip()
            return text

        def clean_title(raw_title: str) -> str:
            if not raw_title:
                return "Unknown"
            text = _strip_date_suffix(str(raw_title).strip())
            if ":" in text:
                parts = [part.strip() for part in text.split(":") if part.strip()]
                if len(parts) >= 2 and "-" in parts[1] and " " not in parts[1]:
                    language = parts[1].split("-", 1)[0].strip()
                    if language:
                        return f"{parts[0]} - {language}"
                return parts[0]
            return text

        def format_pub_date(raw_date: str) -> str:
            if not raw_date:
                return ""
            date_value = pd.to_datetime(raw_date, errors="coerce")
            if pd.isna(date_value):
                return str(raw_date).strip()
            return date_value.strftime("%B %d, %Y")

        def extract_date_from_title(raw_title: str) -> str:
            if not raw_title:
                return ""
            text = str(raw_title)
            pattern = (
                r"(?:\u2013|\u2014|-)\s*"
                r"(?P<date>(January|February|March|April|May|June|July|August|September|October|November|December)"
                r"\s+\d{1,2},\s+\d{4})"
            )
            match = re.search(pattern, text)
            if match:
                return match.group("date").strip()
            return ""

        rows = []
        for rank, (nickname, units) in enumerate(units_by_book.items(), start=1):
            db_nick = royalty_to_db.get(nickname, nickname)
            raw_title = title_map.get(db_nick, nickname)
            title = clean_title(raw_title)
            pub_date = format_pub_date(date_map.get(db_nick, ""))
            if not pub_date:
                pub_date = extract_date_from_title(raw_title)
            rows.append(
                html.Tr([
                    html.Td(rank),
                    html.Td(title),
                    html.Td(pub_date if pub_date else "Unknown"),
                    html.Td(f"{int(units):,}")
                ])
            )

        return dbc.Table(
            [
                html.Thead(html.Tr([
                    html.Th("Rank"),
                    html.Th("Title"),
                    html.Th("Publication Date"),
                    html.Th("Net Units Sold"),
                ])),
                html.Tbody(rows),
            ],
            striped=True,
            hover=True,
            responsive=True,
            size="sm",
            className="mb-0",
        )

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
                html.Th("Avg Price/Unit")
            ])),
            html.Tbody([
                html.Tr([
                    html.Td("📱 eBook"),
                    html.Td(f"{ebook_units:,}"),
                    html.Td(f"{(ebook_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${(ebook_revenue/ebook_units) if ebook_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td("📖 Paperback"),
                    html.Td(f"{paper_units:,}"),
                    html.Td(f"{(paper_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${(paper_revenue/paper_units) if paper_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td("📕 Hardcover"),
                    html.Td(f"{hardcover_units:,}"),
                    html.Td(f"{(hardcover_units/total_units*100) if total_units > 0 else 0:.1f}%"),
                    html.Td(f"${(hardcover_revenue/hardcover_units) if hardcover_units > 0 else 0:.2f}")
                ]),
                html.Tr([
                    html.Td(html.Strong("Total")),
                    html.Td(html.Strong(f"{total_units:,}")),
                    html.Td(html.Strong("100%")),
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
            marketplace_fig = empty_fig
            country_fig = empty_fig
        else:
            marketplace_fig = GeographicCharts.sales_by_marketplace_bar(data)
            country_fig = GeographicCharts.sales_by_country_heatmap(data)
            
        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(f"🛒 Sales Distribution by Marketplace ({filter_text}): {total_sales:,} books")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=marketplace_fig,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=12)
            ]),
            dbc.Row([
                dbc.Col([
                    dbc.Card([
                        dbc.CardHeader(html.H4(f"🗺️ Sales Heatmap by Country ({filter_text}): {total_sales:,} books")),
                        dbc.CardBody([
                            dcc.Graph(
                                figure=country_fig,
                                config={'displayModeBar': False}
                            )
                        ])
                    ], className="shadow-sm mb-4")
                ], md=12)
            ])
        ], fluid=True)
    
    
    def _get_available_covers(self):
        """Resolve book cover images from local assets or S3."""
        use_s3_images = os.getenv('USE_S3_DATA', 'false').lower() == 'true'
        source = "s3" if use_s3_images else "local"

        if self._available_covers is not None and self._available_covers_source == source:
            return self._available_covers

        available_covers = {}
        if use_s3_images:
            try:
                import boto3
                from urllib.parse import quote

                s3 = boto3.client('s3')
                bucket_name = 'resulam-images'
                prefix = 'ResulamBookCoversQRCode_Compressed/Book'
                s3_base_url = "https://resulam-images.s3.amazonaws.com/ResulamBookCoversQRCode_Compressed"

                resp = s3.list_objects_v2(Bucket=bucket_name, Prefix=prefix)
                for obj in resp.get('Contents', []):
                    key = obj['Key']
                    filename = key.split('/')[-1]
                    if filename.lower().startswith('book'):
                        name_part = filename[4:]
                        parts = name_part.split('_', 1)
                        if parts:
                            num_str = parts[0].strip('_')
                            if num_str.isdigit():
                                book_num = int(num_str)
                                available_covers[book_num] = f"{s3_base_url}/{quote(filename)}"
            except Exception as e:
                print(f"Warning: Could not fetch S3 cover list: {e}")
        else:
            assets_path = Path(__file__).parent.parent.parent / 'assets'
            for cover_folder in ['book_covers', 'resource_covers']:
                book_covers_path = assets_path / cover_folder
                if book_covers_path.exists():
                    for img_file in book_covers_path.glob('book*.*'):
                        name = img_file.stem.lower()
                        if name.startswith('book'):
                            parts = name[4:].split('_', 1)
                            if parts:
                                num_str = parts[0].strip('_')
                                if num_str.isdigit():
                                    book_num = int(num_str)
                                    available_covers.setdefault(book_num, f"assets/{cover_folder}/{img_file.name}")

        self._available_covers = available_covers
        self._available_covers_source = source
        return available_covers

    def _build_book_cards(self, filtered_books: pd.DataFrame) -> list:
        """Build book cards with cover images and purchase links."""
        available_covers = self._get_available_covers()
        book_cards = []

        for _, book in filtered_books.iterrows():
            title = book.get('title', 'Unknown Title')
            if ' - ' in str(title):
                title = str(title).split(' - ')[0].strip()

            language = book.get('language_name', 'Unknown')
            authors = book.get('authors', 'Unknown')
            book_id = book.get('id', 0)

            cover_image = available_covers.get(book_id, None)

            paperback_link = book.get('paperback', '')
            ebook_link = book.get('ebook', '')
            hardcover_link = book.get('hard_cover', '')

            link_buttons = []
            if pd.notna(paperback_link) and paperback_link:
                link_buttons.append(
                    dbc.Button(
                        [html.I(className="fas fa-book me-2"), "Paperback"],
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
                        [html.I(className="fas fa-tablet-alt me-2"), "eBook"],
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
                        [html.I(className="fas fa-book-open me-2"), "Hardcover"],
                        href=hardcover_link,
                        target="_blank",
                        color="warning",
                        size="sm",
                        className="me-2 mb-2"
                    )
                )

            if not link_buttons:
                link_buttons.append(html.Span("No purchase links available", className="text-muted"))

            image_link = None
            if pd.notna(paperback_link) and paperback_link:
                image_link = paperback_link
            elif pd.notna(ebook_link) and ebook_link:
                image_link = ebook_link
            elif pd.notna(hardcover_link) and hardcover_link:
                image_link = hardcover_link

            card_children = []
            if cover_image:
                cover_img = dbc.CardImg(
                    src=cover_image,
                    top=True,
                    style={
                        "height": "250px",
                        "objectFit": "cover",
                        "objectPosition": "center top",
                        "backgroundColor": "transparent",
                        "cursor": "pointer" if image_link else "default",
                    }
                )
                if image_link:
                    card_children.append(html.A(cover_img, href=image_link, target="_blank"))
                else:
                    card_children.append(cover_img)

            card_children.append(
                dbc.CardBody([
                    html.H6(
                        title[:70] + "..." if len(str(title)) > 70 else title,
                        className="card-title",
                        style={"fontSize": "0.9rem", "fontWeight": "600"},
                    ),
                    html.P([
                        html.Span(f"Language: {language}", className="me-2"),
                        html.Br(),
                        html.Span(f"Author: {authors}", style={"fontSize": "0.8rem"}),
                    ], className="card-text text-muted small mb-2"),
                    html.Div(link_buttons, className="mt-auto"),
                ], className="d-flex flex-column")
            )

            card = dbc.Card(card_children, className="shadow-sm mb-3 h-100")
            book_cards.append(dbc.Col(card, xs=12, sm=6, md=4, lg=3, className="mb-3"))

        return book_cards

    def _render_chat_history(self, history: list) -> list:
        if not history:
            return [
                html.Div(
                    "Ask me about a language, author, or category.",
                    className="text-muted small"
                )
            ]

        items = []
        for message in history[-20:]:
            role = message.get("role", "assistant")
            content = message.get("content", "")
            class_name = "chat-bubble chat-user" if role == "user" else "chat-bubble chat-assistant"
            if isinstance(content, str) and "\n" in content:
                parts = content.split("\n")
                children = []
                for idx, part in enumerate(parts):
                    if idx:
                        children.append(html.Br())
                    children.append(part)
                items.append(html.Div(children, className=class_name))
            else:
                items.append(html.Div(content, className=class_name))
        return items

    def _render_chat_results(self, response) -> html.Div:
        if response is None:
            return dbc.Alert(
                "Ask for a language, author, or category to see matching books.",
                color="info",
                className="mb-0"
            )

        if response.total_results == 0:
            return dbc.Alert(
                "No books found for this request. Try another language or category.",
                color="warning",
                className="mb-0"
            )

        filter_parts = []
        for key in ["year", "language", "category", "author", "format"]:
            if response.filters.get(key):
                label = "Year" if key == "year" else key.title()
                filter_parts.append(f"{label}: {response.filters[key]}")
        if response.keywords:
            filter_parts.append(f"Keywords: {', '.join(response.keywords)}")
        filter_text = " | ".join(filter_parts) if filter_parts else "All Books"

        header = html.Div([
            html.H6(f"Matches ({response.total_results})", className="mb-1"),
            html.Div(filter_text, className="text-muted small"),
        ], className="mb-2")

        note = html.Div(response.note, className="text-muted small mb-2") if response.note else None
        book_cards = self._build_book_cards(response.results)

        return html.Div([
            header,
            note,
            dbc.Row(book_cards)
        ])

    def _get_ollama_models(self) -> List[str]:
        """Return available local Ollama models, or an empty list on failure."""
        ollama_url = os.getenv("CHATBOT_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        if not ollama_url:
            return []
        try:
            response = requests.get(f"{ollama_url}/api/tags", timeout=3)
            response.raise_for_status()
            data = response.json()
        except Exception:
            return []

        models = []
        for item in data.get("models", []):
            name = str(item.get("name", "")).strip()
            if name:
                models.append(name)
        return sorted(set(models))

    def _create_chatbot_tab(self):
        """Create the chatbot tab content."""
        status = None
        if self.chatbot_engine_rules is None:
            status = dbc.Alert(
                f"Chatbot unavailable: {self.chatbot_init_error or 'Missing books database.'}",
                color="warning",
                className="mb-3"
            )
        elif self.chatbot_engine_llm is None:
            status = dbc.Alert(
                "LLM engine unavailable; rules engine only.",
                color="info",
                className="mb-3"
            )

        engine_default = os.getenv("CHATBOT_ENGINE", "rules").lower().strip()
        use_llm_default = engine_default == "llm"
        engine_label = "LLM" if use_llm_default else "Rules"
        models = self._get_ollama_models()
        model_options = [{"label": name, "value": name} for name in models]
        model_default = None
        env_model = os.getenv("CHATBOT_LLM_MODEL", "llama3.2:3b")
        if model_options:
            model_default = env_model if env_model in models else models[0]
        model_disabled = not model_options
        model_placeholder = "No local models" if model_disabled else "Select model"

        chat_card = dbc.Card([
            dbc.CardHeader(
                dbc.Row([
                    dbc.Col(html.H5("Book Chatbot", className="mb-0")),
                    dbc.Col(
                        html.Div(
                            [
                                html.Span("Engine:", className="text-muted small me-2"),
                                html.Span(engine_label, id="chat-engine-label", className="text-muted small me-3"),
                                dbc.Switch(
                                    id="chat-engine-toggle",
                                    label="LLM",
                                    value=use_llm_default,
                                    className="d-inline-block",
                                ),
                            ],
                            className="d-flex align-items-center justify-content-center gap-2",
                        ),
                        className="text-center"
                    ),
                    dbc.Col(
                        html.Div(
                            [
                                html.Span("Model:", className="text-muted small me-2"),
                                dcc.Dropdown(
                                    id="chat-model-dropdown",
                                    options=model_options,
                                    value=model_default,
                                    placeholder=model_placeholder,
                                    clearable=False,
                                    searchable=True,
                                    disabled=model_disabled,
                                    style={"minWidth": "180px"},
                                ),
                            ],
                            className="d-flex align-items-center justify-content-center gap-2",
                        ),
                        className="text-center"
                    ),
                    dbc.Col(
                        dbc.Button(
                            "Clear",
                            id="chat-clear-btn",
                            color="secondary",
                            size="sm",
                            className="ms-auto"
                        ),
                        className="text-end"
                    ),
                ], align="center")
            ),
            dbc.CardBody([
                status if status else html.Div(),
                html.Div(self._render_chat_history([]), id="chat-history-view", className="chat-history"),
                html.Div([
                    dcc.Textarea(
                        id="chat-input",
                        placeholder="Example: I want book about Basaa",
                        className="chat-input"
                    ),
                    dbc.Button(
                        "Send",
                        id="chat-send-btn",
                        color="primary",
                        className="chat-send-btn"
                    ),
                ], className="chat-input-row"),
                html.Div(
                    "Tip: Ask about a language, author, category, or format (ebook, paperback).",
                    className="text-muted small mt-2"
                ),
            ])
        ], className="shadow-sm h-100")

        results_card = dbc.Card([
            dbc.CardHeader(html.H5("Book Matches", className="mb-0")),
            dbc.CardBody(
                dcc.Loading(
                    id="chat-results-loading",
                    type="default",
                    children=html.Div(self._render_chat_results(None), id="chatbot-results")
                )
            )
        ], className="shadow-sm h-100")

        return dbc.Container([
            dbc.Row([
                dbc.Col(chat_card, md=5, className="mb-3"),
                dbc.Col(results_card, md=7, className="mb-3"),
            ])
        ], fluid=True, className="chatbot-tab")

    def _load_resource_items(self, purchase_only=False):
        """Load non-book resources from the shared resources CSV."""
        try:
            resources_df = pd.read_csv(RESOURCES_DATABASE_PATH).fillna("")
        except Exception as e:
            print(f"Warning: Could not load resources database: {e}")
            return []

        if not hasattr(self, "_resource_authors_by_language"):
            authors_by_language = {}
            try:
                books_df = pd.read_csv(BOOKS_DATABASE_PATH).fillna("")
                for _, book in books_df.iterrows():
                    language_key = str(book.get("language_name", "")).strip().casefold()
                    if not language_key:
                        continue
                    for author in re.split(r"\s*(?:,|;|&|\band\b)\s*", str(book.get("authors", ""))):
                        normalized = normalize_author_name(author.strip())
                        if normalized and normalized != "Resulam":
                            authors_by_language.setdefault(language_key, set()).add(normalized)
            except Exception as e:
                print(f"Warning: Could not infer resource authors: {e}")
            self._resource_authors_by_language = authors_by_language

        if purchase_only and "display_in_purchase" in resources_df.columns:
            resources_df = resources_df[
                resources_df["display_in_purchase"].astype(str).str.lower().isin(["true", "1", "yes"])
            ]

        link_indices = sorted({
            int(match.group(1))
            for column in resources_df.columns
            if (match := re.fullmatch(r"link(\d+)_url", str(column)))
        })
        items = []
        for _, row in resources_df.iterrows():
            links = []
            for idx in link_indices:
                label = str(row.get(f"link{idx}_label", "")).strip()
                url = str(row.get(f"link{idx}_url", "")).strip()
                color = str(row.get(f"link{idx}_color", "")).strip() or "primary"
                if label and url:
                    links.append((label, url, color))

            language = str(row.get("language", "")).strip() or "All"
            explicit_authors = _resource_values(row.get("authors", ""))
            authors = explicit_authors or sorted(
                self._resource_authors_by_language.get(language.casefold(), set())
            )
            items.append({
                "name": str(row.get("name", "")).strip(),
                "category": str(row.get("category", "")).strip(),
                "language": language,
                "languages": _resource_values(row.get("languages", "")) or [language],
                "authors": authors,
                "book_types": _resource_values(row.get("book_types", "")),
                "books": _resource_values(row.get("books", "")),
                "publication_date": str(row.get("publication_date", "")).strip(),
                "image": str(row.get("image", "")).strip(),
                "image_fit": str(row.get("image_fit", "")).strip() or "contain",
                "description": str(row.get("description", "")).strip(),
                "links": links,
            })
        return [item for item in items if item["name"]]

    def _get_resource_categories(self, purchase_only=False):
        """Return resource categories from the shared resources CSV."""
        return sorted({
            item["category"]
            for item in self._load_resource_items(purchase_only=purchase_only)
            if item.get("category")
        })

    def _get_filtered_resource_items(
        self,
        selected_years=None,
        selected_language=None,
        selected_author=None,
        selected_booktype=None,
        selected_book=None,
        selected_category=None,
        ignore=frozenset(),
    ):
        """Return Resources-tab items matching all active facets except ignored ones."""
        return [
            item
            for item in self._load_resource_items(purchase_only=False)
            if item.get("category") != "Comics"
            and matches_resource_filters(
                item,
                selected_years=selected_years,
                selected_language=selected_language,
                selected_author=selected_author,
                selected_booktype=selected_booktype,
                selected_book=selected_book,
                selected_category=selected_category,
                ignore=ignore,
            )
        ]

    @staticmethod
    def _resource_filter_options(values, current_value, all_label, labels=None):
        """Build faceted options while retaining the current URL/UI selection."""
        unique_values = {
            value
            for value in values
            if value is not None and str(value).strip() and not is_universal_language(value)
        }
        if _active_filter(current_value):
            unique_values.add(current_value)
        ordered = sorted(unique_values, key=lambda value: str(value).casefold())
        labels = labels or {}
        return [{"label": f"{all_label} ({len(ordered)})", "value": "all"}] + [
            {"label": labels.get(value, value), "value": value}
            for value in ordered
        ]

    def _build_resource_card(self, item, lg=3):
        """Build one non-book resource card from the shared resource item shape."""
        link_buttons = [
            dbc.Button(
                label,
                href=url,
                target="_blank",
                color=color,
                size="sm",
                className="me-2 mb-2",
            )
            for label, url, color in item.get("links", [])
        ]
        primary_url = item["links"][0][1] if item.get("links") else None
        card_children = []

        if item.get("image"):
            image_fit = item.get("image_fit", "cover")
            object_fit = "cover"
            object_position = "center top"
            if isinstance(image_fit, str) and image_fit.startswith("cover:"):
                object_position = image_fit.split(":", 1)[1].strip() or object_position
            elif image_fit in {"cover", "contain", "fill", "scale-down", "none"}:
                object_fit = image_fit

            image = dbc.CardImg(
                src=item["image"],
                top=True,
                style={
                    "height": "250px",
                    "objectFit": object_fit,
                    "objectPosition": object_position,
                    "backgroundColor": "transparent",
                    "cursor": "pointer" if primary_url else "default",
                },
            )
            card_children.append(html.A(image, href=primary_url, target="_blank") if primary_url else image)

        language = item.get("language", "")
        category = item.get("category", "")
        description = item.get("description", "")
        language_label = "All languages" if language == "All" else (language or "Language not specified")
        language_panel = html.Div(
            [
                html.Span("Language", className="resource-language-label"),
                html.Span(
                    [
                        html.Span("🌐", **{"aria-hidden": "true"}, className="resource-language-icon"),
                        language_label,
                    ],
                    className="resource-language-value",
                ),
            ],
            className="resource-language-panel",
            title=f"Language: {language_label}",
            **{"aria-label": f"Language: {language_label}"},
        )

        details = []
        if category:
            details.append(html.Span(category, style={"fontSize": "0.8rem"}))
        if description:
            if details:
                details.append(html.Br())
            details.append(html.Span(description))

        primary_details = html.Div(
            [
                html.H6(item.get("name", "Resource"), className="mb-2"),
                html.P(details, className="card-text text-muted small mb-0") if details else html.Div(),
            ],
            className="resource-card-primary",
        )
        actions = (
            html.Div(link_buttons, className="resource-card-actions")
            if link_buttons
            else html.Span("Link coming soon", className="resource-card-actions text-muted small")
        )
        body_children = html.Div(
            [primary_details, language_panel, actions],
            className="resource-card-metadata",
        )
        card_children.append(dbc.CardBody(body_children))

        return dbc.Col(
            dbc.Card(card_children, className="shadow-sm h-100"),
            xs=12,
            sm=6,
            md=4,
            lg=lg,
            className="mb-3",
        )

    def _create_resources_tab(
        self,
        selected_language=None,
        selected_category=None,
        selected_author=None,
        selected_booktype=None,
        selected_book=None,
        selected_years=None,
    ):
        """Create the curated resources tab content from the shared resources CSV."""
        resource_groups = {}
        for item in self._load_resource_items(purchase_only=False):
            if item.get("category") == "Comics":
                continue
            if not matches_resource_filters(
                item,
                selected_years=selected_years,
                selected_language=selected_language,
                selected_author=selected_author,
                selected_booktype=selected_booktype,
                selected_book=selected_book,
                selected_category=selected_category,
            ):
                continue
            resource_groups.setdefault(item["category"] or "Resources", []).append(item)

        sections = []
        for title, items in resource_groups.items():
            entries = [
                (pd.to_datetime(item.get("publication_date"), errors="coerce"), self._build_resource_card(item, lg=4))
                for item in items
            ]
            entries.sort(key=lambda entry: entry[0] if not pd.isna(entry[0]) else pd.Timestamp.min, reverse=True)
            sections.append(html.H4(title, className="mt-4 mb-3"))
            sections.append(dbc.Row([card for _, card in entries]))

        return dbc.Container([
            dbc.Row([
                dbc.Col([
                    html.H3("Resulam Resources", className="mb-2"),
                    html.P(
                        "Courses, audiobooks, apps, dictionaries, conjugators, and support links.",
                        className="text-muted mb-3",
                    ),
                ])
            ]),
            *sections,
        ], fluid=True)

    def _get_resource_preview_items(self, selected_language=None):
        """Return non-book resources shown in the purchase grid."""
        purchase_items = self._load_resource_items(purchase_only=True)
        if selected_language and selected_language != "all":
            purchase_items = [
                item for item in purchase_items
                if matches_resource_item_filter(item, selected_language)
            ]
        else:
            return purchase_items

        seen_names = {item["name"] for item in purchase_items if item.get("name")}
        preview_items = list(purchase_items)
        for item in self._load_resource_items(purchase_only=False):
            name = item.get("name")
            if not name or name in seen_names:
                continue
            if item.get("category") not in LANGUAGE_FILTERED_RESOURCE_CATEGORIES:
                continue
            if matches_resource_item_filter(item, selected_language):
                preview_items.append(item)
                seen_names.add(name)
        return preview_items

    def _build_resource_preview_entries(
        self,
        selected_language=None,
        selected_category=None,
        selected_author=None,
        selected_booktype=None,
        selected_book=None,
    ):
        """Build dated non-book resource entries that share the book grid layout."""
        preview_items = self._get_resource_preview_items(selected_language)
        preview_items = [
            item
            for item in preview_items
            if matches_resource_filters(
                item,
                selected_language=selected_language,
                selected_author=selected_author,
                selected_booktype=selected_booktype,
                selected_book=selected_book,
                selected_category=selected_category,
            )
        ]

        if not preview_items:
            return []

        cards = []
        for item in preview_items:
            card = self._build_resource_card(item, lg=3)
            cards.append((pd.to_datetime(item.get("publication_date"), errors="coerce"), card))
        return cards

    def _build_resource_preview_cards(self, selected_language=None, selected_category=None):
        """Build non-book resource cards that share the book grid layout."""
        return [card for _, card in self._build_resource_preview_entries(selected_language, selected_category)]

    def _create_resources_preview_section(self, selected_language=None, selected_category=None):
        """Show key non-book resources on the main purchase tab."""
        cards = self._build_resource_preview_cards(selected_language, selected_category)
        if not cards:
            return html.Div()
        return html.Div([
            html.H3("Comics & Online Courses", className="mt-2 mb-3"),
            dbc.Row(cards),
        ], className="mb-4")

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
            lang_filtered = filtered_books[
                filtered_books['language_name'].apply(
                    lambda value: matches_language_filter(value, selected_language)
                )
            ]
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
            filtered_books = author_filtered
        
        # Apply book filter if selected.
        # Here we expect a canonical nickname (e.g. "ewondo_conversation_de_base").
        # Avoid fuzzy matching because it can wrongly match other languages in the same category
        # (e.g., all "conversation_de_base" books).
        if selected_book and selected_book != "all":
            candidate_db_nicknames = {selected_book}
            try:
                from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY

                for db_nick, royalty_nicks in DB_NICKNAME_TO_ROYALTY.items():
                    if db_nick == selected_book or selected_book in royalty_nicks:
                        candidate_db_nicknames.add(db_nick)
            except Exception:
                pass

            book_filtered = filtered_books[filtered_books["book_nick_name"].isin(candidate_db_nicknames)]

            # Fallback: if nothing matched, attempt a strict normalized compare.
            if len(book_filtered) == 0:
                selected_book_normalized = normalize_text(selected_book).replace("_", " ")

                def book_matches_strict(book_nickname):
                    if pd.isna(book_nickname) or not book_nickname:
                        return False
                    book_nickname_normalized = normalize_text(book_nickname).replace("_", " ")
                    return book_nickname_normalized == selected_book_normalized

                book_filtered = filtered_books[filtered_books["book_nick_name"].apply(book_matches_strict)]

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
            filtered_books = booktype_filtered
        
        # Apply category filter if selected (strict filter - must match exactly)
        if selected_category and selected_category != "all":
            filtered_books = filtered_books[filtered_books['category'] == selected_category]

        resource_entries = self._build_resource_preview_entries(
            selected_language=selected_language,
            selected_category=selected_category,
            selected_author=selected_author,
            selected_booktype=selected_booktype,
            selected_book=selected_book,
        )
        resource_cards = [card for _, card in resource_entries]
        resources_preview = html.Div([
            html.H3("Comics & Online Courses", className="mt-2 mb-3"),
            dbc.Row(resource_cards),
        ], className="mb-4") if resource_cards else html.Div()
        if len(filtered_books) == 0:
            return dbc.Container([
                resources_preview,
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
            assets_path = Path(__file__).parent.parent.parent / 'assets'
            for cover_folder in ['book_covers', 'resource_covers']:
                book_covers_path = assets_path / cover_folder
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
                                    available_covers.setdefault(book_num, f"assets/{cover_folder}/{img_file.name}")
        
        # Create book cards
        book_entries = []
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
                    style={
                        "height": "250px",
                        "objectFit": "cover",
                        "objectPosition": "center top",
                        "backgroundColor": "transparent",
                        "cursor": "pointer" if image_link else "default",
                    }
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
            
            publication_sort_date = pd.to_datetime(book.get('publication_date'), errors="coerce")
            book_entries.append((
                publication_sort_date,
                dbc.Col(card, xs=12, sm=6, md=4, lg=3, className="mb-3")
            ))
        
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
        combined_entries = resource_entries + book_entries
        combined_entries.sort(
            key=lambda item: item[0] if not pd.isna(item[0]) else pd.Timestamp.min,
            reverse=True,
        )
        combined_cards = [card for _, card in combined_entries]
        
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
            html.H3("Comics, Courses & Books", className="mt-2 mb-3") if resource_cards else html.Div(),
            dbc.Row(combined_cards)
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


def create_public_dashboard(
    data: Dict[str, pd.DataFrame],
    server=None,
    prefix: str = "/"
) -> PublicDashboard:
    """
    Factory function to create public dashboard instance
    
    Args:
        data: Dictionary containing processed dataframes
        server: Optional Flask server to attach the Dash app to
        prefix: URL prefix for the app (e.g. "/" or "/shop/")
        
    Returns:
        PublicDashboard instance
    """
    return PublicDashboard(data, server=server, prefix=prefix)


# Backwards compatibility alias
def create_dashboard(
    data: Dict[str, pd.DataFrame],
    server=None,
    prefix: str = "/"
) -> PublicDashboard:
    return create_public_dashboard(data, server=server, prefix=prefix)

