from __future__ import annotations

import json
import os
import re
from typing import Dict, List, Optional

import pandas as pd

from .chatbot import ChatbotEngine, ChatbotResponse, normalize_text


DEFAULT_SYSTEM_PROMPT = (
    "You are a routing assistant for a book catalog. "
    "Return JSON only with fields: "
    "intent (search|most_popular|least_popular|count_authors|count_books|first_published|reset), "
    "language, category, author, format, year, top_n, keywords, reset_filters. "
    "Use null when unknown. keywords must be a JSON array of strings. "
    "If the user asks for top N, set top_n. "
    "Use most_popular only when the user asks about popularity, best sellers, or most sold. "
    "If the user asks for least popular or lowest sales, set intent=least_popular. "
    "If the user asks for how many books or total books, set intent=count_books. "
    "If the user asks to reset or show all, set intent=reset and reset_filters=true."
)


class LLMChatbotEngine(ChatbotEngine):
    def __init__(
        self,
        books_df: pd.DataFrame,
        enable_llm: bool = True,
        royalties_df: Optional[pd.DataFrame] = None,
    ) -> None:
        super().__init__(books_df, enable_llm=enable_llm, royalties_df=royalties_df)
        self.system_prompt = os.getenv("CHATBOT_LLM_SYSTEM_PROMPT", DEFAULT_SYSTEM_PROMPT)

    @classmethod
    def from_csv(
        cls,
        path: str,
        enable_llm: bool = True,
        royalties_df: Optional[pd.DataFrame] = None,
    ) -> "LLMChatbotEngine":
        books_df = pd.read_csv(path)
        return cls(books_df, enable_llm=enable_llm, royalties_df=royalties_df)

    def _call_ollama_json(self, message: str) -> Optional[Dict[str, object]]:
        if not self.enable_llm or self.llm_provider != "ollama":
            return None

        payload = {
            "model": self.ollama_model,
            "messages": [
                {"role": "system", "content": self.system_prompt},
                {"role": "user", "content": message},
            ],
            "stream": False,
            "options": {"temperature": 0.1},
        }

        try:
            import requests

            response = requests.post(
                f"{self.ollama_url}/api/chat",
                json=payload,
                timeout=self.ollama_timeout,
            )
            response.raise_for_status()
            content = response.json().get("message", {}).get("content", "")
        except Exception:
            return None

        return self._parse_json(content)

    def _parse_json(self, content: str) -> Optional[Dict[str, object]]:
        if not content:
            return None
        content = content.strip()
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            pass

        match = re.search(r"\{.*\}", content, re.DOTALL)
        if not match:
            return None
        try:
            return json.loads(match.group(0))
        except json.JSONDecodeError:
            return None

    def _coerce_int(self, value: object) -> Optional[int]:
        if value is None:
            return None
        if isinstance(value, int):
            return value
        try:
            return int(str(value))
        except (TypeError, ValueError):
            return None

    def respond(
        self,
        message: str,
        previous_filters: Optional[Dict[str, str]] = None,
        history: Optional[List[Dict[str, str]]] = None,
    ) -> ChatbotResponse:
        payload = self._call_ollama_json(message)
        if payload is None:
            fallback = super().respond(message, previous_filters, history)
            notice = "LLM unavailable; using rules."
            if fallback.note:
                fallback.note = f"{notice} {fallback.note}"
            else:
                fallback.note = notice
            return fallback

        intent = (payload.get("intent") or "search").strip().lower()
        reset_filters = bool(payload.get("reset_filters"))
        if intent == "reset":
            reset_filters = True

        filters: Dict[str, str] = {}
        if not reset_filters and previous_filters:
            filters.update(previous_filters)

        for key in ["language", "category", "author", "format"]:
            value = payload.get(key)
            if isinstance(value, str) and value.strip():
                filters[key] = value.strip()

        year_value = self._coerce_int(payload.get("year"))
        if year_value:
            filters["year"] = str(year_value)

        keywords = payload.get("keywords") if isinstance(payload.get("keywords"), list) else []
        keywords = [str(k).strip() for k in keywords if str(k).strip()]

        message_norm = normalize_text(message)
        if "year" in filters and not self._extract_year(message_norm):
            filters.pop("year", None)

        extracted_filters, extracted_keywords = self.extract_filters(message)
        for key in ["language", "category", "author", "format"]:
            if key not in filters and extracted_filters.get(key):
                filters[key] = extracted_filters[key]
        if not keywords and extracted_keywords:
            keywords = extracted_keywords

        count_books_intent = self._is_count_books_intent(message_norm)
        count_authors_intent = self._is_count_authors_intent(message_norm)
        first_published_intent = self._is_first_published_intent(message_norm)

        if intent == "most_popular" and not self._is_most_popular_intent(message_norm):
            intent = "search"
        elif intent == "least_popular" and not self._is_least_popular_intent(message_norm):
            intent = "search"
        elif intent == "count_authors" and not count_authors_intent:
            intent = "count_books" if count_books_intent else "search"
        elif intent == "count_books" and not count_books_intent:
            intent = "search"
        elif intent == "first_published" and not first_published_intent:
            intent = "search"
        filtered = self.search_books(filters, keywords)
        total_results = len(filtered)
        display_df = filtered.head(self.result_limit)
        if intent == "search":
            filtered = self._rag_rank_results(filtered, message)
            total_results = len(filtered)
            display_df = filtered.head(self.result_limit)

        response_text = ""
        note = ""
        used_llm = True

        if intent == "first_published":
            response_text, note = self._build_first_published_answer(filtered, filters)
        elif intent == "count_authors":
            response_text, note, filtered, filters = self._build_count_authors_answer(
                filtered,
                filters,
                message_norm,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif intent == "count_books":
            response_text, note, filtered, filters = self._build_count_books_answer(
                filtered,
                filters,
                message_norm,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif intent == "most_popular":
            top_n = self._coerce_int(payload.get("top_n"))
            response_text, note, filtered, filters = self._build_most_popular_answer(
                filtered,
                filters,
                message_norm,
                top_n=top_n,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        elif intent == "least_popular":
            top_n = self._coerce_int(payload.get("top_n"))
            response_text, note, filtered, filters = self._build_least_popular_answer(
                filtered,
                filters,
                message_norm,
                top_n=top_n,
            )
            display_df = filtered.head(self.result_limit)
            total_results = len(filtered)
        else:
            filter_text = self._format_filter_text(filters, keywords)
            if total_results == 0:
                response_text = (
                    f"I could not find any books matching {filter_text}. "
                    "Try another language, author, or category."
                )
            else:
                llm_response = self._call_ollama(message, filter_text, filtered, history)
                if llm_response:
                    if self._llm_conflicts_with_results(llm_response, total_results):
                        titles = self._format_titles(display_df)
                        response_text = f"I found {total_results} books matching {filter_text}. Here are a few: {titles}."
                        used_llm = False
                        note = "LLM response did not match results; using rules."
                    else:
                        response_text = llm_response
                else:
                    titles = self._format_titles(display_df)
                    response_text = f"I found {total_results} books matching {filter_text}. Here are a few: {titles}."
                    used_llm = False

        return ChatbotResponse(
            message=response_text,
            results=display_df,
            filters=filters,
            keywords=keywords,
            total_results=total_results,
            used_llm=used_llm,
            note=note,
        )
