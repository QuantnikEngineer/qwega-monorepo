"""JWKS public key endpoint."""

from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

router = APIRouter(tags=["jwks"])


@router.get("/.well-known/jwks.json")
async def get_jwks(request: Request) -> JSONResponse:
    """Serve RS256 public key in JWKS format."""
    jwks = request.app.state.jwt_manager.get_jwks()
    return JSONResponse(content=jwks, headers={"Cache-Control": "public, max-age=86400"})
