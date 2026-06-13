from dataclasses import dataclass
from pathlib import Path
import yaml

from app.core.config import settings
from app.core.logging import logger


# ── Types ──────────────────────────────────────────────────────────────────────

@dataclass
class RuleResult:
    classification:  str         # "critical" | "non_critical"
    confidence:      float       # 0.0 – 1.0
    triggered_rules: list[str]   # rule names that matched
    sdlc_phase:      str         # dominant phase
    passed:          bool        # True if heuristics classify as critical


# ── Loader ─────────────────────────────────────────────────────────────────────

def _load_rules(path: Path) -> list[dict]:
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data["rules"]


_RULES_PATH = Path(__file__).parent.parent.parent / "config" / "sdlc_rules.yaml"
_RULES      = _load_rules(_RULES_PATH)


# ── Engine ─────────────────────────────────────────────────────────────────────

def classify(text: str) -> RuleResult:
    """
    Matches normalized text against YAML-defined rules.
    Returns RuleResult with classification, confidence, phase.

    Uses recall-biased heuristics because missing critical documents is worse
    than over-classifying borderline content.
    """
    text_lower    = text.lower()
    triggered     = []
    phase_scores: dict[str, float] = {}
    total_hits    = 0

    for rule in _RULES:
        hits = [p for p in rule["patterns"] if p in text_lower]
        if hits:
            hit_count = len(hits)
            capped_hits = min(hit_count, 3)
            score = (capped_hits / 3.0) * rule["weight"]
            triggered.append({
                "name": rule["name"],
                "score": score,
                "weight": rule["weight"],
                "hits": hit_count,
            })
            phase = rule["phase"]
            phase_scores[phase] = phase_scores.get(phase, 0.0) + score
            total_hits += hit_count

    if not triggered:
        logger.info("rule_engine_no_match")
        return RuleResult(
            classification  = "non_critical",
            confidence      = 0.0,
            triggered_rules = [],
            sdlc_phase      = "general",
            passed          = False,
        )

    total_score    = sum(t["score"] for t in triggered)
    matched_weight = sum(t["weight"] for t in triggered)
    confidence     = min(total_score / matched_weight, 1.0)
    dominant_phase = max(phase_scores, key=phase_scores.get)
    rule_names     = [t["name"] for t in triggered]
    has_high_risk_rule = any(t["weight"] >= 1.8 and t["hits"] >= 1 for t in triggered)
    has_broad_signal = len(triggered) >= 2 or total_hits >= 3

    classification = (
        "critical"
        if confidence >= settings.CONFIDENCE_THRESHOLD or has_high_risk_rule or has_broad_signal
        else "non_critical"
    )
    passed = classification == "critical"

    logger.info(
        "rule_engine_done",
        classification=classification,
        confidence=round(confidence, 3),
        phase=dominant_phase,
        rules=rule_names,
        total_hits=total_hits,
    )

    return RuleResult(
        classification  = classification,
        confidence      = confidence,
        triggered_rules = rule_names,
        sdlc_phase      = dominant_phase,
        passed          = passed,
    )