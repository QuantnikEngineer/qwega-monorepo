"""
JWT Manager
===========
RS256 JWT token creation and JWKS endpoint data.
Private key stays on server; public key distributed via /.well-known/jwks.json.
"""

import base64
import math
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import jwt
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.rsa import RSAPublicNumbers

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


class JWTManager:
    """RS256 JWT token manager with JWKS support."""

    def __init__(self):
        self.private_key = None
        self.public_key = None
        self.kid = "wega-key-001"
        self._load_keys()

    def _resolve_key_path(self, configured_path: str, fallback_file: str) -> Path:
        if configured_path:
            return Path(configured_path)
        return Path(__file__).resolve().parents[2] / "keys" / fallback_file

    def _load_keys(self) -> None:
        """Load RSA key pair from filesystem."""
        private_path = self._resolve_key_path(settings.jwt_private_key_path, "private.pem")
        public_path = self._resolve_key_path(settings.jwt_public_key_path, "public.pem")

        try:
            with open(private_path, "rb") as key_file:
                self.private_key = serialization.load_pem_private_key(key_file.read(), password=None)
            with open(public_path, "rb") as key_file:
                self.public_key = serialization.load_pem_public_key(key_file.read())
            logger.info("[jwt] RSA key pair loaded", kid=self.kid)
        except FileNotFoundError as exc:
            logger.error("[jwt] Key file not found", error=str(exc))
            raise

    def create_access_token(
        self,
        sub: str,
        email: str,
        display_name: str,
        roles: list[str],
        capabilities: list[str],
        org_id: str,
        # Primary project for backward compat (gateway reads this)
        project_id: str | None = None,
        # Multi-project: all project IDs user belongs to
        project_ids: list[str] | None = None,
        # Phase 5: allowed agent IDs per role
        allowed_agents: list[str] | None = None,
        # Per-project agent access (Phase 2 delegation)
        project_allowed_agents: dict[str, list[str]] | None = None,
        # Scoped claims (D-17) — kept for backward compat during rolling deploy
        platform_capabilities: list[str] | None = None,
        org_capabilities: list[str] | None = None,
        project_roles: dict[str, list[str]] | None = None,
        self_capabilities: list[str] | None = None,
    ) -> str:
        """Create RS256-signed JWT access token with user claims.

        Includes flat ``roles``/``capabilities``/``allowed_agents`` (Phase 5 primary),
        ``project_id`` (primary project for backward compat), ``project_ids`` (all
        memberships), and scoped claims (D-17 Phase 4) for backward compat.
        """
        now = datetime.now(timezone.utc)
        payload = {
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "sub": sub,
            "email": email,
            "name": display_name,
            "roles": roles,
            "capabilities": capabilities,
            "org_id": org_id,
            "project_id": project_id,
            "project_ids": project_ids or [],
            "allowed_agents": allowed_agents or [],
            "project_allowed_agents": project_allowed_agents or {},
            # Scoped claims (D-17) — backward compat during rolling deploy
            "platform_capabilities": platform_capabilities or [],
            "org_capabilities": org_capabilities or [],
            "project_roles": project_roles or {},
            "self_capabilities": self_capabilities or [],
            "iat": now,
            "exp": now + timedelta(minutes=settings.jwt_access_token_expire_minutes),
            "jti": str(uuid.uuid4()),
        }
        return jwt.encode(payload, self.private_key, algorithm="RS256", headers={"kid": self.kid})

    def create_refresh_token(self) -> str:
        """Create an opaque refresh token (random UUID, stored hashed in DB)."""
        return str(uuid.uuid4())

    def decode_access_token(self, token: str) -> dict[str, Any]:
        """Decode and validate an RS256 access token."""
        return jwt.decode(
            token,
            self.public_key,
            algorithms=["RS256"],
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
        )

    def get_jwks(self) -> dict[str, Any]:
        """Return JWKS (JSON Web Key Set) for public key distribution."""
        if self.public_key is None:
            return {"keys": []}

        pub_numbers: RSAPublicNumbers = self.public_key.public_numbers()

        def _int_to_base64url(value: int) -> str:
            byte_length = math.ceil(value.bit_length() / 8)
            return base64.urlsafe_b64encode(
                value.to_bytes(byte_length, byteorder="big")
            ).rstrip(b"=").decode("ascii")

        return {
            "keys": [
                {
                    "kty": "RSA",
                    "kid": self.kid,
                    "use": "sig",
                    "alg": "RS256",
                    "n": _int_to_base64url(pub_numbers.n),
                    "e": _int_to_base64url(pub_numbers.e),
                }
            ]
        }

