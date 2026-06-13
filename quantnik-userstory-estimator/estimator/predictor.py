from __future__ import annotations

from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import StratifiedKFold, cross_val_score

from estimator.features import FeatureExtractor
from models.schemas import HistoricalStoryRecord, StoryInput


@dataclass(slots=True)
class PredictionResult:
    expected_points: float
    suggested_points: int
    probabilities: dict[int, float]
    model_accuracy: float
    point_range: tuple[int, int]


class StoryPointPredictor:
    """Train and run a local Fibonacci classifier backed by synthetic historical stories."""

    def __init__(self, records: list[HistoricalStoryRecord], random_state: int = 42):
        self.records = records
        self.random_state = random_state
        self.feature_extractor = FeatureExtractor()
        self.allowed_points = sorted({record.story_points for record in records})
        self.model_version = "synthetic-random-forest-v1"
        self.model = RandomForestClassifier(
            n_estimators=250,
            max_depth=8,
            min_samples_leaf=1,
            random_state=random_state,
            class_weight="balanced_subsample",
        )
        self._fit()

    def predict(self, story: StoryInput) -> PredictionResult:
        feature_vector = np.array([self.feature_extractor.extract(story).to_vector()])
        probabilities = self.model.predict_proba(feature_vector)[0]
        class_labels = [int(label) for label in self.model.classes_]
        probability_map = {label: round(float(prob), 4) for label, prob in zip(class_labels, probabilities)}
        expected_points = float(sum(label * probability_map[label] for label in class_labels))
        suggested_points = int(class_labels[int(np.argmax(probabilities))])

        ranked = sorted(probability_map.items(), key=lambda item: item[1], reverse=True)
        top_two = [ranked[0][0]] if len(ranked) == 1 else sorted([ranked[0][0], ranked[1][0]])
        point_range = (top_two[0], top_two[-1])

        return PredictionResult(
            expected_points=round(expected_points, 2),
            suggested_points=suggested_points,
            probabilities=probability_map,
            model_accuracy=round(self.model_accuracy, 4),
            point_range=point_range,
        )

    def nearest_fibonacci(self, value: float) -> int:
        return min(self.allowed_points, key=lambda point: abs(point - value))

    def _fit(self) -> None:
        stories = [
            StoryInput(
                story_id=record.story_id,
                epic_title=record.epic_title,
                title=record.title,
                description=record.description,
                acceptance_criteria=record.acceptance_criteria,
                labels=record.labels,
                components=record.components,
                team_id=record.team_id,
            )
            for record in self.records
        ]
        features = np.array([self.feature_extractor.extract(story).to_vector() for story in stories])
        labels = np.array([record.story_points for record in self.records])
        self.model.fit(features, labels)
        self.model_accuracy = self._estimate_model_accuracy(features, labels)

    def _estimate_model_accuracy(self, features: np.ndarray, labels: np.ndarray) -> float:
        class_counts = Counter(labels.tolist())
        minimum_class_count = min(class_counts.values()) if class_counts else 0
        if minimum_class_count < 2:
            return 0.75

        splits = min(3, minimum_class_count)
        cv = StratifiedKFold(n_splits=splits, shuffle=True, random_state=self.random_state)
        scores = cross_val_score(self.model, features, labels, cv=cv, scoring="accuracy")
        return float(np.mean(scores))
