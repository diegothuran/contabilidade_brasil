from __future__ import annotations

import json
from uuid import uuid4

import pytest
from sqlalchemy import text

from contabil.ai_reviews.model import FakeReviewClient, ReviewCallError, ReviewPoint
from contabil.ai_reviews.worker import run_month_review
from contabil.platform.auth import apply_tenant
from contabil.platform.db import get_admin_engine, get_engine, session_factory
from contabil.platform.settings import get_settings
from tests.integration.test_client_summaries import _seed_ledger
from tests.integration.test_phase_a import _auth, _journal_body, _post, _publish
from tests.integration.test_phase_c import _validate

PERIOD = "le_test-2026-09"
URL = f"/v1/periods/{PERIOD}/ai-reviews"


@pytest.fixture
def settings_env(monkeypatch):
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


def _with_key(settings_env, limit: int | None = None) -> None:
    settings_env.setenv("CLAUDE_API_KEY", "chave-de-teste-sem-uso")
    if limit is not None:
        settings_env.setenv("REVIEW_DAILY_LIMIT", str(limit))
    get_settings.cache_clear()


def _rows(sql: str, **params) -> list:
    with get_admin_engine().connect() as connection:
        return list(connection.execute(text(sql), params).all())


def _request(client, token: str, key: str | None = None):
    return _post(client, token, URL, None, key or uuid4().hex)


def _point(**overrides) -> ReviewPoint:
    values = {
        "relevancia": "alta",
        "categoria": "variacao",
        "titulo": "Receita nova no mês",
        "explicacao": "A receita apareceu só nesta competência.",
        "evidencias": ["indicador:receita", "conta:4.1.01"],
    }
    values.update(overrides)
    return ReviewPoint(**values)


def _dispatch(review_id: str, operation_id: str, fake: FakeReviewClient) -> None:
    """Um despacho do handler, numa transação, como o relay faz."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        run_month_review(session, "tenant_demo", {"review_id": review_id, "operation_id": operation_id}, client=fake)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _requested(client, tokens, settings_env) -> dict:
    _with_key(settings_env)
    response = _request(client, tokens["preparer"])
    assert response.status_code == 202, response.text
    return response.json()


def _list(client, token: str) -> dict:
    response = client.get(URL, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()


def test_request_without_key_is_503(client, tokens, world, settings_env):
    del world
    settings_env.setenv("CLAUDE_API_KEY", "")
    get_settings.cache_clear()
    response = _request(client, tokens["preparer"])
    assert response.status_code == 503, response.text
    assert response.json()["title"] == "Revisão por IA indisponível"
    assert _rows("SELECT count(*) FROM ai_reviews") == [(0,)]
    assert _list(client, tokens["viewer"])["ai_reviews_enabled"] is False


def test_request_creates_review_operation_event_and_audit(client, tokens, world, settings_env):
    del world
    _with_key(settings_env)
    key = uuid4().hex
    response = _request(client, tokens["preparer"], key)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["kind"] == "month_review" and body["status"] == "accepted"
    replay = _request(client, tokens["preparer"], key)
    assert replay.json()["review_id"] == body["review_id"]
    assert _rows("SELECT status, model, prompt_version, packet_version, requested_by FROM ai_reviews") == [
        ("requested", "claude-opus-5-5", "revisao-1", "pacote-1", "preparer")
    ]
    events = _rows("SELECT payload FROM outbox_events WHERE event_type = 'MonthReviewRequested'")
    assert events == [({"review_id": body["review_id"], "operation_id": body["operation_id"]},)]
    assert _rows("SELECT count(*) FROM audit_events WHERE metadata->>'action' = 'ai_review_requested'") == [(1,)]


def test_roles_and_tenant(client, tokens, world, settings_env):
    del world
    _with_key(settings_env)
    assert _request(client, tokens["cliente"]).status_code == 403
    assert _request(client, tokens["viewer"]).status_code == 403
    assert _request(client, tokens["outsider"]).status_code == 404
    assert client.get(URL, headers=_auth(tokens["cliente"])).status_code == 403
    assert client.get(URL, headers=_auth(tokens["outsider"])).status_code == 404
    assert _rows("SELECT count(*) FROM ai_reviews") == [(0,)]


def test_daily_limit_is_429(client, tokens, world, settings_env):
    del world
    _with_key(settings_env, limit=1)
    assert _request(client, tokens["preparer"]).status_code == 202
    response = _request(client, tokens["approver"])
    assert response.status_code == 429, response.text
    assert response.json()["title"] == "Limite diário de revisões por IA atingido"
    assert _rows("SELECT count(*) FROM ai_reviews") == [(1,)]


def test_worker_saves_points_with_valid_evidence_only(client, tokens, world, settings_env):
    del world
    _seed_ledger(client, tokens)
    created = _requested(client, tokens, settings_env)
    fake = FakeReviewClient(
        [
            _point(),
            _point(titulo="Conta inventada", evidencias=["conta:7.7.77"]),
            _point(titulo="Categoria estranha", categoria="fraude", relevancia="urgente", evidencias=["indicador:resultado"]),
        ]
    )
    _dispatch(created["review_id"], created["operation_id"], fake)
    assert fake.calls == 1
    sent = json.loads(fake.last_user or "{}")
    raw = fake.last_user or ""
    # O pacote não leva nome, CNPJ nem ids internos da empresa.
    assert "Empresa Teste" not in raw and "le_test" not in raw and "tenant_demo" not in raw
    assert sent["competencia"] == "2026-09" and sent["versao"] == "pacote-1"
    assert sent["indicadores"]["receita"]["mes"] == "1000.00"
    assert sent["indicadores"]["receita"]["meses_anteriores"] == [None, None, "0.00"]
    review = _rows("SELECT status, stop_reason, input_tokens, output_tokens, input_sha256 IS NOT NULL FROM ai_reviews")
    assert review == [("completed", "end_turn", 1000, 200, True)]
    listed = _list(client, tokens["viewer"])
    assert listed["ai_reviews_enabled"] is True
    item = listed["items"][0]
    _validate("ai-review.schema.json", item)
    assert item["stale"] is False
    assert [(f["position"], f["title"], f["relevance"], f["category"], f["evidence"]) for f in item["findings"]] == [
        (1, "Receita nova no mês", "alta", "variacao", ["indicador:receita", "conta:4.1.01"]),
        (2, "Categoria estranha", "baixa", "outro", ["indicador:resultado"]),
    ]
    assert _rows(f"SELECT status FROM operations WHERE id = '{created['operation_id']}'") == [("running",)]


def test_incomplete_answer_marks_review_and_operation(client, tokens, world, settings_env):
    del world
    created = _requested(client, tokens, settings_env)
    _dispatch(created["review_id"], created["operation_id"], FakeReviewClient([_point()], stop_reason="max_tokens"))
    assert _rows("SELECT status, stop_reason FROM ai_reviews") == [("incomplete", "max_tokens")]
    assert _rows("SELECT count(*) FROM ai_review_findings") == [(0,)]
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{created['operation_id']}'") == [("resposta_incompleta",)]


def test_failed_call_survives_rollback_and_retry_completes(client, tokens, world, settings_env):
    del world
    created = _requested(client, tokens, settings_env)
    with pytest.raises(ReviewCallError):
        _dispatch(created["review_id"], created["operation_id"], FakeReviewClient([], fail=True))
    assert _rows("SELECT status, stop_reason FROM ai_reviews") == [("failed", "error")]
    _dispatch(created["review_id"], created["operation_id"], FakeReviewClient([_point(evidencias=["indicador:receita"])]))
    assert _rows("SELECT status FROM ai_reviews") == [("completed",)]
    # Revisão concluída não chama o modelo de novo numa reentrega.
    again = FakeReviewClient([_point()])
    _dispatch(created["review_id"], created["operation_id"], again)
    assert again.calls == 0
    assert _rows("SELECT count(*) FROM ai_review_findings") == [(1,)]


def test_decisions_latest_wins_and_are_audited(client, tokens, world, settings_env):
    del world
    created = _requested(client, tokens, settings_env)
    _dispatch(created["review_id"], created["operation_id"], FakeReviewClient([_point(evidencias=["indicador:receita"])]))
    finding = _list(client, tokens["viewer"])["items"][0]["findings"][0]
    path = f"/v1/ai-review-findings/{finding['finding_id']}/decisions"
    assert _post(client, tokens["viewer"], path, {"decision": "procede"}).status_code == 403
    assert _post(client, tokens["preparer"], path, {"decision": "talvez"}).status_code == 422
    first = _post(client, tokens["preparer"], path, {"decision": "procede"})
    assert first.status_code == 201, first.text
    second = _post(client, tokens["approver"], path, {"decision": "nao_procede", "note": "  Já corrigido no lançamento de ajuste.  "})
    assert second.status_code == 201, second.text
    decision = _list(client, tokens["viewer"])["items"][0]["findings"][0]["decision"]
    assert (decision["decision"], decision["note"], decision["decided_by"]) == ("nao_procede", "Já corrigido no lançamento de ajuste.", "approver")
    assert _rows("SELECT count(*) FROM ai_review_decisions") == [(2,)]
    audit = _rows("SELECT metadata->>'decision' FROM audit_events WHERE metadata->>'action' = 'ai_review_finding_decided' ORDER BY occurred_at")
    assert audit == [("procede",), ("nao_procede",)]
    # A nota não vai para a auditoria.
    assert _rows("SELECT count(*) FROM audit_events WHERE metadata::text LIKE '%corrigido%'") == [(0,)]
    assert _post(client, tokens["outsider"], path, {"decision": "procede"}).status_code == 404


def test_review_becomes_stale_when_ledger_changes(client, tokens, world, settings_env):
    del world
    _seed_ledger(client, tokens)
    created = _requested(client, tokens, settings_env)
    _dispatch(created["review_id"], created["operation_id"], FakeReviewClient([_point()]))
    assert _list(client, tokens["viewer"])["items"][0]["stale"] is False
    _publish(
        client,
        tokens,
        _journal_body(
            legal_entity_id="le_test",
            period_id=PERIOD,
            entry_date="2026-09-20",
            description="Venda extra",
            lines=[
                {"account_id": "le_test-1.1.02", "side": "debit", "amount": "50.00", "description": "Banco"},
                {"account_id": "le_test-4.1.01", "side": "credit", "amount": "50.00", "description": "Receita"},
            ],
        ),
    )
    assert _list(client, tokens["viewer"])["items"][0]["stale"] is True


@pytest.mark.parametrize("table", ["ai_review_findings", "ai_review_decisions"])
def test_findings_and_decisions_are_insert_only(client, world, table):
    del client, world
    with pytest.raises(Exception, match="permission denied"):
        with get_engine().begin() as connection:
            connection.execute(text("SELECT set_config('app.tenant_id', 'tenant_demo', true)"))
            connection.execute(text(f"UPDATE {table} SET created_at = now()"))
    with pytest.raises(Exception, match="permission denied"):
        with get_engine().begin() as connection:
            connection.execute(text(f"DELETE FROM {table}"))


def test_reviews_cannot_be_deleted(client, world):
    del client, world
    with pytest.raises(Exception, match="permission denied"):
        with get_engine().begin() as connection:
            connection.execute(text("DELETE FROM ai_reviews"))
