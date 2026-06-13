import base64

import app.core.secret_manager as secret_manager_module


class _StubResponse:
    def __init__(self, status_code: int, payload: dict):
        self.status_code = status_code
        self._payload = payload

    def json(self):
        return self._payload


class _StubSession:
    def __init__(self, response: _StubResponse):
        self._response = response
        self.urls: list[str] = []

    def get(self, url: str, timeout: int):
        self.urls.append(url)
        assert timeout == 20
        return self._response


def test_access_secret_uses_rest_endpoint_and_decodes_payload(monkeypatch):
    secret_manager_module.access_secret.cache_clear()
    secret_manager_module._get_authorized_secret_manager_session.cache_clear()
    secret_manager_module._resolve_secret_manager_project.cache_clear()

    monkeypatch.setattr(secret_manager_module.settings, 'gcp_secret_manager_project', 'agents-irfan')
    session = _StubSession(
        _StubResponse(
            200,
            {'payload': {'data': base64.b64encode(b'super-secret').decode('utf-8')}},
        )
    )
    monkeypatch.setattr(secret_manager_module, '_get_authorized_secret_manager_session', lambda: session)

    value = secret_manager_module.access_secret('harness_token')

    assert value == 'super-secret'
    assert session.urls == ['https://secretmanager.googleapis.com/v1/projects/agents-irfan/secrets/harness_token/versions/latest:access']


def test_access_secret_raises_when_provider_returns_error(monkeypatch):
    secret_manager_module.access_secret.cache_clear()
    secret_manager_module._get_authorized_secret_manager_session.cache_clear()
    secret_manager_module._resolve_secret_manager_project.cache_clear()

    monkeypatch.setattr(secret_manager_module.settings, 'gcp_secret_manager_project', 'agents-irfan')
    session = _StubSession(_StubResponse(404, {'error': {'message': 'not found'}}))
    monkeypatch.setattr(secret_manager_module, '_get_authorized_secret_manager_session', lambda: session)

    try:
        secret_manager_module.access_secret('harness_token')
    except secret_manager_module.SecretManagerError as exc:
        assert "Unable to access secret 'harness_token'" in str(exc)
    else:
        raise AssertionError('Expected SecretManagerError')