import re
from presidio_analyzer import AnalyzerEngine, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider
from presidio_anonymizer import AnonymizerEngine
from presidio_anonymizer.entities import OperatorConfig
from app.core.exceptions import GuardrailViolationError
from app.core.logging import logger


# ── Presidio Setup ─────────────────────────────────────────────────────────────

_nlp_provider = NlpEngineProvider(nlp_configuration={
    "nlp_engine_name": "spacy",
    "models": [{"lang_code": "en", "model_name": "en_core_web_sm"}],
})
_analyzer   = AnalyzerEngine(nlp_engine=_nlp_provider.create_engine())
_anonymizer = AnonymizerEngine()

_BLOCKED_ENTITIES = [
    "CREDIT_CARD",
    "US_SSN",
    "PHONE_NUMBER",
    "US_PASSPORT",
    "IP_ADDRESS",
    "IBAN_CODE",
    "US_BANK_NUMBER",
    "MEDICAL_LICENSE",
]

# ── Injection Patterns ─────────────────────────────────────────────────────────

_INJECTION_PATTERNS = [
    r"ignore\s+((?:all|previous|above)\s+)*instructions",
    r"you are now",
    r"forget (everything|your instructions)",
    r"act as (a|an)",
    r"jailbreak",
    r"dan mode",
    r"disregard your",
    r"bypass your",
    r"override (your|all) (instructions|rules)",
    r"pretend you (are|have no)",
    r"simulate (a|an)",
]

# ── Public API ─────────────────────────────────────────────────────────────────

def validate(query: str) -> str:
    _check_basic(query)
    query = _check_pii(query)
    _check_injection(query)
    return query.strip()


# ── Checks ─────────────────────────────────────────────────────────────────────

def _check_basic(query: str):
    if not query or not query.strip():
        raise GuardrailViolationError("INPUT", "Query cannot be empty")
    if len(query) > 1000:
        raise GuardrailViolationError("INPUT", "Query exceeds 1000 character limit")


def _check_pii(query: str) -> str:
    results: list[RecognizerResult] = _analyzer.analyze(
        text=query,
        entities=_BLOCKED_ENTITIES,
        language="en",
    )

    high_confidence = [r for r in results if r.score >= 0.75]

    if high_confidence:
        detected = list({r.entity_type for r in high_confidence})
        logger.warning("pii_detected", entities=detected)
        raise GuardrailViolationError(
            "INPUT",
            f"Query contains sensitive information: {', '.join(detected)}. Remove it before querying.",
        )

    # Redact lower confidence hits
    if results:
        anonymized = _anonymizer.anonymize(
            text=query,
            analyzer_results=results,
            operators={
                entity: OperatorConfig("replace", {"new_value": f"<{entity}>"})
                for entity in _BLOCKED_ENTITIES
            },
        )
        logger.info("pii_redacted", count=len(results))
        return anonymized.text

    return query


def _check_injection(query: str):
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, query, re.IGNORECASE):
            logger.warning("injection_detected", pattern=pattern)
            raise GuardrailViolationError(
                "INPUT",
                "Prompt injection attempt detected",
            )
