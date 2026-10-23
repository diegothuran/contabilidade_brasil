from __future__ import annotations

import os
import time
from pathlib import Path
from urllib.parse import urlparse, urlunparse

import httpx
import pytest
from tests.integration.world import reset_world
from alembic import command
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, text


def _use_test_database(name: str) -> None:
    current = os.environ.get(name)
    if not current:
        return
    parts = urlparse(current)
    database = parts.path.rstrip("/").rsplit("/", 1)[-1]
    if database == "contabil_test":
        return
    if database == "contabil":
        os.environ[name] = urlunparse(parts._replace(path="/contabil_test"))


def _use_test_bucket() -> None:
    if os.environ.get("OBJECT_STORAGE_BUCKET") == "contabil-dev":
        os.environ["OBJECT_STORAGE_BUCKET"] = "contabil-test"


_use_test_database("DATABASE_URL")
_use_test_database("DATABASE_ADMIN_URL")
_use_test_bucket()


def _wait_postgres(url: str) -> None:
    engine = create_engine(url)
    deadline = time.time() + 60
    last_error: Exception | None = None
    while time.time() < deadline:
        try:
            with engine.connect() as connection:
                connection.execute(text("SELECT 1"))
            engine.dispose()
            return
        except Exception as exc:
            last_error = exc
            time.sleep(1)
    engine.dispose()
    pytest.fail(f"postgres indisponível: {last_error}")


def _upgrade() -> None:
    root = Path(os.environ.get("APP_HOME", Path(__file__).resolve().parents[2]))
    config = Config(str(root / "alembic.ini"))
    command.upgrade(config, "head")


@pytest.fixture(scope="session")
def app():
    if os.environ.get("RUN_INTEGRATION") != "1":
        pytest.skip("defina RUN_INTEGRATION=1 para os testes de integração")
    from contabil.platform.db import get_admin_engine, get_engine
    from contabil.platform.settings import get_settings

    get_settings.cache_clear()
    get_engine.cache_clear()
    get_admin_engine.cache_clear()
    settings = get_settings()
    if settings.database_admin_url.rsplit("/", 1)[-1] != "contabil_test":
        pytest.skip("DATABASE_ADMIN_URL não aponta para contabil_test")
    _wait_postgres(settings.database_admin_url)
    _upgrade()
    from contabil.platform.storage import _client, ensure_configured_buckets

    _client.cache_clear()
    ensure_configured_buckets()
    from contabil.main import create_app

    return create_app()


@pytest.fixture(scope="session")
def client(app):
    with TestClient(app, raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def tokens(app):
    del app
    from contabil.platform.settings import get_settings

    settings = get_settings()
    deadline = time.time() + 90
    last_error: str | None = None
    names = ("preparer", "approver", "admin", "viewer", "outsider")
    while time.time() < deadline:
        try:
            issued: dict[str, str] = {}
            for username in names:
                response = httpx.post(
                    settings.oidc_token_url,
                    data={
                        "grant_type": "password",
                        "client_id": "contabil-web",
                        "username": username,
                        "password": settings.dev_user_password,
                        "scope": "openid",
                    },
                    timeout=10,
                )
                response.raise_for_status()
                issued[username] = response.json()["access_token"]
            return issued
        except Exception as exc:
            last_error = str(exc)
            time.sleep(2)
    pytest.fail(f"keycloak não emitiu tokens: {last_error}")


@pytest.fixture
def world(app):
    del app
    reset_world()
    yield
