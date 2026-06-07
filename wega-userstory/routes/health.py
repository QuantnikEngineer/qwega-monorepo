from fastapi import APIRouter

from .support import logger


router = APIRouter()


@router.get(
    "/health",
    tags=["Health"],
    summary="Health check endpoint",
    description="Check if the API is running and healthy",
    response_description="Health status"
)
async def health():
    logger.debug("Health check requested")
    return {
        "status": "healthy",
        "agent": "user_story_agent"
    }