from collections.abc import Generator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from cara.core.config import Settings, get_settings
from main import app


@pytest.fixture()
def test_app() -> Generator[FastAPI, None, None]:
    get_settings.cache_clear()
    app.dependency_overrides = {}
    app.dependency_overrides[get_settings] = lambda: Settings(_env_file=None)
    yield app
    app.dependency_overrides.clear()
    get_settings.cache_clear()


@pytest.fixture()
def client(test_app: FastAPI) -> Generator[TestClient, None, None]:
    with TestClient(test_app) as test_client:
        yield test_client
