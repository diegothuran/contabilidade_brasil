from __future__ import annotations

import threading
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest
from fastapi.testclient import TestClient

from contabil.bootstrap import bootstrap
from contabil.platform.auth import authenticate
from contabil.platform.settings import Settings, get_settings
from contabil.worker import run_loop


def test_heroku_url_falls_back_to_one_credential() -> None:
    settings = Settings(
        database_url="postgres://user:secret@host:5432/db",
        database_admin_url="",
    )
    assert settings.database_url == "postgresql+psycopg://user:secret@host:5432/db"
    assert settings.database_admin_url == settings.database_url


def test_postgresql_scheme_is_normalized() -> None:
    settings = Settings(database_url="postgresql://user:secret@host:5432/db", database_admin_url="postgresql://admin:secret@host:5432/db")
    assert settings.database_url == "postgresql+psycopg://user:secret@host:5432/db"
    assert settings.database_admin_url == "postgresql+psycopg://admin:secret@host:5432/db"


def test_authenticate_reads_configured_claims(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OIDC_USERNAME_CLAIM", "cognito:username")
    monkeypatch.setenv("OIDC_TENANT_CLAIM", "custom:tenant_id")
    get_settings.cache_clear()
    monkeypatch.setattr(
        "contabil.platform.auth.decode_token",
        lambda _token: {"cognito:username": "ana", "custom:tenant_id": ["tenant_demo"]},
    )
    session = MagicMock()
    session.execute.return_value.one_or_none.return_value = (SimpleNamespace(roles=["preparer"]), "Ana", "Escritório")
    try:
        principal = authenticate(session, "token")
    finally:
        get_settings.cache_clear()
    assert principal.user_id == "ana"
    assert principal.tenant_id == "tenant_demo"
    assert "preparer" in principal.roles


def test_spa_serves_index_for_client_routes(tmp_path, monkeypatch: pytest.MonkeyPatch) -> None:
    (tmp_path / "index.html").write_text("contabil-spa", encoding="utf-8")
    (tmp_path / "assets").mkdir()
    (tmp_path / "favicon.ico").write_bytes(b"ico")
    monkeypatch.setenv("STATIC_DIR", str(tmp_path))
    monkeypatch.setenv("OUTBOX_IN_PROCESS", "0")
    get_settings.cache_clear()
    from contabil.main import create_app

    try:
        with TestClient(create_app()) as client:
            assert client.get("/healthz").json()["status"] == "ok"
            assert "contabil-spa" in client.get("/app/journals").text
            assert client.get("/favicon.ico").content == b"ico"
    finally:
        get_settings.cache_clear()


def test_run_loop_returns_when_stopped() -> None:
    stop = threading.Event()
    stop.set()
    run_loop(stop)


def test_bootstrap_rejects_unknown_role() -> None:
    with pytest.raises(ValueError, match="Papéis aceitos"):
        bootstrap("tenant", "Nome", "user", "Pessoa", ["owner"])
