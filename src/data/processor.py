"""
Data loading and processing utilities
"""
import pandas as pd
import re
from typing import Dict, List, Tuple
from pathlib import Path

from ..config import (
    BOOKS_DATABASE_PATH,
    ROYALTIES_HISTORY_PATH,
    AUTHOR_NORMALIZATION,
    TITLE_NORMALIZATION,
    BOOK_NICKNAME_MAPPING,
    EXCHANGE_RATES_HARDCODED,
    USE_LIVE_RATES,
    CURRENT_YEAR
)
from ..utils.exchange_rates import get_exchange_rates


class DataLoader:
    """Handles loading of all data files"""
    
    @staticmethod
    def load_books_database(path: Path = BOOKS_DATABASE_PATH) -> pd.DataFrame:
        """Load and return books database"""
        df = pd.read_csv(path, encoding="utf-8")
        df = df.rename(columns={"title": "Title"})
        return df
    
    @staticmethod
    def load_royalties_data(path: Path = ROYALTIES_HISTORY_PATH) -> Tuple[pd.DataFrame, ...]:
        """Load all royalties sheets from Excel file"""
        combined_sales = pd.read_excel(path, sheet_name="Combined Sales")
        ebook_royalty = pd.read_excel(path, sheet_name="eBook Royalty")
        paperback_royalty = pd.read_excel(path, sheet_name="Paperback Royalty")
        hardcover_royalty = pd.read_excel(path, sheet_name="Hardcover Royalty")
        
        return combined_sales, ebook_royalty, paperback_royalty, hardcover_royalty


class DataCleaner:
    """Handles data cleaning and normalization"""
    
    @staticmethod
    def strip_and_replace_spaces(cell):
        """Strip and replace multiple spaces with single space"""
        if isinstance(cell, str):
            cell = cell.strip()
            cell = re.sub(r'\s+', ' ', cell)
        return cell
    
    @staticmethod
    def normalize_dataframe(df: pd.DataFrame) -> pd.DataFrame:
        """Apply cleaning to entire dataframe"""
        return df.map(DataCleaner.strip_and_replace_spaces)
    
    @staticmethod
    def normalize_authors(df: pd.DataFrame, column: str = 'Author Name') -> pd.DataFrame:
        """Normalize author names using the mapping"""
        df[column] = df[column].str.strip()
        df[column] = df[column].replace(AUTHOR_NORMALIZATION)
        return df
    
    @staticmethod
    def normalize_titles(df: pd.DataFrame, column: str = 'Title') -> pd.DataFrame:
        """Normalize book titles"""
        for old_title, new_title in TITLE_NORMALIZATION.items():
            df[column] = df[column].str.replace(old_title, new_title, regex=False)
        
        # Just strip whitespace - don't split on en-dash as it breaks nickname matching
        df[column] = df[column].str.strip()
        
        return df


class LanguageClassifier:
    """Classifies languages from book titles"""
    
    @staticmethod
    def classify_language(title: str) -> str:
        """Determine language from title"""
        if not isinstance(title, str):
            return title
            
        title_lower = title.lower()
        
        if "nùfī" in title_lower or "nufi" in title_lower or "fe'efe'e" in title_lower or "Nzhìèkǔ' mɑ̀nkō ngʉ́ngà'" in title:
            return "Nufi"
        elif "medumba" in title_lower:
            return "Medumba"
        elif "yemba" in title_lower:
            return "Yemba"
        elif "yoruba" in title_lower:
            return "Yoruba"
        elif "duala" in title_lower:
            return "Duala"
        elif "fongbe" in title_lower:
            return "Fongbe"
        elif "chichewa" in title_lower:
            return "Chichewa"
        elif "tshiluba" in title_lower:
            return "Tshiluba"
        elif "twi" in title_lower:
            return "Twi"
        elif "shupamom" in title_lower or "bamoun" in title_lower:
            return "Bamoun"
        elif "grenier du nguemba" in title_lower or "Ŋgə̂mbà" in title:
            return "Ngemba"
        elif "grenier du hausa" in title_lower or "grenier hausa" in title_lower:
            return "Hausa"
        else:
            return "Other"


class BookMetadataMapper:
    """Maps book metadata like nicknames and authors"""
    
    def __init__(self, books_df: pd.DataFrame):
        self.books_df = books_df
        self._create_mappings()
    
    def _create_mappings(self):
        """Create dictionaries for quick lookup"""
        self.nickname_mapping = dict(zip(
            self.books_df['Title'].tolist(),
            self.books_df['book_nick_name'].tolist()
        ))
        
        self.author_mapping = dict(zip(
            self.books_df['Title'].tolist(),
            self.books_df['authors'].tolist()
        ))
        
        self.language_mapping = dict(zip(
            self.books_df['Title'].tolist(),
            self.books_df['language_name'].tolist()
        ))

        # Precompute normalized lookups for resilient matching (language)
        self._language_lookup = {}
        for title, language in self.language_mapping.items():
            if isinstance(title, str) and isinstance(language, str):
                normalized_key = self._normalize_for_matching(title)
                self._language_lookup[normalized_key] = language
        
        # Precompute normalized nickname lookup for fuzzy matching
        self._nickname_lookup = {}
        for title, nickname in BOOK_NICKNAME_MAPPING.items():
            normalized_key = self._normalize_for_matching(title)
            self._nickname_lookup[normalized_key] = nickname
    
    def _normalize_for_matching(self, text: str) -> str:
        """Normalize text for fuzzy matching - remove accents and special chars"""
        import unicodedata
        import re
        # Normalize quotes and apostrophes BEFORE unicode normalization
        # This handles curly quotes that might be affected by NFKD
        text = text.replace('\u2018', "'")  # LEFT SINGLE QUOTATION MARK
        text = text.replace('\u2019', "'")  # RIGHT SINGLE QUOTATION MARK  
        text = text.replace('\u201C', '"')  # LEFT DOUBLE QUOTATION MARK
        text = text.replace('\u201D', '"')  # RIGHT DOUBLE QUOTATION MARK
        text = text.replace('\u00AB', '"')  # LEFT-POINTING DOUBLE ANGLE QUOTATION MARK «
        text = text.replace('\u00BB', '"')  # RIGHT-POINTING DOUBLE ANGLE QUOTATION MARK »
        text = text.replace('\u2013', '-')  # EN DASH
        text = text.replace('\u2014', '-')  # EM DASH
        text = text.replace('\u02BC', "'")  # MODIFIER LETTER APOSTROPHE
        text = text.replace('\u02B9', "'")  # MODIFIER LETTER PRIME
        text = text.replace('\u0027', "'")  # APOSTROPHE (standard)
        text = text.replace('\u2032', "'")  # PRIME
        # Normalize unicode characters
        text = unicodedata.normalize('NFKD', text)
        # Remove combining characters (accents)
        text = ''.join(c for c in text if not unicodedata.combining(c))
        # Convert to lowercase
        text = text.lower()
        # Collapse multiple spaces into single space
        text = re.sub(r'\s+', ' ', text)
        # Strip trailing punctuation (period, comma, etc.) that might cause mismatches
        text = text.strip().rstrip('.,;:!')
        return text
    
    def get_book_nickname(self, title: str) -> str:
        """Get book nickname from hardcoded mapping ONLY"""
        if not isinstance(title, str):
            return title

        title_stripped = title.strip()

        # First try exact match
        if title_stripped in BOOK_NICKNAME_MAPPING:
            return BOOK_NICKNAME_MAPPING[title_stripped]
        
        # Try normalized match for resilience against Unicode variations
        title_normalized = self._normalize_for_matching(title_stripped)
        if title_normalized in self._nickname_lookup:
            return self._nickname_lookup[title_normalized]

        # Fallback: return simplified title (not the old CSV nicknames)
        return title_stripped
    
    def get_authors(self, title: str) -> str:
        """Get authors from title with special rules"""
        if 'Guide de conversation trilingue français-anglais-yemba' in title:
            return 'Giresse Jiokeng Feutsa, Oliver Germain Tafouemewe, Shck Tchamna'
        elif "Contes bamilekés racontés en medumba et traduits en français (Black and White)" in title:
            return "Leopold Tchoumi"
        elif "Yoruba - French - English Phrasebook: Guide de conversation Yoruba – Français - Anglais" in title:
            return "Resulam, Shck Tchamna"
        elif "Le Grenier du Nguemba: Ntâŋ Ŋgə̂mbà : Ngemba Attic" in title:
            return "Deeh Segallo, Resulam, Shck Tchamna"
        elif "La fourmi affamée: Nzhìèkǔ' mɑ̀nkō ngʉ́ngà'" in title:
            return "Resulam, Shck Tchamna"
        elif "nùfī" in title.lower() or "nufi" in title.lower() or "fe'efe'e" in title.lower():
            return "Resulam, Shck Tchamna"
        else:
            return self.author_mapping.get(title, "Resulam, Shck Tchamna")

    def get_language(self, title: str) -> str:
        """Resolve language for a given title with graceful fallbacks"""
        if not isinstance(title, str):
            return "Other"

        title_stripped = title.strip()
        
        # First try exact match from language_mapping
        if title_stripped in self.language_mapping:
            lang = self.language_mapping[title_stripped]
            if isinstance(lang, str) and lang:
                return lang
        
        # Try normalized match (handles Unicode variations, extra spaces, etc.)
        title_normalized = self._normalize_for_matching(title_stripped)
        if title_normalized in self._language_lookup:
            return self._language_lookup[title_normalized]

        # Fallback to keyword-based classification
        return LanguageClassifier.classify_language(title_stripped)


class RoyaltiesProcessor:
    """Process royalties data with calculations"""
    
    @staticmethod
    def count_authors(authors_str: str) -> int:
        """Count number of authors in comma-separated string"""
        if not isinstance(authors_str, str):
            return 1
        if "resulam" in authors_str.lower():
            return len(authors_str.split(","))
        else:
            return len(authors_str.split(",")) + 1
    
    @staticmethod
    def convert_to_usd(row: pd.Series, exchange_rates: Dict[str, float]) -> float:
        """Convert royalty to USD using exchange rates"""
        return row['Royalty'] * exchange_rates.get(row['Currency'], 1.0)
    
    @staticmethod
    def categorize_book_type(isbn: str, ebook_list: List, paper_list: List, hardcover_list: List) -> str:
        """Categorize book type from ISBN/ASIN"""
        isbn_str = str(isbn)
        if isbn_str in paper_list:
            return "Paper"
        elif isbn_str in hardcover_list:
            return "HardCover"
        elif isbn_str in ebook_list:
            return "Ebook"
        else:
            return "Unknown"
    
    @staticmethod
    def process_royalties(df: pd.DataFrame, mapper: BookMetadataMapper,
                         ebook_list: List, paper_list: List, hardcover_list: List,
                         exchange_rates: Dict[str, float] = None) -> pd.DataFrame:
        """Complete processing pipeline for royalties data"""
        
        if exchange_rates is None:
            exchange_rates = get_exchange_rates(
                use_live=USE_LIVE_RATES,
                hardcoded_fallback=EXCHANGE_RATES_HARDCODED
            )
        
        # Language is already set from books database via mapper.get_language()
        # No need to overwrite with LanguageClassifier
        
        # Count authors
        df['Authors Count'] = df['Authors'].apply(RoyaltiesProcessor.count_authors)
        
        # Convert to USD
        df['Royalty USD'] = df.apply(
            lambda row: RoyaltiesProcessor.convert_to_usd(row, exchange_rates),
            axis=1
        )
        
        # Calculate royalty per author
        df['Royalty per Author (USD)'] = df['Royalty USD'] / df['Authors Count']
        
        # Categorize book type
        df['BookType'] = df['ASIN/ISBN'].apply(
            lambda x: RoyaltiesProcessor.categorize_book_type(
                x, ebook_list, paper_list, hardcover_list
            )
        )
        
        # Add year sold column
        df['Year Sold'] = pd.to_datetime(df['Royalty Date']).dt.year
        
        return df
    
    @staticmethod
    def explode_authors(df: pd.DataFrame) -> pd.DataFrame:
        """Explode authors into separate rows for individual analysis"""
        df['Authors_Exploded'] = df['Authors'].str.strip().str.split(',')
        df_exploded = df.explode('Authors_Exploded')
        df_exploded['Authors_Exploded'] = df_exploded['Authors_Exploded'].str.strip()
        df_exploded['Authors_Exploded'] = df_exploded['Authors_Exploded'].replace(AUTHOR_NORMALIZATION)
        return df_exploded


def load_and_process_all_data() -> Dict[str, pd.DataFrame]:
    """
    Main function to load and process all data
    Returns dictionary with processed dataframes
    """
    # Load data
    books_df = DataLoader.load_books_database()
    sell_history, ebook_df, paper_df, hardcover_df = DataLoader.load_royalties_data()
    
    # Clean books database
    books_df = DataCleaner.normalize_titles(books_df)
    books_df['authors'] = books_df['authors'].str.strip()
    books_df['authors'] = books_df['authors'].replace(AUTHOR_NORMALIZATION)
    
    # Strip date suffix from books database titles (e.g., " – June 23, 2015")
    # This helps match with royalties titles that don't have dates
    import re
    date_pattern = r'\.?\s*[–-]\s*(?:January|February|March|April|May|June|July|August|September|October|November|December)\s+\d{1,2},?\s+\d{4}\.?,?\s*$'
    books_df['Title'] = books_df['Title'].str.replace(date_pattern, '', regex=True).str.strip()
    
    # Get unique ISBNs/ASINs
    ebook_list = ebook_df["ASIN"].unique().tolist()
    paper_list = [str(x) for x in paper_df["ISBN"].unique().tolist()]
    hardcover_list = [str(x) for x in hardcover_df["ISBN"].unique().tolist()]
    
    # Clean and normalize sell history
    sell_history = DataCleaner.normalize_dataframe(sell_history)
    sell_history = DataCleaner.normalize_titles(sell_history)
    sell_history = DataCleaner.normalize_authors(sell_history)
    
    # Create mapper
    mapper = BookMetadataMapper(books_df)
    
    # First, add the new columns to sell_history
    sell_history['book_nick_name'] = sell_history['Title'].apply(mapper.get_book_nickname)
    sell_history['Authors'] = sell_history['Title'].apply(mapper.get_authors)
    sell_history['Language'] = sell_history['Title'].apply(mapper.get_language)
    
    # Select columns of interest
    columns_of_interest = [
        "Royalty Date", "Title", "ASIN/ISBN", "Language", "book_nick_name",
        "Authors", "Units Sold", "Units Refunded", "Net Units Sold",
        "Marketplace", "Royalty Type", "Transaction Type", "Royalty", "Currency"
    ]
    
    # Process royalties
    royalties_history = sell_history[columns_of_interest].copy()
    royalties_history = RoyaltiesProcessor.process_royalties(
        royalties_history, mapper, ebook_list, paper_list, hardcover_list
    )
    
    # Explode authors for individual analysis
    royalties_exploded = RoyaltiesProcessor.explode_authors(royalties_history)
    
    return {
        'books': books_df,
        'royalties_history': royalties_history,
        'royalties_exploded': royalties_exploded,
        'ebook_list': ebook_list,
        'paper_list': paper_list,
        'hardcover_list': hardcover_list
    }
