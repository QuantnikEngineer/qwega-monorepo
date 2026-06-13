from __future__ import annotations

from dataclasses import dataclass

from estimator.features import FeatureExtractor
from models.schemas import SimilarStoryReference, StoryInput
from tools.vector_store import InMemoryVectorStore


@dataclass(slots=True)
class RetrievalResult:
    similar_stories: list[SimilarStoryReference]
    historical_anchor: float | None
    historical_variance: float
    mean_similarity: float
    max_similarity: float


class SimilarityRetrievalService:
    """Retrieve similar historical stories and compute summary anchor metrics."""

    def __init__(self, vector_store: InMemoryVectorStore, feature_extractor: FeatureExtractor):
        self.vector_store = vector_store
        self.feature_extractor = feature_extractor

    def retrieve(self, story: StoryInput, top_k: int) -> RetrievalResult:
        query_text = self.feature_extractor.story_to_text(story)
        matches = self.vector_store.search(query_text=query_text, top_k=top_k, team_id=story.team_id)
        similar = [
            SimilarStoryReference(
                story_id=match.record.story_id,
                epic_title=match.record.epic_title,
                title=match.record.title,
                story_points=match.record.story_points,
                similarity_score=match.score,
            )
            for match in matches
        ]
        if not similar:
            return RetrievalResult(
                similar_stories=[],
                historical_anchor=None,
                historical_variance=0.0,
                mean_similarity=0.0,
                max_similarity=0.0,
            )

        weights = [item.similarity_score for item in similar]
        weighted_sum = sum(item.story_points * item.similarity_score for item in similar)
        total_weight = sum(weights)
        historical_anchor = weighted_sum / total_weight if total_weight else None
        mean_similarity = sum(weights) / len(weights)
        max_similarity = max(weights)
        mean_points = sum(item.story_points for item in similar) / len(similar)
        historical_variance = sum((item.story_points - mean_points) ** 2 for item in similar) / len(similar)

        return RetrievalResult(
            similar_stories=similar,
            historical_anchor=round(historical_anchor, 2) if historical_anchor is not None else None,
            historical_variance=round(historical_variance, 4),
            mean_similarity=round(mean_similarity, 4),
            max_similarity=round(max_similarity, 4),
        )
