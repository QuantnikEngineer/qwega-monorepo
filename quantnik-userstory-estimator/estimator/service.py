from __future__ import annotations

import os
from pathlib import Path

from estimator.agent import EnterpriseExplainer, ExplanationRequest
from estimator.predictor import StoryPointPredictor
from estimator.retrieval import SimilarityRetrievalService
from estimator.rules import RuleEngine
from models.schemas import (
    EpicInput,
    EstimateStoriesRequest,
    EstimateStoriesResponse,
    EstimatedEpic,
    EstimatedStory,
    EstimationBreakdown,
    StoryInput,
)
from tools.history_loader import HistoryLoader
from tools.registrar import RegistrationService
from tools.vector_store import InMemoryVectorStore
from estimator.features import FeatureExtractor


class StoryEstimationService:
    """Application service orchestrating retrieval, scoring, and explainability."""

    def __init__(self) -> None:
        data_dir = Path(__file__).resolve().parent.parent / "data"
        self.synthetic_history_enabled = os.getenv("ENABLE_SYNTHETIC_HISTORY", "true").lower() == "true"
        self.history_loader = HistoryLoader(data_dir=data_dir)
        history = self.history_loader.load_synthetic_history() if self.synthetic_history_enabled else []
        self.feature_extractor = FeatureExtractor()
        self.vector_store = InMemoryVectorStore(history)
        self.retrieval = SimilarityRetrievalService(self.vector_store, self.feature_extractor)
        self.predictor = StoryPointPredictor(history, random_state=int(os.getenv("MODEL_RANDOM_STATE", "42")))
        self.rule_engine = RuleEngine()
        self.explainer = EnterpriseExplainer()
        self.registrar = RegistrationService()

    async def estimate(self, payload: EstimateStoriesRequest) -> EstimateStoriesResponse:
        estimated_epics: list[EstimatedEpic] = []
        loose_story_results: list[EstimatedStory] = []

        for epic in payload.epics:
            estimated_stories = [
                await self._estimate_story(story=story, epic_title=epic.epic_title, top_k=payload.top_k_similar)
                for story in epic.user_stories
            ]
            estimated_epics.append(
                EstimatedEpic(
                    epic_title=epic.epic_title,
                    epic_description=epic.epic_description,
                    user_stories=estimated_stories,
                )
            )

        if payload.stories:
            synthetic_epic = EpicInput(epic_title="Ungrouped Stories", user_stories=payload.stories)
            estimated_stories = [
                await self._estimate_story(story=story, epic_title=synthetic_epic.epic_title, top_k=payload.top_k_similar)
                for story in synthetic_epic.user_stories
            ]
            estimated_epics.append(EstimatedEpic(epic_title=synthetic_epic.epic_title, user_stories=estimated_stories))
            loose_story_results = estimated_stories

        total_story_count = sum(len(epic.user_stories) for epic in estimated_epics)
        average_points = 0.0
        if total_story_count:
            all_points = [story.estimated_story_points for epic in estimated_epics for story in epic.user_stories]
            average_points = sum(all_points) / len(all_points)

        summary = (
            f"Estimated {total_story_count} stories across {len(estimated_epics)} epic groups. "
            f"Average estimated size: {average_points:.1f} points."
        )

        return EstimateStoriesResponse(
            status="success",
            summary=summary,
            epics=estimated_epics,
            stories=loose_story_results,
            synthetic_history_used=self.synthetic_history_enabled,
            model_version=self.predictor.model_version,
        )

    def load_sample_request(self) -> dict:
        return self.history_loader.load_sample_request()

    async def _estimate_story(self, story: StoryInput, epic_title: str, top_k: int) -> EstimatedStory:
        retrieval_result = self.retrieval.retrieve(story=story, top_k=top_k)
        prediction_result = self.predictor.predict(story)
        rule_result = self.rule_engine.apply(story)

        final_numeric_score = self._combine_scores(
            historical_anchor=retrieval_result.historical_anchor,
            mean_similarity=retrieval_result.mean_similarity,
            historical_variance=retrieval_result.historical_variance,
            model_expected_points=prediction_result.expected_points,
            rule_adjustment=rule_result.adjustment,
        )
        estimated_story_points = self.predictor.nearest_fibonacci(final_numeric_score)
        confidence_score = self._calculate_confidence(
            model_accuracy=prediction_result.model_accuracy,
            retrieval_mean_similarity=retrieval_result.mean_similarity,
            retrieval_variance=retrieval_result.historical_variance,
            top_probability=max(prediction_result.probabilities.values()),
            has_acceptance_criteria=bool(story.acceptance_criteria),
            flag_count=len(rule_result.flags),
        )
        confidence = self._to_confidence_band(confidence_score)

        explanation = await self.explainer.explain(
            ExplanationRequest(
                story=story,
                estimate=estimated_story_points,
                confidence=confidence,
                confidence_score=confidence_score,
                flags=rule_result.flags,
                historical_anchor=retrieval_result.historical_anchor,
                model_expected_points=prediction_result.expected_points,
                similar_stories=retrieval_result.similar_stories,
            )
        )

        return EstimatedStory(
            story_id=story.story_id or story.title.lower().replace(" ", "-")[:48],
            epic_title=epic_title,
            title=story.title,
            description=story.description,
            acceptance_criteria=story.acceptance_criteria,
            estimated_story_points=estimated_story_points,
            confidence=confidence,
            confidence_score=confidence_score,
            point_range=list(prediction_result.point_range),
            flags=rule_result.flags,
            rationale=explanation.rationale,
            clarifying_questions=list(dict.fromkeys(rule_result.clarifying_questions + explanation.clarifying_questions)),
            similar_stories=retrieval_result.similar_stories,
            breakdown=EstimationBreakdown(
                historical_anchor=retrieval_result.historical_anchor,
                ml_expected_points=prediction_result.expected_points,
                rule_adjustment=rule_result.adjustment,
                final_numeric_score=round(final_numeric_score, 2),
                model_accuracy=prediction_result.model_accuracy,
                model_version=self.predictor.model_version,
            ),
        )

    @staticmethod
    def _combine_scores(
        historical_anchor: float | None,
        mean_similarity: float,
        historical_variance: float,
        model_expected_points: float,
        rule_adjustment: float,
    ) -> float:
        if historical_anchor is None:
            return (0.85 * model_expected_points) + (0.15 * rule_adjustment)

        similarity_boost = min(0.2, mean_similarity * 0.25)
        variance_penalty = min(0.15, historical_variance / 30.0)
        retrieval_weight = max(0.30, 0.50 + similarity_boost - variance_penalty)
        rule_weight = 0.10
        model_weight = 1.0 - retrieval_weight - rule_weight
        return (
            retrieval_weight * historical_anchor
            + model_weight * model_expected_points
            + rule_weight * rule_adjustment
        )

    @staticmethod
    def _calculate_confidence(
        model_accuracy: float,
        retrieval_mean_similarity: float,
        retrieval_variance: float,
        top_probability: float,
        has_acceptance_criteria: bool,
        flag_count: int,
    ) -> float:
        confidence = (
            top_probability * 0.35
            + retrieval_mean_similarity * 0.30
            + model_accuracy * 0.20
            + (0.10 if has_acceptance_criteria else 0.0)
            + max(0.0, 0.10 - min(0.10, retrieval_variance / 20.0))
        )
        confidence -= min(0.15, flag_count * 0.03)
        return round(max(0.0, min(1.0, confidence)), 4)

    @staticmethod
    def _to_confidence_band(confidence_score: float) -> str:
        if confidence_score >= 0.75:
            return "HIGH"
        if confidence_score >= 0.50:
            return "MEDIUM"
        return "LOW"
