from __future__ import annotations

import base64
from functools import lru_cache

from app.core.config import settings


class SecretManagerError(RuntimeError):
    pass


@lru_cache
def _resolve_secret_manager_project() -> str:
    if settings.gcp_secret_manager_project.strip():
        return settings.gcp_secret_manager_project.strip()

    if settings.google_cloud_project.strip():
        return settings.google_cloud_project.strip()

    try:
        import google.auth

        _, project_id = google.auth.default()
    except Exception as exc:  # noqa: BLE001
        raise SecretManagerError('Unable to determine the Google Cloud project for Secret Manager.') from exc

    if not project_id:
        raise SecretManagerError('Unable to determine the Google Cloud project for Secret Manager.')

    return project_id


def _build_secret_resource_name(secret_name: str) -> str:
    normalized_secret_name = secret_name.strip()
    if not normalized_secret_name:
        raise SecretManagerError('Secret name is empty.')

    if normalized_secret_name.startswith('projects/'):
        return normalized_secret_name if '/versions/' in normalized_secret_name else f'{normalized_secret_name}/versions/latest'

    project_id = _resolve_secret_manager_project()
    return f'projects/{project_id}/secrets/{normalized_secret_name}/versions/latest'


@lru_cache
def _get_authorized_secret_manager_session():
    try:
        import google.auth
        from google.auth.transport.requests import AuthorizedSession
    except ImportError as exc:  # pragma: no cover - dependency presence is environment-specific
        raise SecretManagerError('google-auth is not installed.') from exc

    credentials, _ = google.auth.default()
    return AuthorizedSession(credentials)


@lru_cache
def access_secret(secret_name: str) -> str:
    resource_name = _build_secret_resource_name(secret_name)
    session = _get_authorized_secret_manager_session()
    url = f'https://secretmanager.googleapis.com/v1/{resource_name}:access'

    try:
        response = session.get(url, timeout=20)
    except Exception as exc:  # noqa: BLE001
        raise SecretManagerError(f'Unable to access secret {secret_name!r} in Google Secret Manager.') from exc

    if response.status_code != 200:
        raise SecretManagerError(f'Unable to access secret {secret_name!r} in Google Secret Manager.')

    try:
        payload = response.json()
        encoded_value = payload['payload']['data']
        value = base64.b64decode(encoded_value).decode('utf-8').strip()
    except Exception as exc:  # noqa: BLE001
        raise SecretManagerError(f'Secret {secret_name!r} returned an invalid payload.') from exc

    if not value:
        raise SecretManagerError(f'Secret {secret_name!r} is empty.')

    return value


def resolve_optional_secret(secret_name: str | None) -> str | None:
    if not secret_name or not secret_name.strip():
        return None

    return access_secret(secret_name.strip())