"""Gateway JWKS contract route."""

import httpx
from fastapi import APIRouter
from fastapi.responses import JSONResponse

from app.config import settings
from app.models import JWKSResponse

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/jwks", response_model=JWKSResponse)
async def gateway_jwks() -> JSONResponse:
    """Public JWKS endpoint contract exposed by gateway."""
    upstream_url = f"{settings.auth_service_url.rstrip('/')}/.well-known/jwks.json"
    payload = {"keys": []}

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(upstream_url)
            if response.status_code == 200:
                body = response.json()
                if isinstance(body, dict) and isinstance(body.get("keys"), list):
                    payload = {"keys": body["keys"]}
    except httpx.HTTPError:
        # Keep contract reachable even if auth service is unavailable during bootstrap.
        pass

    return JSONResponse(content=JWKSResponse(**payload).model_dump())
