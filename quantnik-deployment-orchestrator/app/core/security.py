from __future__ import annotations

import hmac
from dataclasses import dataclass

from fastapi import Header, HTTPException, Request

from app.core.config import settings
from app.core.logging import get_logger
from app.core.secret_manager import SecretManagerError, resolve_optional_secret

logger = get_logger(__name__)


@dataclass(frozen=True)
class RepositoryLookupCaller:
    principal: str
    auth_type: str


def _is_local_debug_request(request: Request) -> bool:
    client_host = (request.client.host if request.client else '') or ''
    return client_host.lower() in {'127.0.0.1', '::1', 'localhost', 'testclient'}


def _split_role_values(value: str | None) -> set[str]:
    if not value:
        return set()

    return {item.strip().lower() for item in value.split(',') if item.strip()}


def _extract_bearer_token(authorization_header: str | None) -> str | None:
    if not authorization_header:
        return None

    scheme, _, value = authorization_header.partition(' ')
    if scheme.lower() != 'bearer' or not value.strip():
        return None

    return value.strip()


def _resolve_service_token() -> str | None:
    secret_name = settings.repository_lookup_service_token_secret_name.strip()
    if secret_name:
        try:
            return resolve_optional_secret(secret_name)
        except SecretManagerError as exc:
            logger.error('Failed to resolve repository lookup service token secret %r: %s', secret_name, exc)
            raise HTTPException(status_code=503, detail='Repository lookup authentication is unavailable.') from exc

    token = settings.repository_lookup_service_token.strip()
    return token or None


def require_repository_lookup_access(
    request: Request,
    authorization: str | None = Header(default=None),
) -> RepositoryLookupCaller:
    if settings.debug and settings.repository_lookup_allow_local_debug_bypass and _is_local_debug_request(request):
        return RepositoryLookupCaller(principal='local-debug', auth_type='local-debug-bypass')

    principal_header = settings.repository_lookup_identity_header
    roles_header = settings.repository_lookup_roles_header
    principal = (request.headers.get(principal_header) or '').strip()
    roles = _split_role_values(request.headers.get(roles_header))

    if principal:
        allowed_users = set(settings.repository_lookup_authorized_users_list)
        allowed_roles = set(settings.repository_lookup_authorized_roles_list)

        if allowed_users and principal.lower() not in allowed_users:
            raise HTTPException(status_code=403, detail='Repository lookup access is not allowed for this user.')

        if allowed_roles and not roles.intersection(allowed_roles):
            raise HTTPException(status_code=403, detail='Repository lookup access is not allowed for this role.')

        return RepositoryLookupCaller(principal=principal, auth_type='identity-header')

    service_token = _resolve_service_token()
    if service_token:
        bearer_token = _extract_bearer_token(authorization)
        if not bearer_token:
            raise HTTPException(status_code=401, detail='Repository lookup authentication is required.')

        if not hmac.compare_digest(bearer_token, service_token):
            raise HTTPException(status_code=403, detail='Repository lookup authentication failed.')

        return RepositoryLookupCaller(principal='service-token', auth_type='service-token')

    raise HTTPException(status_code=401, detail='Repository lookup authentication is required.')