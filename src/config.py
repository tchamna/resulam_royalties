"""
Configuration module for Resulam Royalties Dashboard
"""
from pathlib import Path
from datetime import datetime

# Date configuration
CURRENT_YEAR = datetime.now().year
LAST_YEAR = CURRENT_YEAR - 1

# Revenue configuration
NET_REVENUE_PERCENTAGE = 1  # 80% of royalties go to net revenue (after platform/fees)

# Project paths
PROJECT_ROOT = Path(__file__).parent.parent
DATA_DIR = PROJECT_ROOT / "data"

# Data file paths - Support both local development and S3-based deployment
import os
_USE_S3 = os.getenv('USE_S3_DATA', 'false').lower() == 'true'

# Local paths (always available for fallback/development)
MAIN_DIR = r"G:\My Drive\Mbú'ŋwɑ̀'nì\RoyaltiesResulam"
LOCAL_BOOKS_DATABASE_PATH = Path(MAIN_DIR) / "Resulam_books_database_Amazon_base_de_donnee_livres.csv"
LOCAL_ROYALTIES_HISTORY_PATH = Path(MAIN_DIR) / f"KDP_OrdersResulamBookSales2015_{CURRENT_YEAR}RoyaltiesReportsHistory.xlsx"

# EC2 paths - data downloaded from S3
DATA_DIR_LOCAL = PROJECT_ROOT / "data"
EC2_BOOKS_DATABASE_PATH = DATA_DIR_LOCAL / "Resulam_books_database_Amazon_base_de_donnee_livres.csv"
EC2_ROYALTIES_HISTORY_PATH = DATA_DIR_LOCAL / f"KDP_OrdersResulamBookSales2015_{CURRENT_YEAR}RoyaltiesReportsHistory.xlsx"

# Determine which paths to use - prioritize S3-downloaded files, fallback to local
def _get_data_paths():
    """Resolve data paths based on environment and file availability."""
    # Check if we're on EC2 with S3 data
    if _USE_S3:
        # Try EC2 S3 downloaded paths first
        if EC2_BOOKS_DATABASE_PATH.exists():
            books_path = EC2_BOOKS_DATABASE_PATH
        else:
            books_path = LOCAL_BOOKS_DATABASE_PATH
        
        if EC2_ROYALTIES_HISTORY_PATH.exists():
            royalties_path = EC2_ROYALTIES_HISTORY_PATH
        else:
            royalties_path = LOCAL_ROYALTIES_HISTORY_PATH
    else:
        # Local development - use Google Drive paths
        books_path = LOCAL_BOOKS_DATABASE_PATH
        royalties_path = LOCAL_ROYALTIES_HISTORY_PATH
    
    return books_path, royalties_path

BOOKS_DATABASE_PATH, ROYALTIES_HISTORY_PATH = _get_data_paths()

# Author name normalization mapping
AUTHOR_NORMALIZATION = {
    "Rodrigue": "Shck Tchamna",
    "Shck Shck": "Shck Tchamna",
    "Shck Shck Tchamna": "Shck Tchamna",
    "Rodrigue Tchamna": "Shck Tchamna",
    "Shck Ca᷅mnà'": "Shck Tchamna",
    "Shck Cǎmnà'": "Shck Tchamna",
    "Shck CCa᷅mnà'": "Shck Tchamna",
    "Zachée Denis BITJAA  KODY": "Zachée Denis BITJAA KODY",
    "Zachee Bitjaa Kody": "Zachée Denis BITJAA KODY",
    "Pr Zachée Denis BITJAA KODY": "Zachée Denis BITJAA KODY",
    'Resulam Resulam': "Resulam",
    "Jean rene Djobia": "Tanyi Djobia René",
    "Jean René Djobia": "Tanyi Djobia René",
    "Tanyi Djobia Rene": "Tanyi Djobia René",
    'Tchamna': "Shck Tchamna",
    "Mə̂fo Gòmlù' Gòmlù' Motoum": "Mə̂fo Gòmlù' Motoum",
    "Mə̂fo Gòmlù' Motoum": "Mə̂fo Gòmlù' Motoum",  # straight apostrophe
    "Mə̂fo Gòmlù’ Motoum": "Mə̂fo Gòmlù' Motoum",  # right single quotation mark -> straight apostrophe
    "Pascaline Motoum": "Mə̂fo Gòmlù' Motoum",
    'SHCK Tchamna': "Shck Tchamna",
    "Claude Lionel Mvondo": "Claude Lionel Mvondo Edzoa",
    " Claude Lionel Mvondo Edzoa": "Claude Lionel Mvondo Edzoa",
    "Claude Mvondo Edzoa": "Claude Lionel Mvondo Edzoa",
    "IMELE TSAFACK": "Imele Tsafack",
    "Tsafack Imele": "Imele Tsafack",
    "Joseph Oyange Wajuanga": "Joseph Oyange",
    "Josephine Ndonke": "Joséphine Ndonke",
    "Joséphine Ndonke": "Joséphine Ndonke",
    "Iyo Ngobo Ekwalla": "Ngobo Ekwala",
    "Oliver Germain Tafouemewe": "Olivier Tafouemewe",
    "Gabriel Deeh Segallo": "Deeh Segallo",
    "Deeh Segallo": "Deeh Segallo",
    "Ngo Bibouth": "Martine Rosette Ngo Bibuth",
    "Martine Rosette Ngo Bibuth": "Martine Rosette Ngo Bibuth",
}

# Title normalization mapping
TITLE_NORMALIZATION = {
    "Conversation de base": "Conversations de base",
    "Guide de conversation trilingue français-anglais-yemba": 
        "Guide de conversation trilingue français-anglais-yemba: French-Yemba-English Phrasebook"
}

# Book nickname mapping for visualization
BOOK_NICKNAME_MAPPING = {
    **{f"Nùfī Attic - Le Grenier du Nùfī - KAM {i}:": "nufi_attic_interactive" for i in range(1, 9)},
    "Ntǎ' Nùfī - Nùfī Attic - Le Grenier du Nùfī (Version sans audio)": "nufi_attic_ebook",
    "Conte Africain -Fongbe: « Travaille aujourd'hui et mange demain, paresse aujourd'hui et vole demain » – January 15, 2019": "fongbe_conte_travaille_paresse",
    "Conte Africain -Fongbe: « Travaille aujourd'hui et mange demain, paresse aujourd'hui et vole demain ».": "fongbe_conte_travaille_paresse",
    "Guide de conversation trilingue Français-anglais-fe'efe'e.: French-Fè'éfě'è-English Phrasebook": "nufi_phrasebook",
    "La grammaire des langues bamilekes : cas du nufi": "nufi_grammaire",
    "La fourmi affamée : Nufi-Français: Nzhìèkǔ' mɑ̀nkō ngʉ́ngà'": "nufi_fourmi_affamee",
    "Contes africains, contes bamilekés racontés en nufi et traduits en francais (Full Color): African's fairy tales": "nufi_contes_bamilekes",
    "Conversations de base en langue fe'efe'e: Basic Conversation in Fe'efe'e Language": "nufi_conv.base",
    "Conte Bamiléké-Nufi « Travaille aujourd'hui et mange demain, paresse aujourd'hui et vole demain ».: Version Nufi-Francais": "nufi_travail_paresse",
    "Contes africains, contes bamilékés racontés en nufi et traduits en français (Black and White): African's fairy tales": "nufi_contes_bamileke_black_white",
    "Contes bamilekés racontés en medumba et traduits en français (Black and White): medumba (Bangangte) Fairy tales": "medumba_contes_bamilekes_black_white",
    "Contes bamilekés racontés en medumba et traduits en français: medumba (bangante) fairy tales": "medumba_contes_bamileke_couleur",
    "Expressions idiomatiques en langue fè'éfě'è (nùfī): Yū' mfèn pí yū' nkɑ̀ndàk mɑ̀ ghə̀ə̄ fè'éfě'è (nùfī)": "nufi_expression_idiom.",
    "Grammaire des langues bamilékés : Cas du nufi (fè'éfě'è): Sìēmbʉ́ɑ́ fè'éfě'è": "nufi_grammaire",
    "Guide de conversation (phrasebook) en langue fe'efe'e (nufi) - part I: Trilingual Phrasebook : French-English-Nufi": "nufi_phrasebook",
    "Guide de conversation trilingue français-anglais-douala: French-Duala-English Phrasebook": "duala_phrasebook",
    "Guide de conversation trilingue français-anglais-medumba: French-Medumba-English Phrasebook": "medumba_phrasebook",
    "Guide de conversation trilingue français-anglais-yemba: French-Yemba-English Phrasebook": "yemba_phrasebook",
    "La fourmi affamée: Nzhìèkǔ' mɑ̀nkō ngʉ́ngà'": "nufi_fourmi_affamee",
    "Le Grenier du Nguemba: Ntâŋ Ŋgə̂mbà : Ngemba Attic": "ngemba_grenier",
    "Syllabaire et dictionnaire visuel en langue nufi (fe'efe'e): Nkǔnjâ'wū pí mbíághəə": "nufi_syllabaire",
    "Yoruba - French - English Phrasebook: Guide de conversation Yoruba – Français - Anglais": "yoruba_phrasebook",
    "Contes africains, contes bamilekés racontés en nufi et traduits en francais: African's fairy tales, bamileke tales": "nufi_contes_bamilekes",
    "La fourmi affamée : Ŋgə̂mbà – Français: Tə́ttá pfʉ́ njjikhwu'ú": "ngemba_fourmi_affamee"
}

# Exchange rates (to USD) - HARDCODED FALLBACK
EXCHANGE_RATES_HARDCODED = {
    'EUR': 1.1,    # 1 Euro = 1.1 USD
    'JPY': 0.0073, # 1 Japanese Yen = 0.0073 USD
    'USD': 1.0,    # 1 USD = 1.0 USD
    "CAD": 0.8,    # 1 Canadian Dollar = 0.8 USD
    'GBP': 1.3,    # 1 British Pound = 1.3 USD
    "BRL": 0.2,    # 1 Brazilian Real = 0.2 USD
    "AUD": 0.7,    # 1 Australian Dollar = 0.7 USD
    "PLN": 0.25,   # 1 Polish Zloty = 0.25 USD
    "SEK": 0.1,    # 1 Swedish Krona = 0.1 USD
    "INR": 0.0126  # 1 Indian Rupee = 0.0126 USD
}

# Exchange rates configuration
USE_LIVE_RATES = True  # Set to True to fetch live rates from API
EXCHANGE_RATES = EXCHANGE_RATES_HARDCODED  # Default to hardcoded rates

# Marketplace to country mapping
MARKETPLACE_COUNTRY_MAPPING = {
    "Amazon.ca": "Canada",
    "Amazon.co.jp": "Japan",
    "Amazon.co.uk": "United Kingdom",
    "Amazon.com": "United States",
    "Amazon.com.au": "Australia",
    "Amazon.com.br": "Brazil",
    "Amazon.de": "Germany",
    "Amazon.es": "Spain",
    "Amazon.fr": "France",
    "Amazon.in": "India",
    "Amazon.it": "Italy",
    "Amazon.nl": "Netherlands",
    "Amazon.pl": "Poland",
    "Amazon.se": "Sweden",
    "CreateSpace DE": "Germany",
    "CreateSpace UK": "United Kingdom",
    "CreateSpace US": "United States"
}

# Dashboard configuration
DASHBOARD_CONFIG = {
    'title': 'Resulam Royalties Dashboard',
    'debug': True,
    'host': '0.0.0.0',
    'port': 8050,
    'adjusted_amount': 5.0,  # USD adjustment for royalties < 100
    'conversion_rate_xaf': 500  # USD to XAF conversion rate
}

# Visualization settings
VIZ_CONFIG = {
    'template': 'plotly_white',
    'color_scheme': 'plotly',
    'excluded_languages': ['Bamileke', 'Africa']
}
