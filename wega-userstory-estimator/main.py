import logging
import os
from logging.handlers import RotatingFileHandler
from pathlib import Path

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from estimator.service import StoryEstimationService
from models.schemas import EstimateStoriesRequest, EstimateStoriesResponse, HealthResponse

load_dotenv()

LOG_DIR = Path("logs")
LOG_DIR.mkdir(exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        RotatingFileHandler(LOG_DIR / "app.log", maxBytes=10 * 1024 * 1024, backupCount=5),
        logging.StreamHandler(),
    ],
)

logger = logging.getLogger(__name__)
service = StoryEstimationService()

app = FastAPI(
    title="WEGA User Story Estimator API",
    description="Estimate story points from direct story payloads using retrieval, ML scoring, and explainable output.",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    """Return a lightweight health response with model and explainer state."""
    return HealthResponse(
        status="healthy",
        service="WEGA User Story Estimator",
        model_version=service.predictor.model_version,
        synthetic_history_enabled=service.synthetic_history_enabled,
        gemini_explanations_enabled=service.explainer.gemini_enabled,
    )


@app.get("/sample-estimation-request", tags=["Samples"])
async def sample_estimation_request() -> dict:
    """Return a ready-to-use direct payload for local testing without orchestrators."""
    return service.load_sample_request()


@app.post("/estimate-story-points", response_model=EstimateStoriesResponse, tags=["Estimation"])
async def estimate_story_points(payload: EstimateStoriesRequest) -> EstimateStoriesResponse:
    """Estimate story points for direct story and epic payloads.

    The service accepts direct epics and stories because orchestrators are not available
    in the local environment. Incoming payloads are normalized into a consistent internal
    structure before retrieval, scoring, and explanation are applied.
    """
    try:
        return await service.estimate(payload)
    except ValueError as exc:
        logger.warning("Invalid estimation request: %s", exc)
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    except Exception as exc:  # noqa: BLE001
        logger.exception("Estimation failed: %s", exc)
        raise HTTPException(status_code=500, detail=f"Estimation failed: {exc}") from exc


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=int(os.getenv("PORT", "8080")),
        reload=True,
    )
