from better_profanity import profanity
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.logging import logger
from app.retrieval.qdrant_store import SearchResult


profanity.load_censor_words()

_GROUNDING_THRESHOLD = 0.15
_INSUFFICIENT_KB     = (
    "The knowledge base does not contain sufficient information to answer this. "
    "Please upload relevant SDLC documents."
)
_TOXICITY_RESPONSE   = (
    "The response was flagged. Please rephrase your query."
)


# ── Public API ─────────────────────────────────────────────────────────────────

def validate(answer: str, sources: list[SearchResult]) -> dict:
    if not sources:
        logger.warning("output_no_sources")
        return _fail(_INSUFFICIENT_KB, "No sources retrieved")

    grounding = _check_grounding(answer, sources)
    if not grounding["passed"]:
        return grounding

    toxicity = _check_toxicity(answer)
    if not toxicity["passed"]:
        return toxicity

    return _pass(answer)


# ── Checks ─────────────────────────────────────────────────────────────────────

def _check_grounding(answer: str, sources: list[SearchResult]) -> dict:
    """
    TF-IDF cosine similarity between answer and retrieved context.
    Fully offline, no external calls.
    """
    context = " ".join(s.content for s in sources)
    try:
        vectorizer = TfidfVectorizer(stop_words="english")
        matrix     = vectorizer.fit_transform([answer, context])
        score      = cosine_similarity(matrix[0], matrix[1])[0][0]

        logger.info("grounding_score", score=round(float(score), 3))

        if score < _GROUNDING_THRESHOLD:
            return _fail(
                _INSUFFICIENT_KB,
                f"Answer not grounded in retrieved context (score={score:.2f})",
            )
        return _pass(answer)
    except Exception as e:
        logger.error("grounding_check_failed", error=str(e))
        return _pass(answer)  # fail open — don't block on check error


def _check_toxicity(answer: str) -> dict:
    """
    better-profanity offline toxicity check.
    """
    if profanity.contains_profanity(answer):
        logger.warning("toxicity_detected")
        return _fail(_TOXICITY_RESPONSE, "Toxic content detected in response")
    return _pass(answer)


# ── Helpers ────────────────────────────────────────────────────────────────────

def _pass(answer: str) -> dict:
    return {"passed": True,  "answer": answer, "warning": None}

def _fail(answer: str, warning: str) -> dict:
    return {"passed": False, "answer": answer, "warning": warning}