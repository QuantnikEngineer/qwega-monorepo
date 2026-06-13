from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_db
from app.feedback.collector import collect
from app.schemas.feedback import FeedbackRequest, FeedbackResponse

router = APIRouter()


@router.post(
    "/feedback",
    response_model=FeedbackResponse,
    status_code=201,
    summary="Submit user feedback",
    description=(
        "Accepts three feedback types:\n\n"
        "- **rating** — positive/negative signal on an agent output (Postgres only, not indexed).\n"
        "- **correction** — a factual correction to an output (indexed to Qdrant as CRITICAL).\n"
        "- **domain_preference** — a company/domain rule the agent should follow "
        "(indexed to Qdrant as CRITICAL, surfaced via /context/enrich on next generation)."
    ),
)
async def submit_feedback(
    body: FeedbackRequest,
    db:   AsyncSession = Depends(get_db),
) -> FeedbackResponse:
    return await collect(body, db)
