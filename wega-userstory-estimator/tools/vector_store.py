from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from models.schemas import HistoricalStoryRecord


@dataclass(slots=True)
class SearchMatch:
    record: HistoricalStoryRecord
    score: float


class InMemoryVectorStore:
    """A lightweight TF-IDF based vector store for local development.

    The architecture allows a future pgvector or managed-vector implementation without
    changing the estimator service contract. For now, TF-IDF is sufficient, deterministic,
    and easy to run locally.
    """

    def __init__(self, records: Iterable[HistoricalStoryRecord]):
        self.records = list(records)
        self.vectorizer = TfidfVectorizer(
            ngram_range=(1, 2),
            max_features=20_000,
            stop_words="english",
            sublinear_tf=True,
        )
        corpus = [self._full_text(record) for record in self.records]
        self.matrix = self.vectorizer.fit_transform(corpus) if corpus else None

    def search(self, query_text: str, top_k: int, team_id: str | None = None) -> list[SearchMatch]:
        if self.matrix is None or not self.records:
            return []

        candidate_indices = [
            index
            for index, record in enumerate(self.records)
            if team_id is None or record.team_id == team_id
        ]
        if not candidate_indices:
            candidate_indices = list(range(len(self.records)))

        query_vector = self.vectorizer.transform([query_text])
        candidate_matrix = self.matrix[candidate_indices]
        scores = cosine_similarity(query_vector, candidate_matrix).flatten()

        ranked_indices = np.argsort(scores)[::-1]
        matches: list[SearchMatch] = []
        for position in ranked_indices[:top_k]:
            score = float(scores[position])
            if score <= 0:
                continue
            record = self.records[candidate_indices[position]]
            matches.append(SearchMatch(record=record, score=round(score, 4)))
        return matches

    @staticmethod
    def _full_text(record: HistoricalStoryRecord) -> str:
        criteria = " ".join(item.criterion for item in record.acceptance_criteria)
        return f"{record.title} {record.description} {criteria}".strip()
