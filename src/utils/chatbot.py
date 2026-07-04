from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, List, Optional, Tuple
import os
import re
import unicodedata

import pandas as pd
import requests

from .rag_index import RagIndex
from src.hardcoded_nicknames import DB_NICKNAME_TO_ROYALTY


STOPWORDS = {
    "a",
    "an",
    "the",
    "and",
    "or",
    "to",
    "of",
    "for",
    "in",
    "on",
    "about",
    "with",
    "please",
    "show",
    "find",
    "give",
    "me",
    "i",
    "want",
    "need",
    "book",
    "books",
    "what",
    "language",
    "author",
    "category",
    "genre",
    "by",
    "from",
    "most",
    "popular",
    "best",
    "top",
    "bestseller",
    "best-seller",
    "bestselling",
    "best-selling",
    "selling",
    "sell",
    "sold",
    "when",
    "was",
    "first",
    "earliest",
    "oldest",
    "publish",
    "published",
    "publication",
    "date",
    "year",
}

REPLACEMENTS = {
    "pubular": "popular",
}

FORMAT_KEYWORDS = {
    "Ebook": ["ebook", "e-book", "kindle", "digital"],
    "Paper": ["paperback", "paper back", "print"],
    "HardCover": ["hardcover", "hard cover"],
}


def normalize_text(value: str) -> str:
    if value is None or (isinstance(value, float) and pd.isna(value)):
        return ""
    text = str(value).strip().lower()
    text = unicodedata.normalize("NFD", text)
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    for wrong, right in REPLACEMENTS.items():
        text = re.sub(rf"\\b{re.escape(wrong)}\\b", right, text)
    text = re.sub(r"\s+", " ", text)
    return text


@dataclass
class ChatbotResponse:
    message: str
    results: pd.DataFrame
    filters: Dict[str, str]
    keywords: List[str]
    total_results: int
    used_llm: bool
    note: str = ""


class ChatbotEngine:
    def __init__(
        self,
        books_df: pd.DataFrame,
        enable_llm: bool = True,
        royalties_df: Optional[pd.DataFrame] = None,
    ) -> None:
        self.books_df = books_df.copy()
        self.royalties_df = royalties_df.copy() if royalties_df is not None else None
        self.db_to_royalty_nicknames = DB_NICKNAME_TO_ROYALTY
        self.royalty_to_db_nickname = {}
        for db_nick, royalty_nicks in DB_NICKNAME_TO_ROYALTY.items():
            for royalty_nick in royalty_nicks:
                self.royalty_to_db_nickname[royalty_nick] = db_nick
        llm_flag = os.getenv("CHATBOT_USE_LLM", "true").lower().strip()
        self.enable_llm = enable_llm and llm_flag not in {"0", "false", "no"}
        self.llm_provider = os.getenv("CHATBOT_LLM_PROVIDER", "ollama").lower().strip()
        self.ollama_url = os.getenv("CHATBOT_OLLAMA_URL", "http://localhost:11434").rstrip("/")
        self.ollama_model = os.getenv("CHATBOT_LLM_MODEL", "llama3.2:3b")
        self.ollama_timeout = float(os.getenv("CHATBOT_OLLAMA_TIMEOUT", "20"))
        self.result_limit = int(os.getenv("CHATBOT_RESULT_LIMIT", "12"))
        self.rag_enabled = os.getenv("CHATBOT_RAG_ENABLED", "true").lower().strip() not in {"0", "false", "no"}
        self.rag_top_k = int(os.getenv("CHATBOT_RAG_TOP_K", "30"))
        self.rag_index_path = os.getenv("CHATBOT_RAG_INDEX_PATH", "data/chatbot_rag_index.pkl")
        self.rag_index = None
        self._prepare_index()
        self._init_rag_index()

    @classmethod
    def from_csv(
        cls,
        path: str,
        enable_llm: bool = True,
        royalties_df: Optional[pd.DataFrame] = None,
    ) -> "ChatbotEngine":
        books_df = pd.read_csv(path)
        return cls(books_df, enable_llm=enable_llm, royalties_df=royalties_df)

    def _get_series(self, column: str) -> pd.Series:
        if column in self.books_df.columns:
            return self.books_df[column].fillna("")
        return pd.Series([""] * len(self.books_df))

    def _prepare_index(self) -> None:
        title_series = self._get_series("title")
        language_series = self._get_series("language_name")
        category_series = self._get_series("category")
        authors_series = self._get_series("authors")
        nickname_series = self._get_series("book_nick_name")

        self.books_df["title_norm"] = title_series.apply(normalize_text)
        self.books_df["language_norm"] = language_series.apply(normalize_text)
        self.books_df["category_norm"] = category_series.apply(normalize_text)
        self.books_df["authors_norm"] = authors_series.apply(normalize_text)
        self.books_df["nickname_norm"] = nickname_series.apply(normalize_text)
        self.books_df["combined_norm"] = (
            self.books_df["title_norm"]
            + " "
            + self.books_df["language_norm"]
            + " "
            + self.books_df["category_norm"]
            + " "
            + self.books_df["authors_norm"]
            + " "
            + self.books_df["nickname_norm"]
        )

        self.languages = sorted({str(lang).strip() for lang in language_series if str(lang).strip()})
        self.categories = sorted({str(cat).strip() for cat in category_series if str(cat).strip()})
        self.authors = sorted(self._extract_authors(authors_series))

        self._language_options = self._build_options(self.languages)
        self._category_options = self._build_options(self.categories)
        self._author_options = self._build_options(self.authors)

    def _init_rag_index(self) -> None:
        if not self.rag_enabled:
            return
        try:
            key_field = self._resolve_rag_key_field()
            fields = self._get_rag_fields()
            self.rag_index = RagIndex.load_or_build(
                self.books_df,
                index_path=self.rag_index_path,
                key_field=key_field,
                fields=fields,
                normalize_fn=normalize_text,
                stopwords=STOPWORDS,
            )
        except Exception as exc:
            print(f"Warning: RAG index disabled: {exc}")
            self.rag_index = None

    def _resolve_rag_key_field(self) -> Optional[str]:
        if "book_nick_name" in self.books_df.columns:
            return "book_nick_name"
        if "id" in self.books_df.columns:
            return "id"
        return None

    def _get_rag_fields(self) -> List[str]:
        candidates = [
            "title",
            "language_name",
            "authors",
            "category",
            "subtitle",
            "description",
            "summary",
            "keywords",
            "short_description",
            "long_description",
            "book_nick_name",
        ]
        return [field for field in candidates if field in self.books_df.columns]

    def _extract_authors(self, authors_series: pd.Series) -> List[str]:
        authors: List[str] = []
        for value in authors_series:
            if not value or (isinstance(value, float) and pd.isna(value)):
                continue
            parts = re.split(r",|;|&|\band\b", str(value))
            for part in parts:
                cleaned = part.strip()
                if cleaned:
                    authors.append(cleaned)
        return list({author for author in authors if author})

    def _build_options(self, values: List[str]) -> List[Tuple[str, str]]:
        options: List[Tuple[str, str]] = []
        for value in values:
            normalized = normalize_text(value)
            if normalized:
                options.append((normalized, value))
        options.sort(key=lambda item: len(item[0]), reverse=True)
        return options

    def _find_option(self, message_norm: str, options: List[Tuple[str, str]]) -> Optional[str]:
        for normalized, original in options:
            if normalized and normalized in message_norm:
                return original
        return None

    def _extract_format(self, message_norm: str) -> Optional[str]:
        for fmt, keywords in FORMAT_KEYWORDS.items():
            for keyword in keywords:
                if keyword in message_norm:
                    return fmt
        return None

    def _extract_author_hint(self, message_norm: str) -> Optional[str]:
        if not message_norm:
            return None
        markers = ["sold by", "by", "author", "authors", "written by"]
        for marker in markers:
            if marker in message_norm:
                _, tail = message_norm.split(marker, 1)
                tail = tail.strip()
                if not tail:
                    continue
                stop_tokens = {
                    "in",
                    "for",
                    "with",
                    "language",
                    "category",
                    "format",
                    "ebook",
                    "paperback",
                    "hardcover",
                    "books",
                    "book",
                }
                parts = tail.split()
                collected = []
                for part in parts:
                    if part in stop_tokens:
                        break
                    collected.append(part)
                hint = " ".join(collected).strip()
                if hint and hint not in STOPWORDS:
                    return hint
        return None

    def _match_author_by_keyword(self, keyword: str) -> Optional[str]:
        if not keyword:
            return None
        keyword_norm = normalize_text(keyword)
        if not keyword_norm or keyword_norm in STOPWORDS:
            return None
        for normalized, original in self._author_options:
            if keyword_norm in normalized:
                return original
        return None

    def _extract_keywords(self, message_norm: str, reserved_terms: List[str]) -> List[str]:
        reserved = set()
        for term in reserved_terms:
            if term:
                reserved.update(normalize_text(term).split())

        words = re.findall(r"[a-z0-9']+", message_norm)
        keywords = []
        for word in words:
            if word in STOPWORDS or word in reserved or len(word) < 3:
                continue
            keywords.append(word)
        return list(dict.fromkeys(keywords))

    def _is_reset_message(self, message_norm: str) -> bool:
        reset_phrases = ["reset", "start over", "clear filters", "forget", "show all"]
        return any(phrase in message_norm for phrase in reset_phrases)

    def _is_first_published_intent(self, message_norm: str) -> bool:
        if not message_norm:
            return False
        has_time_word = any(token in message_norm for token in ["when", "year", "date"])
        has_first_word = any(token in message_norm for token in ["first", "earliest", "oldest"])
        has_publish_word = any(token in message_norm for token in ["publish", "published", "publication"])
        return (has_first_word and has_publish_word) or (has_time_word and has_publish_word)

    def _is_most_popular_intent(self, message_norm: str) -> bool:
        if not message_norm:
            return False
        if "most popular" in message_norm:
            return True
        if "best seller" in message_norm or "bestseller" in message_norm:
            return True
        if "best selling" in message_norm or "bestselling" in message_norm:
            return True
        if "top selling" in message_norm or "top seller" in message_norm:
            return True
        if "most sold" in message_norm or "highest selling" in message_norm:
            return True
        if "most popular book" in message_norm or "top book" in message_norm:
            return True
        return False

    def _is_least_popular_intent(self, message_norm: str) -> bool:
        if not message_norm:
            return False
        if "least popular" in message_norm:
            return True
        if "least sold" in message_norm or "fewest sold" in message_norm:
            return True
        if "lowest selling" in message_norm or "lowest sales" in message_norm:
            return True
        if "worst selling" in message_norm or "worst seller" in message_norm:
            return True
        if "publish the least" in message_norm or "published the least" in message_norm:
            return True
        return "least" in message_norm and "popular" in message_norm

    def _extract_top_n(self, message_norm: str) -> Optional[int]:
        if not message_norm:
            return None
        match = re.search(r"\btop\s+(\d{1,2})\b", message_norm)
        if match:
            return int(match.group(1))
        if "top" in message_norm and "book" in message_norm:
            return 5
        if "most popular books" in message_norm:
            return 5
        return None

    def _extract_bottom_n(self, message_norm: str) -> Optional[int]:
        if not message_norm:
            return None
        match = re.search(r"\b(bottom|least|lowest)\s+(\d{1,2})\b", message_norm)
        if match:
            return int(match.group(2))
        if "least popular books" in message_norm:
            return 5
        if "least sold books" in message_norm or "lowest selling books" in message_norm:
            return 5
        if "least popular book" in message_norm or "least sold book" in message_norm:
            return 1
        return None

    def apply_filters(
        self,
        message: str,
        previous_filters: Optional[Dict[str, str]] = None,
        keep_previous_filters: bool = True,
    ) -> Tuple[Dict[str, str], List[str]]:
        message_norm = normalize_text(message)
        if not message_norm:
            return previous_filters or {}, []

        if self._is_reset_message(message_norm):
            return {}, []

        previous_filters = previous_filters.copy() if previous_filters else {}
        if not keep_previous_filters:
            previous_filters = {}
        extracted, keywords = self.extract_filters(message)

        for key in ["language", "category", "author", "format"]:
            value = extracted.get(key)
            if value:
                previous_filters[key] = value

        if "all languages" in message_norm or "any language" in message_norm:
            previous_filters.pop("language", None)
        if "all categories" in message_norm or "any category" in message_norm:
            previous_filters.pop("category", None)
        if "all authors" in message_norm or "any author" in message_norm:
            previous_filters.pop("author", None)

        return previous_filters, keywords

    def extract_filters(self, message: str) -> Tuple[Dict[str, Optional[str]], List[str]]:
        message_norm = normalize_text(message)
        if not message_norm:
            return {}, []

        language = self._find_option(message_norm, self._language_options)
        category = self._find_option(message_norm, self._category_options)
        author = self._find_option(message_norm, self._author_options)
        format_value = self._extract_format(message_norm)
        if not author:
            author_hint = self._extract_author_hint(message_norm)
            if author_hint:
                author = self._match_author_by_keyword(author_hint) or author_hint

        keywords = self._extract_keywords(message_norm, [language, category, author])
        return {
            "language": language,
            "category": category,
            "author": author,
            "format": format_value,
        }, keywords

    def _filter_df(self, df: pd.DataFrame, filters: Dict[str, str], keywords: List[str]) -> pd.DataFrame:
        filtered = df
        mask = pd.Series(True, index=filtered.index)

        if filters.get("language"):
            target = normalize_text(filters["language"])
            mask &= filtered["language_norm"] == target
        if filters.get("category"):
            target = normalize_text(filters["category"])
            mask &= filtered["category_norm"] == target
        if filters.get("author"):
            target = normalize_text(filters["author"])
            mask &= filtered["authors_norm"].str.contains(re.escape(target), na=False)
        if filters.get("format"):
            if filters["format"] == "Ebook":
                ebook_series = filtered["ebook"] if "ebook" in filtered.columns else pd.Series([""] * len(filtered))
                mask &= ebook_series.fillna("").astype(str).str.len() > 0
            elif filters["format"] == "Paper":
                paper_series = filtered["paperback"] if "paperback" in filtered.columns else pd.Series([""] * len(filtered))
                mask &= paper_series.fillna("").astype(str).str.len() > 0
            elif filters["format"] == "HardCover":
                hardcover_series = filtered["hard_cover"] if "hard_cover" in filtered.columns else pd.Series([""] * len(filtered))
                mask &= hardcover_series.fillna("").astype(str).str.len() > 0

        if keywords:
            pattern = "|".join(re.escape(keyword) for keyword in keywords)
            mask &= filtered["combined_norm"].str.contains(pattern, na=False)

        filtered = filtered[mask].copy()
        return self._sort_books(filtered)

    def _sort_books(self, df: pd.DataFrame) -> pd.DataFrame:
        if "year" in df.columns:
            return df.sort_values("year", ascending=False)
        if "publication_date" in df.columns:
            return df.sort_values("publication_date", ascending=False)
        if "id" in df.columns:
            return df.sort_values("id", ascending=False)
        return df

    def search_books(self, filters: Dict[str, str], keywords: List[str]) -> pd.DataFrame:
        return self._filter_df(self.books_df, filters, keywords)

    def _rag_rank_results(self, df: pd.DataFrame, message: str) -> pd.DataFrame:
        if not self.rag_index or df.empty:
            return df
        hits = self.rag_index.query(
            message,
            top_k=self.rag_top_k,
            normalize_fn=normalize_text,
            stopwords=STOPWORDS,
        )
        if not hits:
            return df

        rank_map = {doc_id: idx for idx, (doc_id, _score) in enumerate(hits)}
        key_field = self.rag_index.key_field
        ranked = df.copy()
        if key_field and key_field in ranked.columns:
            ranked["_rag_rank"] = ranked[key_field].map(rank_map)
        else:
            ranked["_rag_rank"] = [rank_map.get(idx) for idx in ranked.index]
        ranked["_orig_rank"] = range(len(ranked))
        ranked["_rag_rank"] = ranked["_rag_rank"].fillna(len(rank_map) + 1)
        ranked = ranked.sort_values(by=["_rag_rank", "_orig_rank"]).drop(columns=["_rag_rank", "_orig_rank"])
        return ranked

    def respond(
        self,
        message: str,
        previous_filters: Optional[Dict[str, str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> ChatbotResponse:
        message_norm = normalize_text(message)
        first_published_intent = self._is_first_published_intent(message_norm)
        count_authors_intent = self._is_count_authors_intent(message_norm)
        count_books_intent = self._is_count_books_intent(message_norm)
        most_popular_intent = self._is_most_popular_intent(message_norm)
        least_popular_intent = self._is_least_popular_intent(message_norm)
        top_n = self._extract_top_n(message_norm)
        bottom_n = self._extract_bottom_n(message_norm)
        keep_previous = not (count_authors_intent or count_books_intent)
        filters, keywords = self.apply_filters(
            message,
            previous_filters,
            keep_previous_filters=keep_previous,
        )
        if "year" in filters and not self._extract_year(message_norm):
            filters.pop("year", None)
        if count_authors_intent:
            keywords = []
        if count_books_intent:
            keywords = []
        if first_published_intent:
            keywords = []
        if most_popular_intent:
            keywords = []
        if least_popular_intent:
            keywords = []
        filtered = self.search_books(filters, keywords)
        total_results = len(filtered)
        display_df = filtered.head(self.result_limit)
        if not (first_published_intent or count_authors_intent or most_popular_intent or least_popular_intent):
            filtered = self._rag_rank_results(filtered, message)
            total_results = len(filtered)
            display_df = filtered.head(self.result_limit)
        filter_text = self._format_filter_text(filters, keywords)

        if total_results == 0:
            fallback = (
                f"I could not find any books matching {filter_text}. "
                "Try another language, author, or category."
            )
        elif not filters and not keywords:
            titles = self._format_titles(display_df)
            fallback = (
                "Tell me a language, author, or category. "
                f"Here are a few recent titles: {titles}."
            )
        else:
            titles = self._format_titles(display_df)
            fallback = f"I found {total_results} books matching {filter_text}. Here are a few: {titles}."

        used_llm = False
        note = ""
        response_text = fallback

        if total_results > 0 and first_published_intent:
            response_text, note = self._build_first_published_answer(filtered, filters)
        elif count_authors_intent:
            response_text, note, filtered, filters = self._build_count_authors_answer(
                filtered,
                filters,
                message_norm,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif count_books_intent:
            response_text, note, filtered, filters = self._build_count_books_answer(
                filtered,
                filters,
                message_norm,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif most_popular_intent:
            response_text, note, filtered, filters = self._build_most_popular_answer(
                filtered,
                filters,
                message_norm,
                top_n=top_n,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif least_popular_intent:
            if bottom_n is None and top_n and "least" in message_norm:
                bottom_n = top_n
            response_text, note, filtered, filters = self._build_least_popular_answer(
                filtered,
                filters,
                message_norm,
                top_n=bottom_n,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)

        if (
            not first_published_intent
            and not count_authors_intent
            and not count_books_intent
            and not most_popular_intent
            and not least_popular_intent
            and self.enable_llm
            and self.llm_provider == "ollama"
            and total_results > 0
        ):
            llm_response = self._call_ollama(message, filter_text, filtered, history)
            if llm_response:
                if self._llm_conflicts_with_results(llm_response, total_results):
                    note = "LLM response did not match results; using rules."
                else:
                    response_text = llm_response
                    used_llm = True
            else:
                note = "LLM unavailable, showing keyword-based matches."
        elif self.enable_llm and self.llm_provider not in {"ollama", "none"}:
            note = "LLM provider not configured; using keyword search."

        return ChatbotResponse(
            message=response_text,
            results=display_df,
            filters=filters,
            keywords=keywords,
            total_results=total_results,
            used_llm=used_llm,
            note=note,
        )

    def _build_first_published_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
    ) -> Tuple[str, str]:
        if filtered.empty:
            return "I could not find any matching books.", ""

        title = None
        date_label = None
        note = ""

        def clean_title(raw_title: str) -> str:
            if not raw_title:
                return ""
            text = str(raw_title).strip()
            for sep in [" - "]:
                if sep in text:
                    text = text.split(sep)[0].strip()
                    break
            return text

        if "publication_date" in filtered.columns:
            dates = pd.to_datetime(filtered["publication_date"], errors="coerce")
            if dates.notna().any():
                idx = dates.idxmin()
                title = clean_title(filtered.loc[idx].get("title", ""))
                date_value = dates.loc[idx]
                if pd.notna(date_value):
                    date_label = date_value.strftime("%B %d, %Y")

        if not title and "year" in filtered.columns:
            year_series = pd.to_numeric(filtered["year"], errors="coerce")
            if year_series.notna().any():
                min_year = int(year_series.min())
                idx = year_series[year_series == min_year].index[0]
                title = clean_title(filtered.loc[idx].get("title", ""))
                date_label = str(min_year)

        if not title:
            note = "Publication dates are missing in the catalog."
            title = clean_title(filtered.iloc[0].get("title", "")) or "a matching book"

        scope = filters.get("language") or filters.get("category") or filters.get("author") or "this selection"
        if date_label:
            response = f"The earliest {scope} book in the catalog is {title} (published {date_label})."
        else:
            response = f"The earliest {scope} book I can see is {title}."

        return response, note

    def _filter_royalties_by_year(self, df: pd.DataFrame, year: Optional[int]) -> pd.DataFrame:
        if df.empty or not year:
            return df
        if "Year Sold" in df.columns:
            year_series = pd.to_numeric(df["Year Sold"], errors="coerce")
            return df[year_series == year]
        if "Royalty Date" in df.columns:
            date_series = pd.to_datetime(df["Royalty Date"], errors="coerce")
            return df[date_series.dt.year == year]
        return df

    def _format_filter_text(self, filters: Dict[str, str], keywords: List[str]) -> str:
        parts = []
        if filters.get("year"):
            parts.append(f"year: {filters['year']}")
        if filters.get("language"):
            parts.append(f"language: {filters['language']}")
        if filters.get("category"):
            parts.append(f"category: {filters['category']}")
        if filters.get("author"):
            parts.append(f"author: {filters['author']}")
        if filters.get("format"):
            parts.append(f"format: {filters['format']}")
        if keywords:
            parts.append(f"keywords: {', '.join(keywords)}")
        return ", ".join(parts) if parts else "your request"

    def _extract_year(self, message_norm: str) -> Optional[int]:
        match = re.search(r"\b(19|20)\d{2}\b", message_norm)
        if match:
            return int(match.group(0))
        return None

    def _is_count_authors_intent(self, message_norm: str) -> bool:
        if not message_norm:
            return False
        wants_count = "how many" in message_norm or "number of" in message_norm
        mentions_author = "author" in message_norm or "authors" in message_norm
        mentions_publish = "publish" in message_norm or "published" in message_norm
        mentions_year = bool(self._extract_year(message_norm))
        return (wants_count and mentions_author) or (mentions_author and mentions_year and mentions_publish)

    def _is_count_books_intent(self, message_norm: str) -> bool:
        if not message_norm:
            return False
        wants_count = (
            "how many" in message_norm
            or "number of" in message_norm
            or "total number" in message_norm
            or "total" in message_norm
            or "count" in message_norm
        )
        mentions_books = "book" in message_norm or "books" in message_norm or "titles" in message_norm
        mentions_authors = "author" in message_norm or "authors" in message_norm
        return wants_count and mentions_books and not mentions_authors

    def _filter_by_year(self, df: pd.DataFrame, year: Optional[int]) -> pd.DataFrame:
        if not year or df.empty:
            return df
        if "year" in df.columns:
            year_series = pd.to_numeric(df["year"], errors="coerce")
            return df[year_series == year]
        if "publication_date" in df.columns:
            date_series = pd.to_datetime(df["publication_date"], errors="coerce")
            return df[date_series.dt.year == year]
        return df

    def _count_unique_authors(self, df: pd.DataFrame) -> int:
        if df.empty or "authors" not in df.columns:
            return 0
        author_series = df["authors"].fillna("")
        unique_authors = self._extract_authors(author_series)
        return len({normalize_text(author) for author in unique_authors})

    def _build_count_authors_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
        message_norm: str,
    ) -> Tuple[str, str, pd.DataFrame, Dict[str, str]]:
        year = self._extract_year(message_norm)
        scoped = self._filter_by_year(filtered, year)

        filters = filters.copy()
        if year:
            filters["year"] = str(year)

        scope = filters.get("language") or filters.get("category") or filters.get("author") or "all languages"
        count = self._count_unique_authors(scoped)

        if year:
            response = f"{count} authors published in {year} ({scope})."
        else:
            response = f"{count} authors published ({scope})."

        note = "" if count else "No matching author records found for that year."
        return response, note, scoped, filters

    def _build_count_books_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
        message_norm: str,
    ) -> Tuple[str, str, pd.DataFrame, Dict[str, str]]:
        year = self._extract_year(message_norm)
        scoped = self._filter_by_year(filtered, year)

        filters = filters.copy()
        if year:
            filters["year"] = str(year)

        scope = filters.get("language") or filters.get("category") or filters.get("author") or "all languages"
        count = len(scoped)

        if year:
            response = f"{count} books published in {year} ({scope})."
        else:
            response = f"{count} books in the catalog ({scope})."

        note = "" if count else "No matching books found for that year."
        return response, note, scoped, filters

    def _llm_conflicts_with_results(self, llm_response: str, total_results: int) -> bool:
        if total_results <= 0 or not llm_response:
            return False
        text = normalize_text(llm_response)
        phrases = [
            "could not find",
            "couldnt find",
            "couldn't find",
            "no book",
            "no books",
            "no matching",
            "not found",
            "did not find",
            "didn't find",
        ]
        return any(phrase in text for phrase in phrases)

    def _build_most_popular_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
        message_norm: str,
        top_n: Optional[int] = None,
    ) -> Tuple[str, str, pd.DataFrame, Dict[str, str]]:
        return self._build_popularity_answer(
            filtered,
            filters,
            message_norm,
            top_n=top_n,
            ascending=False,
        )

    def _build_least_popular_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
        message_norm: str,
        top_n: Optional[int] = None,
    ) -> Tuple[str, str, pd.DataFrame, Dict[str, str]]:
        return self._build_popularity_answer(
            filtered,
            filters,
            message_norm,
            top_n=top_n,
            ascending=True,
        )

    def _build_popularity_answer(
        self,
        filtered: pd.DataFrame,
        filters: Dict[str, str],
        message_norm: str,
        top_n: Optional[int] = None,
        ascending: bool = False,
    ) -> Tuple[str, str, pd.DataFrame, Dict[str, str]]:
        if self.royalties_df is None or self.royalties_df.empty:
            response = "I do not have sales data loaded to answer popularity yet."
            note = "Sales history is missing."
            return response, note, filtered, filters

        royalties = self.royalties_df.copy()
        filters = filters.copy()

        year = self._extract_year(message_norm)
        if year:
            filters["year"] = str(year)
            royalties = self._filter_royalties_by_year(royalties, year)

        if filters.get("language") and "Language" in royalties.columns:
            lang = filters["language"]
            royalties = royalties[royalties["Language"].fillna("").str.lower() == lang.lower()]

        candidate_books = self.books_df
        if filters.get("category"):
            category_norm = normalize_text(filters["category"])
            candidate_books = candidate_books[candidate_books["category_norm"] == category_norm]
        if filters.get("author"):
            author_norm = normalize_text(filters["author"])
            candidate_books = candidate_books[candidate_books["authors_norm"].str.contains(re.escape(author_norm), na=False)]

        if not candidate_books.empty:
            if "book_nick_name" in candidate_books.columns and "book_nick_name" in royalties.columns:
                db_nicknames = candidate_books["book_nick_name"].dropna().tolist()
                royalty_nicknames = set()
                for db_nick in db_nicknames:
                    royalty_nicknames.update(self.db_to_royalty_nicknames.get(db_nick, [db_nick]))
                royalties = royalties[royalties["book_nick_name"].isin(royalty_nicknames)]
            elif "title_norm" in candidate_books.columns and "Title" in royalties.columns:
                title_norms = set(candidate_books["title_norm"].dropna())
                royalties["title_norm"] = royalties["Title"].map(normalize_text)
                royalties = royalties[royalties["title_norm"].isin(title_norms)]

        if royalties.empty:
            response = "I could not find sales records for that request."
            return response, "No matching sales data found.", filtered, filters

        unit_col = None
        for candidate in ["Net Units Sold", "Units Sold"]:
            if candidate in royalties.columns:
                unit_col = candidate
                break

        if unit_col is None:
            response = "Sales data is missing unit counts for popularity."
            return response, "Units sold column missing.", filtered, filters

        group_col = "book_nick_name" if "book_nick_name" in royalties.columns else "Title"
        if group_col not in royalties.columns:
            response = "Sales data does not include book identifiers for popularity."
            return response, "Book identifier missing.", filtered, filters

        grouped = royalties.groupby(group_col)[unit_col].sum().sort_values(ascending=ascending)
        if grouped.empty:
            response = "I could not find any sales totals to rank popularity."
            return response, "No sales totals available.", filtered, filters

        top_key = grouped.index[0]
        top_units = grouped.iloc[0]
        if top_n:
            top_n = min(max(int(top_n), 1), self.result_limit)
        else:
            top_n = 1

        def clean_title(raw_title: str) -> str:
            if not raw_title:
                return ""
            text = str(raw_title).strip()
            for sep in [" - "]:
                if sep in text:
                    text = text.split(sep)[0].strip()
                    break
            return text

        title = ""
        result_books = filtered
        ranked_entries = []
        if group_col == "book_nick_name":
            mapping = (
                self.books_df.set_index("book_nick_name")["title"].to_dict()
                if "book_nick_name" in self.books_df.columns and "title" in self.books_df.columns
                else {}
            )

            def resolve_title(royalty_nick: str) -> str:
                db_nick = self.royalty_to_db_nickname.get(royalty_nick, royalty_nick)
                return clean_title(mapping.get(db_nick, royalty_nick))

            title = resolve_title(top_key)
            top_keys = grouped.head(top_n).index.tolist()

            if "book_nick_name" in self.books_df.columns:
                mapped_db = []
                for key in top_keys:
                    db_nick = self.royalty_to_db_nickname.get(key, key)
                    if db_nick not in mapped_db:
                        mapped_db.append(db_nick)
                result_books = self.books_df[self.books_df["book_nick_name"].isin(mapped_db)].copy()
                order = {key: i for i, key in enumerate(mapped_db)}
                result_books["rank"] = result_books["book_nick_name"].map(order)
                result_books = result_books.sort_values("rank").drop(columns=["rank"])

            for key, units in grouped.head(top_n).items():
                ranked_entries.append((resolve_title(key), int(units)))
        else:
            title = clean_title(top_key)
            top_titles = [normalize_text(val) for val in grouped.head(top_n).index.tolist()]
            if "title_norm" in self.books_df.columns:
                result_books = self.books_df[self.books_df["title_norm"].isin(top_titles)].copy()
            for key, units in grouped.head(top_n).items():
                ranked_entries.append((clean_title(key), int(units)))

        scope = filters.get("language") or filters.get("category") or filters.get("author") or "all languages"
        if top_n > 1 and ranked_entries:
            lines = [
                f"{idx + 1}. {entry_title} ({units:,})"
                for idx, (entry_title, units) in enumerate(ranked_entries)
            ]
            if ascending:
                response = f"Bottom {top_n} least popular books in {scope}:\n" + "\n".join(lines)
            else:
                response = f"Top {top_n} most popular books in {scope}:\n" + "\n".join(lines)
        else:
            label = "least" if ascending else "most"
            response = f"The {label} popular book in {scope} is {title} with {int(top_units):,} units sold."
        return response, "", result_books, filters

    def _format_titles(self, df: pd.DataFrame, limit: int = 5) -> str:
        titles = []
        for _, row in df.head(limit).iterrows():
            title = row.get("title", "")
            if not title:
                continue
            title_str = str(title)
            if " - " in title_str:
                title_str = title_str.split(" - ")[0].strip()
            titles.append(title_str)
        return ", ".join(titles) if titles else "some titles"

    def _build_context(self, df: pd.DataFrame, limit: int = 10) -> str:
        lines = []
        for _, row in df.head(limit).iterrows():
            title = str(row.get("title", "")).strip()
            language = str(row.get("language_name", "")).strip()
            authors = str(row.get("authors", "")).strip()
            category = str(row.get("category", "")).strip()
            if not title:
                continue
            lines.append(
                f"- {title} | Language: {language} | Category: {category} | Authors: {authors}"
            )
        return "\n".join(lines)

    def _call_ollama(
        self,
        message: str,
        filter_text: str,
        results: pd.DataFrame,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> Optional[str]:
        if not self.ollama_url:
            return None

        context = self._build_context(results)
        if not context:
            return None

        system_prompt = (
            "You are a helpful book assistant for Resulam. "
            "Answer using only the catalog context. "
            "If the catalog lacks the answer, say so. "
            "Keep responses short and friendly."
        )
        user_prompt = (
            f"User question: {message}\n"
            f"Filters: {filter_text}\n"
            f"Catalog context:\n{context}"
        )

        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            "stream": False,
            "options": {"temperature": 0.2},
        }

        try:
            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.ollama_timeout,
            )
            response.raise_for_status()
            data = response.json()
            content = data.get("message", {}).get("content", "").strip()
            return content or None
        except Exception:
            return None
