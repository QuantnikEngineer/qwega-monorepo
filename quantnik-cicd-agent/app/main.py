from fastapi import FastAPI, HTTPException

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
from app.models.requests import GeneratePipelineRequest, create_sample_request
from app.models.responses import CatalogResponse, GeneratePipelineResponse, HealthResponse
from app.services.pipeline_guardrails import PipelineValidationError
from app.services.pipeline_renderers import PipelineRenderError
from app.services.pipeline_service import CiPipelineService

setup_logging(settings.log_level)
logger = get_logger(__name__)
service = CiPipelineService()

app = FastAPI(
    title="Quantnik CI Agent",
    description="Generate enterprise CI pipelines from structured intent payloads.",
    version=settings.app_version,
)


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health() -> HealthResponse:
    return HealthResponse(
        status="healthy",
        service=settings.app_name,
        version=settings.app_version,
        template_count=service.template_count,
        supported_platforms=service.supported_platforms,
    )


@app.get("/v1/catalog", response_model=CatalogResponse, tags=["Catalog"])
async def catalog() -> CatalogResponse:
    logger.info("Catalog requested")
    return service.get_catalog()


@app.get("/v1/sample-request", tags=["Samples"])
async def sample_request() -> dict:
    logger.info("Sample request requested")
    return create_sample_request().model_dump(mode="json")


@app.post("/v1/pipelines/generate", response_model=GeneratePipelineResponse, tags=["Pipelines"])
async def generate_pipeline(request: GeneratePipelineRequest) -> GeneratePipelineResponse:
    logger.info(
        "Pipeline generation requested",
        extra={
            "platform": request.target.platform,
            "pipeline_name": request.pipeline_name,
            "stage_count": len(request.stages),
        },
    )
    try:
        return service.generate(request)
    except PipelineValidationError as error:
        raise HTTPException(status_code=400, detail=error.violations) from error
    except PipelineRenderError as error:
        raise HTTPException(status_code=error.status_code, detail=error.detail) from error