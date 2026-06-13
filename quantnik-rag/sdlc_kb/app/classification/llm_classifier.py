import json
from typing import TypedDict

import vertexai
from vertexai.generative_models import GenerativeModel

from app.core.config import settings
from app.core.exceptions import ClassificationError
from app.core.logging import logger


# ── Types ──────────────────────────────────────────────────────────────────────

class ClassificationResult(TypedDict):
    classification:  str        # "critical" | "non_critical"
    confidence:      float      # 0.0 – 1.0
    sdlc_phase:      str        # requirements | design | development | testing | deployment | security | general
    reasoning:       str        # one-line explanation
    triggered_areas: list[str]  # which SDLC areas were detected


# ── Prompt ─────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """
You are an SDLC document classification expert.

Your job is to analyze a document and determine:
1. Whether it is CRITICAL or NON_CRITICAL for the software development lifecycle
2. Which SDLC phase it primarily belongs to
3. Your confidence level

CLASSIFICATION CRITERIA:

CRITICAL — document contains any of:
- Security specifications, auth flows, threat models, compliance requirements (GDPR, HIPAA, PCI etc.)
- Architecture decisions, system design, data models, API contracts
- Business or functional requirements, acceptance criteria
- Deployment configurations, infrastructure specs, CI/CD pipelines
- Domain-specific business logic unique to this product
- SLAs, NFRs, performance benchmarks
- Test strategies, test plans with coverage requirements

NON_CRITICAL — document contains:
- General meeting notes without decisions
- Boilerplate or template content
- Generic how-to guides not specific to this product
- Status updates or progress reports without technical detail
- Onboarding or HR-related content

SDLC PHASES:
- requirements  : business/functional/non-functional requirements
- design        : architecture, data models, system design
- development   : api specs, coding guidelines, technical specs
- testing       : test plans, test cases, QA strategy
- deployment    : CI/CD, infra, release plans
- security      : auth, compliance, threat models, data privacy
- general       : does not fit any specific phase

Respond ONLY in this exact JSON format with no extra text:
{
  "classification":  "critical" or "non_critical",
  "confidence":      0.0 to 1.0,
  "sdlc_phase":      "<phase>",
  "reasoning":       "<one sentence explaining why>",
  "triggered_areas": ["<area1>", "<area2>"]
}
"""


# ── Classifier ─────────────────────────────────────────────────────────────────

class LLMClassifier:

    def __init__(self):
        vertexai.init(
            project=settings.VERTEX_PROJECT_ID,
            location=settings.VERTEX_LOCATION,
        )
        self._model = GenerativeModel(
            model_name=settings.VERTEX_LLM_MODEL,
            system_instruction=_SYSTEM_PROMPT,
        )

    async def classify(self, text: str) -> ClassificationResult:
        # Use first 3000 chars — enough signal, avoids token waste
        excerpt = text[:3000].strip()

        prompt = f"Classify this document:\n\n---\n{excerpt}\n---"

        try:
            response = self._model.generate_content(prompt)
            raw = response.text.strip().replace("```json", "").replace("```", "").strip()
            result = json.loads(raw)
            self._validate(result)
            logger.info(
                "llm_classification_done",
                classification=result["classification"],
                phase=result["sdlc_phase"],
                confidence=result["confidence"],
            )
            return result

        except json.JSONDecodeError as e:
            raise ClassificationError(f"LLM returned invalid JSON: {e}")
        except Exception as e:
            raise ClassificationError(str(e))

    def _validate(self, result: dict):
        valid_classifications = {"critical", "non_critical"}
        valid_phases = {
            "requirements", "design", "development",
            "testing", "deployment", "security", "general",
        }
        if result.get("classification") not in valid_classifications:
            raise ClassificationError(f"Invalid classification: {result.get('classification')}")
        if result.get("sdlc_phase") not in valid_phases:
            result["sdlc_phase"] = "general"
        if not isinstance(result.get("confidence"), (int, float)):
            result["confidence"] = 0.5