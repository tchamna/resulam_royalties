from __future__ import annotations

from typing import Callable, Dict, Iterable, List, Optional, Tuple
import math
import os
import pickle
import re

import pandas as pd


TOKEN_PATTERN = re.compile(r"[a-z0-9']+")


class RagIndex:
    VERSION = 1

    def __init__(
        self,
        key_field: Optional[str],
        doc_ids: List[object],
        doc_vectors: List[Dict[str, float]],
        doc_norms: List[float],
        idf: Dict[str, float],
        meta: Dict[str, object],
    ) -> None:
        self._key_field = key_field
        self._doc_ids = doc_ids
        self._doc_vectors = doc_vectors
        self._doc_norms = doc_norms
        self._idf = idf
        self._meta = meta

    @property
    def key_field(self) -> Optional[str]:
        return self._key_field

    @property
    def meta(self) -> Dict[str, object]:
        return self._meta

    @classmethod
    def load(cls, path: str) -> "RagIndex":
        with open(path, "rb") as handle:
            payload = pickle.load(handle)
        if not isinstance(payload, dict) or payload.get("version") != cls.VERSION:
            raise ValueError("RAG index format mismatch")
        return cls(
            payload.get("key_field"),
            payload.get("doc_ids", []),
            payload.get("doc_vectors", []),
            payload.get("doc_norms", []),
            payload.get("idf", {}),
            payload.get("meta", {}),
        )

    def save(self, path: str) -> None:
        directory = os.path.dirname(path)
        if directory:
            os.makedirs(directory, exist_ok=True)
        payload = {
            "version": self.VERSION,
            "key_field": self._key_field,
            "doc_ids": self._doc_ids,
            "doc_vectors": self._doc_vectors,
            "doc_norms": self._doc_norms,
            "idf": self._idf,
            "meta": self._meta,
        }
        with open(path, "wb") as handle:
            pickle.dump(payload, handle)

    @classmethod
    def load_or_build(
        cls,
        df: pd.DataFrame,
        index_path: str,
        key_field: Optional[str],
        fields: List[str],
        normalize_fn: Callable[[str], str],
        stopwords: Iterable[str],
        min_token_len: int = 3,
    ) -> "RagIndex":
        if not fields:
            raise ValueError("No fields available for RAG indexing")

        meta = {
            "row_count": len(df),
            "key_field": key_field,
            "fields": fields,
        }

        if index_path and os.path.exists(index_path):
            try:
                existing = cls.load(index_path)
                if existing.meta.get("row_count") == meta["row_count"] and existing.meta.get("key_field") == meta["key_field"] and existing.meta.get("fields") == meta["fields"]:
                    return existing
            except Exception:
                pass

        index = cls.build(
            df,
            key_field=key_field,
            fields=fields,
            normalize_fn=normalize_fn,
            stopwords=stopwords,
            min_token_len=min_token_len,
        )
        index._meta = meta
        if index_path:
            try:
                index.save(index_path)
            except Exception:
                pass
        return index

    @classmethod
    def build(
        cls,
        df: pd.DataFrame,
        key_field: Optional[str],
        fields: List[str],
        normalize_fn: Callable[[str], str],
        stopwords: Iterable[str],
        min_token_len: int = 3,
    ) -> "RagIndex":
        records = df[fields].copy()
        if key_field and key_field not in records.columns:
            records[key_field] = df[key_field]

        stopwords_set = {token.strip() for token in stopwords}
        doc_ids: List[object] = []
        doc_vectors: List[Dict[str, float]] = []
        doc_norms: List[float] = []
        df_counts: Dict[str, int] = {}
        doc_tokens: List[List[str]] = []

        for idx, row in records.iterrows():
            parts = []
            for field in fields:
                value = row.get(field, "")
                if value is None or (isinstance(value, float) and pd.isna(value)):
                    continue
                text = str(value).strip()
                if text:
                    parts.append(text)
            joined = " ".join(parts)
            tokens = cls._tokenize(joined, normalize_fn, stopwords_set, min_token_len)
            doc_tokens.append(tokens)
            doc_id = row.get(key_field) if key_field else idx
            doc_ids.append(doc_id)
            unique_tokens = set(tokens)
            for token in unique_tokens:
                df_counts[token] = df_counts.get(token, 0) + 1

        total_docs = max(len(doc_tokens), 1)
        idf: Dict[str, float] = {}
        for token, count in df_counts.items():
            idf[token] = math.log((total_docs + 1) / (count + 1)) + 1.0

        for tokens in doc_tokens:
            tf_counts: Dict[str, int] = {}
            for token in tokens:
                tf_counts[token] = tf_counts.get(token, 0) + 1
            vec: Dict[str, float] = {}
            norm_sq = 0.0
            for token, count in tf_counts.items():
                weight = (1.0 + math.log(count)) * idf.get(token, 0.0)
                if weight <= 0.0:
                    continue
                vec[token] = weight
                norm_sq += weight * weight
            doc_vectors.append(vec)
            doc_norms.append(math.sqrt(norm_sq) if norm_sq else 0.0)

        return cls(key_field, doc_ids, doc_vectors, doc_norms, idf, {})

    @classmethod
    def _tokenize(
        cls,
        text: str,
        normalize_fn: Callable[[str], str],
        stopwords: Iterable[str],
        min_token_len: int,
    ) -> List[str]:
        normalized = normalize_fn(text)
        tokens = TOKEN_PATTERN.findall(normalized)
        return [
            token
            for token in tokens
            if token not in stopwords and len(token) >= min_token_len
        ]

    def query(
        self,
        text: str,
        top_k: int = 10,
        normalize_fn: Optional[Callable[[str], str]] = None,
        stopwords: Optional[Iterable[str]] = None,
        min_token_len: int = 3,
    ) -> List[Tuple[object, float]]:
        normalizer = normalize_fn or (lambda value: value.lower())
        stopwords_set = {token.strip() for token in stopwords} if stopwords else set()
        tokens = self._tokenize(text, normalizer, stopwords_set, min_token_len)
        if not tokens:
            return []
        tf_counts: Dict[str, int] = {}
        for token in tokens:
            if token not in self._idf:
                continue
            tf_counts[token] = tf_counts.get(token, 0) + 1

        if not tf_counts:
            return []

        q_vec: Dict[str, float] = {}
        norm_sq = 0.0
        for token, count in tf_counts.items():
            weight = (1.0 + math.log(count)) * self._idf.get(token, 0.0)
            if weight <= 0.0:
                continue
            q_vec[token] = weight
            norm_sq += weight * weight
        q_norm = math.sqrt(norm_sq) if norm_sq else 0.0
        if q_norm == 0.0:
            return []

        scores: List[Tuple[object, float]] = []
        for doc_id, doc_vec, doc_norm in zip(self._doc_ids, self._doc_vectors, self._doc_norms):
            if not doc_vec or doc_norm == 0.0:
                continue
            dot = 0.0
            for token, q_weight in q_vec.items():
                d_weight = doc_vec.get(token)
                if d_weight is not None:
                    dot += q_weight * d_weight
            if dot <= 0.0:
                continue
            score = dot / (q_norm * doc_norm)
            scores.append((doc_id, score))

        scores.sort(key=lambda item: item[1], reverse=True)
        return scores[:top_k]
