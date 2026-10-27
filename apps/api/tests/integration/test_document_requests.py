from __future__ import annotations

import json
from uuid import uuid4

from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import text

from contabil.platform.db import get_engine
from tests.integration.test_phase_a import _auth, _post, _schemas


def _ask(client, token: str, *, title: str = "Recibo de aluguel", period: str = "le_test-2026-09", due_on: str = "2026-09-30") -> dict:
    response = _post(
        client,
        token,
        "/v1/document-requests",
        {
            "legal_entity_id": "le_test",
            "period_id": period,
            "document_type": "receipt",
            "title": title,
            "due_on": due_on,
        },
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_request_blocks_close_until_confirmed(client, tokens, world):
    del world
    created = _ask(client, tokens["preparer"])
    schema = json.loads((_schemas() / "document-request.schema.json").read_text(encoding="utf-8"))
    errors = list(Draft202012Validator(schema, format_checker=FormatChecker()).iter_errors(created))
    assert not errors, [error.message for error in errors]
    assert created["status"] == "open"
    assert created["document_id"] is None
    denied = _post(
        client,
        tokens["viewer"],
        "/v1/document-requests",
        {
            "legal_entity_id": "le_test",
            "period_id": "le_test-2026-09",
            "document_type": "receipt",
            "title": "Consulta não pede",
            "due_on": "2026-09-30",
        },
    )
    assert denied.status_code == 403
    opened = _post(client, tokens["approver"], "/v1/periods/le_test-2026-09/close-runs", {})
    assert opened.status_code == 201, opened.text
    run_id = opened.json()["close_run_id"]
    reviewed = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/items/trial_balance_review", {"status": "completed"})
    assert reviewed.status_code == 200, reviewed.text
    blocked = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert blocked.status_code == 409
    assert any(item["item_id"] == "document_requests_open" for item in blocked.json()["errors"])
    uploaded = client.post(
        f"/v1/document-requests/{created['document_request_id']}/content",
        files={"file": ("recibo.txt", b"recibo de teste\n", "text/plain")},
        headers=_auth(tokens["preparer"], uuid4().hex),
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "received"
    still = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert still.status_code == 409
    confirmed = _post(client, tokens["approver"], f"/v1/document-requests/{created['document_request_id']}/confirm")
    assert confirmed.status_code == 200, confirmed.text
    assert confirmed.json()["status"] == "confirmed"
    assert confirmed.json()["document_id"]
    closed = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert closed.status_code == 200, closed.text


def test_short_cancel_reason_is_rejected_and_other_office_cannot_see_the_request(client, tokens, world):
    del world
    created = _ask(client, tokens["admin"], title="Contrato social", period="le_test-2026-08", due_on="2026-08-31")
    short = _post(
        client,
        tokens["preparer"],
        f"/v1/document-requests/{created['document_request_id']}/cancel",
        {"reason": "curto"},
    )
    assert short.status_code == 400
    cancelled = _post(
        client,
        tokens["preparer"],
        f"/v1/document-requests/{created['document_request_id']}/cancel",
        {"reason": "O cliente enviou o contrato por outro canal."},
    )
    assert cancelled.status_code == 200, cancelled.text
    assert cancelled.json()["status"] == "cancelled"
    hidden = client.get(
        "/v1/document-requests",
        params={"legal_entity_id": "le_test", "period_id": "le_test-2026-08"},
        headers=_auth(tokens["outsider"]),
    )
    assert hidden.status_code == 404
    with get_engine().begin() as connection:
        connection.execute(text("SELECT set_config('app.tenant_id', 'tenant_other', true)"))
        seen = connection.execute(text("SELECT count(*) FROM document_requests")).scalar_one()
    assert seen == 0
    listed = client.get(
        "/v1/document-requests",
        params={"legal_entity_id": "le_test", "period_id": "le_test-2026-08"},
        headers=_auth(tokens["preparer"]),
    )
    assert listed.status_code == 200
    assert listed.json()["items"][0]["document_request_id"] == created["document_request_id"]
