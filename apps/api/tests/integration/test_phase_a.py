from __future__ import annotations

import os
from decimal import Decimal
from pathlib import Path
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import text

from contabil.platform.db import get_admin_engine, get_engine
from contabil.worker import relay_once
from contabil.platform.db import session_factory


def _auth(token: str, key: str | None = None) -> dict[str, str]:
    headers = {"Authorization": f"Bearer {token}"}
    if key is not None:
        headers["Idempotency-Key"] = key
    return headers


def _post(client, token: str, path: str, body: dict | None = None, key: str | None = None):
    return client.post(path, json={} if body is None else body, headers=_auth(token, key or uuid4().hex))


def _journal_body(**overrides) -> dict:
    body = {
        "legal_entity_id": "le_test",
        "period_id": "le_test-2026-09",
        "currency": "BRL",
        "entry_date": "2026-09-15",
        "description": "Despesa de teste",
        "lines": [
            {"account_id": "le_test-5.1.01", "side": "debit", "amount": "10.00", "description": "Débito"},
            {"account_id": "le_test-2.1.01", "side": "credit", "amount": "10.00", "description": "Crédito"},
        ],
    }
    body.update(overrides)
    return body


def _publish(client, tokens, body: dict | None = None) -> dict:
    created = _post(client, tokens["preparer"], "/v1/journals", body or _journal_body())
    assert created.status_code == 201, created.text
    journal_id = created.json()["journal_id"]
    assert _post(client, tokens["preparer"], f"/v1/journals/{journal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/approve").status_code == 200
    published = _post(client, tokens["approver"], f"/v1/journals/{journal_id}/publish")
    assert published.status_code == 200, published.text
    return published.json()


def _schemas() -> Path:
    configured = os.environ.get("SCHEMAS_DIR")
    if configured:
        return Path(configured)
    return Path(__file__).resolve().parents[4] / "schemas"


def test_unbalanced_journal_is_rejected(client, tokens, world):
    del world
    body = _journal_body()
    body["lines"][1]["amount"] = "9.00"
    response = _post(client, tokens["preparer"], "/v1/journals", body)
    assert response.status_code == 400
    assert response.json()["title"] == "Journal desequilibrado"
    balance = client.get(
        "/v1/legal-entities/le_test/trial-balance",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    assert balance.status_code == 200
    assert balance.json()["debit_total"] == "0"


def test_publish_rejects_tampered_unbalanced_journal(client, tokens, world):
    del world
    created = _post(client, tokens["preparer"], "/v1/journals", _journal_body())
    journal_id = created.json()["journal_id"]
    assert _post(client, tokens["preparer"], f"/v1/journals/{journal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/approve").status_code == 200
    with get_admin_engine().begin() as connection:
        connection.execute(text("UPDATE journal_lines SET amount = 9 WHERE journal_id = :id AND side = 'credit'"), {"id": journal_id})
    published = _post(client, tokens["approver"], f"/v1/journals/{journal_id}/publish")
    assert published.status_code == 409
    assert published.json()["title"] == "Journal desequilibrado"
    current = client.get(f"/v1/journals/{journal_id}", headers=_auth(tokens["approver"]))
    assert current.json()["status"] == "approved"


def test_database_rejects_unbalanced_publish(client, tokens, world):
    del client, tokens, world
    with pytest.raises(Exception, match="not balanced"):
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    """
                    INSERT INTO journal_entries (
                      id, schema_version, tenant_id, legal_entity_id, period_id, status, currency,
                      entry_date, description, source_type, source_id, created_by, created_at
                    ) VALUES (
                      'jnl_unbalanced', '1.0.0', 'tenant_demo', 'le_test', 'le_test-2026-09', 'draft', 'BRL',
                      '2026-09-15', 'Desequilibrado', 'manual', 'src', 'preparer', now()
                    )
                    """
                )
            )
            connection.execute(
                text(
                    """
                    INSERT INTO journal_lines (
                      id, tenant_id, journal_id, line_no, account_id, side, amount, description, dimension_values
                    ) VALUES
                      ('ln_bad_1', 'tenant_demo', 'jnl_unbalanced', 1, 'le_test-5.1.01', 'debit', 10, 'D', '{}'::jsonb),
                      ('ln_bad_2', 'tenant_demo', 'jnl_unbalanced', 2, 'le_test-2.1.01', 'credit', 4, 'C', '{}'::jsonb)
                    """
                )
            )
            connection.execute(
                text("UPDATE journal_entries SET status = 'published', published_at = now(), published_by = 'approver' WHERE id = 'jnl_unbalanced'")
            )
    with get_admin_engine().begin() as connection:
        count = connection.execute(text("SELECT count(*) FROM journal_entries WHERE id = 'jnl_unbalanced'")).scalar_one()
    assert count == 0


def test_published_journal_is_immutable(client, tokens, world):
    del world
    published = _publish(client, tokens)
    journal_id = published["journal_id"]
    original_amount = published["lines"][0]["amount"]
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE journal_lines SET amount = 1 WHERE journal_id = :id"), {"id": journal_id})
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE journal_entries SET description = 'alterado' WHERE id = :id"), {"id": journal_id})
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("DELETE FROM journal_entries WHERE id = :id"), {"id": journal_id})
    current = client.get(f"/v1/journals/{journal_id}", headers=_auth(tokens["viewer"]))
    assert current.status_code == 200
    assert current.json()["lines"][0]["amount"] == original_amount
    assert current.json()["description"] == "Despesa de teste"


def test_closed_period_and_reopen(client, tokens, world):
    del world
    opened = _post(client, tokens["approver"], "/v1/periods/le_test-2026-08/close-runs", {})
    assert opened.status_code == 201, opened.text
    run_id = opened.json()["close_run_id"]
    blocked = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert blocked.status_code == 409
    assert blocked.json()["title"] == "Fechamento bloqueado"
    reviewed = _post(
        client,
        tokens["approver"],
        f"/v1/close-runs/{run_id}/items/trial_balance_review",
        {"status": "completed"},
    )
    assert reviewed.status_code == 200
    closed = _post(client, tokens["approver"], "/v1/periods/le_test-2026-08/close")
    assert closed.status_code == 200
    assert closed.json()["status"] == "closed"
    denied = _post(
        client,
        tokens["preparer"],
        "/v1/journals",
        _journal_body(period_id="le_test-2026-08", entry_date="2026-08-10"),
    )
    assert denied.status_code == 409
    assert denied.json()["title"] == "Período fechado"
    request = _post(client, tokens["preparer"], "/v1/periods/le_test-2026-08/reopen-requests", {"reason": "Ajuste de competência"})
    assert request.status_code == 201
    request_id = request.json()["reopen_request_id"]
    assert _post(client, tokens["preparer"], f"/v1/reopen-requests/{request_id}/approve").status_code == 403
    approved = _post(client, tokens["approver"], f"/v1/reopen-requests/{request_id}/approve")
    assert approved.status_code == 200
    assert approved.json()["status"] == "reopened"
    events = client.get("/v1/audit-events", headers=_auth(tokens["approver"]))
    assert any(item["event_type"] == "period_reopened" and item["reason"] == "Ajuste de competência" for item in events.json()["items"])
    reopened = _publish(client, tokens, _journal_body(period_id="le_test-2026-08", entry_date="2026-08-10", description="Após reabertura"))
    assert reopened["status"] == "published"


def test_creator_cannot_approve_and_viewer_cannot_create(client, tokens, world):
    del world
    created = _post(client, tokens["admin"], "/v1/journals", _journal_body(description="Criado pelo admin"))
    assert created.status_code == 201
    journal_id = created.json()["journal_id"]
    assert _post(client, tokens["admin"], f"/v1/journals/{journal_id}/submit").status_code == 200
    rejected = _post(client, tokens["admin"], f"/v1/journals/{journal_id}/approve")
    assert rejected.status_code == 403
    assert rejected.json()["title"] == "Segregação de funções"
    forbidden = _post(client, tokens["viewer"], "/v1/journals", _journal_body(description="Consulta"))
    assert forbidden.status_code == 403


def test_reversal_preserves_original_and_nets_zero(client, tokens, world):
    del world
    body = _journal_body(
        description="Aporte",
        lines=[
            {"account_id": "le_test-1.1.02", "side": "debit", "amount": "80.00", "description": "Banco"},
            {"account_id": "le_test-3.1.01", "side": "credit", "amount": "80.00", "description": "Capital"},
        ],
    )
    original = _publish(client, tokens, body)
    reversal = _post(client, tokens["preparer"], f"/v1/journals/{original['journal_id']}/reverse")
    assert reversal.status_code == 201
    reversal_id = reversal.json()["journal_id"]
    assert reversal.json()["source"]["source_type"] == "reversal"
    assert reversal.json()["source"]["reverses_journal_id"] == original["journal_id"]
    assert reversal.json()["lines"][0]["side"] == "credit"
    assert _post(client, tokens["preparer"], f"/v1/journals/{reversal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{reversal_id}/approve").status_code == 200
    published = _post(client, tokens["approver"], f"/v1/journals/{reversal_id}/publish")
    assert published.status_code == 200
    original_after = client.get(f"/v1/journals/{original['journal_id']}", headers=_auth(tokens["preparer"]))
    assert original_after.json()["status"] == "reversed"
    assert original_after.json()["lines"][0]["amount"] == "80"
    balance = client.get(
        "/v1/legal-entities/le_test/trial-balance",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    rows = {row["account_id"]: row for row in balance.json()["rows"]}
    assert rows["le_test-1.1.02"]["balance"] == "0"
    assert rows["le_test-3.1.01"]["balance"] == "0"
    drill = client.get(
        "/v1/accounts/le_test-1.1.02/lines",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    assert {line["journal_id"] for line in drill.json()["lines"]} == {original["journal_id"], reversal_id}


def test_cross_tenant_is_hidden(client, tokens, world):
    del world
    published = _publish(client, tokens)
    hidden = client.get(f"/v1/journals/{published['journal_id']}", headers=_auth(tokens["outsider"]))
    assert hidden.status_code == 404
    listed = client.get("/v1/legal-entities", headers=_auth(tokens["outsider"]))
    assert listed.status_code == 200
    assert all(item["legal_entity_id"] != "le_test" for item in listed.json()["items"])
    with get_engine().begin() as connection:
        connection.execute(text("SELECT set_config('app.tenant_id', 'tenant_other', true)"))
        count = connection.execute(text("SELECT count(*) FROM journal_entries WHERE id = :id"), {"id": published["journal_id"]}).scalar_one()
    assert count == 0
    with pytest.raises(Exception):
        with get_engine().begin() as connection:
            connection.execute(text("SELECT set_config('app.tenant_id', 'tenant_other', true)"))
            connection.execute(
                text(
                    """
                    INSERT INTO legal_entities (id, tenant_id, name, cnpj, currency, created_at)
                    VALUES ('le_leak', 'tenant_demo', 'Vazamento', '10000000000100', 'BRL', now())
                    """
                )
            )


def test_idempotency_replay_and_conflict(client, tokens, world):
    del world
    body = _journal_body(description="Idempotente")
    key = "idem-key-0001"
    first = _post(client, tokens["preparer"], "/v1/journals", body, key=key)
    second = _post(client, tokens["preparer"], "/v1/journals", body, key=key)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["journal_id"] == second.json()["journal_id"]
    conflict = _post(client, tokens["preparer"], "/v1/journals", _journal_body(description="Outro corpo"), key=key)
    assert conflict.status_code == 409
    listed = client.get(
        "/v1/journals",
        params={"legal_entity_id": "le_test", "period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    matches = [item for item in listed.json()["items"] if item["description"] == "Idempotente"]
    assert len(matches) == 1


def test_audit_chain_detects_tamper_and_outbox_relays(client, tokens, world):
    del world
    _publish(client, tokens)
    verify = client.get("/v1/audit-events/verify", headers=_auth(tokens["preparer"]))
    assert verify.status_code == 200
    assert verify.json()["valid"] is True
    assert verify.json()["checked"] > 0
    with pytest.raises(Exception):
        with get_engine().begin() as connection:
            connection.execute(text("SELECT set_config('app.tenant_id', 'tenant_demo', true)"))
            connection.execute(text("UPDATE audit_events SET reason = 'adulterado'"))
    admin = get_admin_engine()
    try:
        with admin.begin() as connection:
            connection.execute(text("ALTER TABLE audit_events DISABLE TRIGGER USER"))
        with admin.begin() as connection:
            connection.execute(text("UPDATE audit_events SET event_hash = repeat('ab', 32) WHERE tenant_id = 'tenant_demo'"))
        tampered = client.get("/v1/audit-events/verify", headers=_auth(tokens["preparer"]))
        assert tampered.json()["valid"] is False
        assert tampered.json()["broken_event_id"]
    finally:
        with admin.begin() as connection:
            connection.execute(text("ALTER TABLE audit_events ENABLE TRIGGER USER"))
    session = session_factory(admin=True)()
    try:
        assert relay_once(session) >= 1
        session.commit()
        assert relay_once(session) == 0
        session.commit()
    finally:
        session.close()


def test_responses_match_contracts(client, tokens, world):
    del world
    published = _publish(client, tokens)
    events = client.get("/v1/audit-events", headers=_auth(tokens["preparer"]))
    schemas = _schemas()
    journal_schema = __import__("json").loads((schemas / "journal-entry.schema.json").read_text(encoding="utf-8"))
    audit_schema = __import__("json").loads((schemas / "audit-event.schema.json").read_text(encoding="utf-8"))
    journal_errors = list(Draft202012Validator(journal_schema, format_checker=FormatChecker()).iter_errors(published))
    assert not journal_errors, [error.message for error in journal_errors]
    event = events.json()["items"][0]
    audit_errors = list(Draft202012Validator(audit_schema, format_checker=FormatChecker()).iter_errors(event))
    assert not audit_errors, [error.message for error in audit_errors]
    assert Decimal(published["lines"][0]["amount"]) == Decimal(published["lines"][1]["amount"])


def test_group_account_is_rejected(client, tokens, world):
    del world
    body = _journal_body()
    body["lines"][0]["account_id"] = "le_test-5"
    response = _post(client, tokens["preparer"], "/v1/journals", body)
    assert response.status_code == 400
    assert response.json()["title"] == "Conta inválida"
