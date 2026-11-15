from __future__ import annotations

import json

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from contabil.platform.db import get_admin_engine
from tests.integration.test_close_runs import _ready_run
from tests.integration.test_phase_a import _auth, _journal_body, _post, _publish
from tests.integration.world import add_entity


def _insert_summary(connection, status: str = "published") -> None:
    connection.execute(
        text(
            "INSERT INTO client_summaries (id, tenant_id, legal_entity_id, period_id, status, payload, created_by, created_at) "
            "VALUES ('cs_x', 'tenant_demo', 'le_test', 'le_test-2026-09', :status, CAST(:payload AS jsonb), 'preparer', now())"
        ),
        {"status": status, "payload": json.dumps({"revenue": "1"})},
    )


def test_published_payload_is_immutable(client, tokens, world):
    del client, tokens, world
    with get_admin_engine().begin() as connection:
        _insert_summary(connection)
    with pytest.raises(DBAPIError, match="payload is immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE client_summaries SET payload = CAST('{}' AS jsonb) WHERE id = 'cs_x'"))
    with pytest.raises(DBAPIError, match="cannot be deleted"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("DELETE FROM client_summaries WHERE id = 'cs_x'"))


PERIOD = "le_test-2026-09"
URL = f"/v1/periods/{PERIOD}/client-summary"


def _seed_ledger(client, tokens, entity: str = "le_test", period: str = PERIOD, revenue: str = "1000.00", expense: str = "710.00") -> None:
    """Conta de receita, conta bancária, uma receita e uma despesa publicadas."""
    with get_admin_engine().begin() as connection:
        connection.execute(
            text(
                "INSERT INTO accounts (id, tenant_id, legal_entity_id, chart_id, code, name, account_type, postable, active, created_at) "
                "VALUES (:id, 'tenant_demo', :entity, :chart, '4.1.01', 'Receita de serviços', 'revenue', true, true, now()) "
                "ON CONFLICT DO NOTHING"
            ),
            {"id": f"{entity}-4.1.01", "entity": entity, "chart": f"chart_{entity}"},
        )
        connection.execute(
            text(
                "INSERT INTO bank_accounts (id, tenant_id, legal_entity_id, account_id, name, bank_code, branch, "
                "account_number_masked, currency, active, created_at) "
                "VALUES (:id, 'tenant_demo', :entity, :account, 'Conta', '001', '0001', '1234', 'BRL', true, now())"
            ),
            {"id": f"ba_{entity}", "entity": entity, "account": f"{entity}-1.1.02"},
        )
    day = f"{period[-7:]}-10"
    _publish(
        client,
        tokens,
        _journal_body(
            legal_entity_id=entity,
            period_id=period,
            entry_date=day,
            description="Venda",
            lines=[
                {"account_id": f"{entity}-1.1.02", "side": "debit", "amount": revenue, "description": "Banco"},
                {"account_id": f"{entity}-4.1.01", "side": "credit", "amount": revenue, "description": "Receita"},
            ],
        ),
    )
    _publish(
        client,
        tokens,
        _journal_body(
            legal_entity_id=entity,
            period_id=period,
            entry_date=day,
            description="Despesa",
            lines=[
                {"account_id": f"{entity}-5.1.01", "side": "debit", "amount": expense, "description": "Despesa"},
                {"account_id": f"{entity}-1.1.02", "side": "credit", "amount": expense, "description": "Banco"},
            ],
        ),
    )


def _close(client, tokens, period: str = PERIOD) -> None:
    run_id = _ready_run(client, tokens, period)
    assert _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close").status_code == 200


def _reopen(client, tokens, period: str = PERIOD) -> None:
    request = _post(client, tokens["preparer"], f"/v1/periods/{period}/reopen-requests", {"reason": "Ajuste de competência"})
    assert request.status_code == 201, request.text
    approved = _post(client, tokens["approver"], f"/v1/reopen-requests/{request.json()['reopen_request_id']}/approve")
    assert approved.status_code == 200, approved.text


def _published(client, tokens) -> dict:
    created = _post(client, tokens["preparer"], URL)
    assert created.status_code == 201, created.text
    published = _post(client, tokens["approver"], f"{URL}/publish")
    assert published.status_code == 200, published.text
    return published.json()


def test_generate_requires_closed_period(client, tokens, world):
    del world
    response = _post(client, tokens["preparer"], URL)
    assert response.status_code == 409
    assert "Competência aberta" in response.text


def test_generate_and_publish_by_other_person(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    denied = _post(client, tokens["viewer"], URL)
    assert denied.status_code == 403
    created = _post(client, tokens["preparer"], URL)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["status"] == "draft"
    assert body["payload"]["revenue"] == "1000"
    assert body["payload"]["expense"] == "710"
    assert body["payload"]["result"] == "290"
    assert body["payload"]["cash"] == "290"
    assert body["payload"]["margin_percent"] == "29.0"
    assert _post(client, tokens["preparer"], f"{URL}/publish").status_code == 403
    published = _post(client, tokens["approver"], f"{URL}/publish")
    assert published.status_code == 200, published.text
    assert published.json()["status"] == "published"
    assert published.json()["published_by"] == "approver"
    assert _post(client, tokens["preparer"], URL).status_code == 409
    fetched = client.get(URL, headers=_auth(tokens["approver"]))
    assert fetched.status_code == 200 and fetched.json()["status"] == "published"


def test_creator_cannot_publish(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    assert _post(client, tokens["approver"], URL).status_code == 201
    response = _post(client, tokens["approver"], f"{URL}/publish")
    assert response.status_code == 409
    assert "Quem gerou não publica" in response.text


def test_regenerate_draft_recalculates(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    first = _post(client, tokens["preparer"], URL)
    assert first.status_code == 201
    with get_admin_engine().begin() as connection:
        connection.execute(text("UPDATE client_summaries SET payload = CAST('{}' AS jsonb)"))
    second = _post(client, tokens["preparer"], URL)
    assert second.status_code == 200, second.text
    assert second.json()["summary_id"] == first.json()["summary_id"]
    assert second.json()["payload"]["revenue"] == "1000"


def test_reopen_withdraws_published(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    _published(client, tokens)
    _reopen(client, tokens)
    with get_admin_engine().begin() as connection:
        row = connection.execute(text("SELECT status, withdrawn_reason FROM client_summaries")).one()
    assert row.status == "withdrawn"
    assert row.withdrawn_reason == "Competência reaberta"
    shown = client.get(URL, headers=_auth(tokens["approver"]))
    assert shown.status_code == 200 and shown.json()["status"] == "withdrawn"


def test_withdraw_needs_reason_and_approver(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    _published(client, tokens)
    assert _post(client, tokens["preparer"], f"{URL}/withdraw", {"reason": "Número errado no resumo"}).status_code == 403
    assert _post(client, tokens["approver"], f"{URL}/withdraw", {"reason": "curto"}).status_code in (400, 422)
    done = _post(client, tokens["approver"], f"{URL}/withdraw", {"reason": "Número errado no resumo"})
    assert done.status_code == 200, done.text
    assert done.json()["status"] == "withdrawn"
    assert done.json()["withdrawn_reason"] == "Número errado no resumo"


def test_client_sees_only_published_own_entity(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    draft = _post(client, tokens["preparer"], URL)
    assert draft.status_code == 201
    listed = client.get("/v1/portal/summaries", headers=_auth(tokens["cliente"]))
    assert listed.status_code == 200, listed.text
    assert listed.json()["items"] == []
    by_id = client.get(f"/v1/portal/summaries/{draft.json()['summary_id']}", headers=_auth(tokens["cliente"]))
    assert by_id.status_code == 404
    published = _published_after_draft(client, tokens)
    listed = client.get("/v1/portal/summaries", headers=_auth(tokens["cliente"])).json()["items"]
    assert [item["summary_id"] for item in listed] == [published["summary_id"]]
    one = client.get(f"/v1/portal/summaries/{published['summary_id']}", headers=_auth(tokens["cliente"]))
    assert one.status_code == 200
    assert one.json()["payload"]["sentences"][0].startswith("Em setembro/2026")
    for body in (one.json(), listed[0]):
        assert "created_by" not in body and "published_by" not in body
        assert "status" not in body and "withdrawn_reason" not in body
        assert body["competence"] == "2026-09"

    add_entity("le_two", "tenant_demo", "Empresa Dois", "300000000001")
    _seed_ledger(client, tokens, entity="le_two", period="le_two-2026-09")
    _close(client, tokens, "le_two-2026-09")
    other_url = "/v1/periods/le_two-2026-09/client-summary"
    assert _post(client, tokens["preparer"], other_url).status_code == 201
    other = _post(client, tokens["approver"], f"{other_url}/publish")
    assert other.status_code == 200, other.text
    response = client.get(f"/v1/portal/summaries/{other.json()['summary_id']}", headers=_auth(tokens["cliente"]))
    assert response.status_code == 404
    listed = client.get("/v1/portal/summaries", headers=_auth(tokens["cliente"])).json()["items"]
    assert len(listed) == 1


def _published_after_draft(client, tokens) -> dict:
    published = _post(client, tokens["approver"], f"{URL}/publish")
    assert published.status_code == 200, published.text
    return published.json()


def test_client_loses_summary_after_reopen(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    published = _published(client, tokens)
    path = f"/v1/portal/summaries/{published['summary_id']}"
    assert client.get(path, headers=_auth(tokens["cliente"])).status_code == 200
    _reopen(client, tokens)
    assert client.get(path, headers=_auth(tokens["cliente"])).status_code == 404
    assert client.get("/v1/portal/summaries", headers=_auth(tokens["cliente"])).json()["items"] == []


def test_office_user_cannot_use_portal_route(client, tokens, world):
    del world
    assert client.get("/v1/portal/summaries", headers=_auth(tokens["admin"])).status_code == 403
    assert client.get("/v1/portal/summaries/csum_x", headers=_auth(tokens["preparer"])).status_code == 403
    assert client.get(URL, headers=_auth(tokens["cliente"])).status_code == 403


def test_reopen_withdraws_draft_and_new_close_regenerates(client, tokens, world):
    del world
    _seed_ledger(client, tokens)
    _close(client, tokens)
    old = _post(client, tokens["preparer"], URL)
    assert old.status_code == 201
    _reopen(client, tokens)
    with get_admin_engine().begin() as connection:
        row = connection.execute(text("SELECT status, withdrawn_reason FROM client_summaries")).one()
    assert row.status == "withdrawn" and row.withdrawn_reason == "Competência reaberta"
    _publish(
        client,
        tokens,
        _journal_body(
            period_id=PERIOD,
            entry_date="2026-09-20",
            description="Venda nova",
            lines=[
                {"account_id": "le_test-1.1.02", "side": "debit", "amount": "500.00", "description": "Banco"},
                {"account_id": "le_test-4.1.01", "side": "credit", "amount": "500.00", "description": "Receita"},
            ],
        ),
    )
    _close(client, tokens)
    assert _post(client, tokens["approver"], f"{URL}/publish").status_code == 404
    fresh = _post(client, tokens["preparer"], URL)
    assert fresh.status_code == 201, fresh.text
    assert fresh.json()["summary_id"] != old.json()["summary_id"]
    assert fresh.json()["payload"]["revenue"] == "1500"


def test_office_get_shows_withdrawn_summary_with_reason(client, tokens, world):
    del world
    assert client.get(URL, headers=_auth(tokens["approver"])).status_code == 404
    _seed_ledger(client, tokens)
    _close(client, tokens)
    published = _published(client, tokens)
    done = _post(client, tokens["approver"], f"{URL}/withdraw", {"reason": "Número errado no resumo"})
    assert done.status_code == 200, done.text
    shown = client.get(URL, headers=_auth(tokens["approver"]))
    assert shown.status_code == 200, shown.text
    assert shown.json()["summary_id"] == published["summary_id"]
    assert shown.json()["status"] == "withdrawn"
    assert shown.json()["withdrawn_reason"] == "Número errado no resumo"
    again = _post(client, tokens["preparer"], URL)
    assert again.status_code == 201
    live = client.get(URL, headers=_auth(tokens["approver"])).json()
    assert live["status"] == "draft" and live["summary_id"] == again.json()["summary_id"]


MOVED = "cannot change tenant, entity or period"


@pytest.mark.parametrize(
    ("statement", "message"),
    [
        ("UPDATE client_summaries SET status = 'draft' WHERE id = 'cs_x'", "cannot go back to draft"),
        ("UPDATE client_summaries SET period_id = 'le_test-2026-08' WHERE id = 'cs_x'", MOVED),
        ("UPDATE client_summaries SET legal_entity_id = 'le_other' WHERE id = 'cs_x'", MOVED),
        ("UPDATE client_summaries SET tenant_id = 'tenant_other' WHERE id = 'cs_x'", MOVED),
    ],
)
def test_guard_blocks_backward_status_and_moves(client, tokens, world, statement, message):
    """Casa a mensagem do trigger, para o teste não passar por erro de chave estrangeira."""
    del client, tokens, world
    with get_admin_engine().begin() as connection:
        _insert_summary(connection)
    with pytest.raises(DBAPIError, match=message):
        with get_admin_engine().begin() as connection:
            connection.execute(text(statement))


def test_guard_blocks_leaving_withdrawn(client, tokens, world):
    del client, tokens, world
    with get_admin_engine().begin() as connection:
        _insert_summary(connection, "withdrawn")
    with pytest.raises(DBAPIError, match="withdrawn client summary cannot come back"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE client_summaries SET status = 'published' WHERE id = 'cs_x'"))
