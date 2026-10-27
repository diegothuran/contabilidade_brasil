from __future__ import annotations

from sqlalchemy import text

from contabil.platform.db import get_admin_engine
from tests.integration.test_phase_a import _auth, _journal_body, _post


def _ready_run(client, tokens, period_id: str) -> str:
    opened = _post(client, tokens["approver"], f"/v1/periods/{period_id}/close-runs", {})
    assert opened.status_code == 201, opened.text
    run_id = opened.json()["close_run_id"]
    reviewed = _post(
        client,
        tokens["approver"],
        f"/v1/close-runs/{run_id}/items/trial_balance_review",
        {"status": "completed"},
    )
    assert reviewed.status_code == 200, reviewed.text
    return run_id


def test_preparer_cannot_decide_or_close(client, tokens, world):
    del world
    opened = _post(client, tokens["preparer"], "/v1/periods/le_test-2026-08/close-runs", {})
    assert opened.status_code == 201, opened.text
    run_id = opened.json()["close_run_id"]
    denied = _post(
        client,
        tokens["preparer"],
        f"/v1/close-runs/{run_id}/items/trial_balance_review",
        {"status": "completed"},
    )
    assert denied.status_code == 403
    assert _post(client, tokens["preparer"], f"/v1/close-runs/{run_id}/close").status_code == 403


def test_close_writes_snapshot_and_package(client, tokens, world):
    del world
    run_id = _ready_run(client, tokens, "le_test-2026-08")
    closed = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["status"] == "closed"
    assert body["snapshot_sha256"]
    assert body["evidence_package_ref"].endswith("/evidence-package")
    package = client.get(f"/v1/close-runs/{run_id}/evidence-package", headers=_auth(tokens["approver"]))
    assert package.status_code == 200, package.text
    assert package.json()["snapshot_sha256"] == body["snapshot_sha256"]
    assert package.json()["snapshot"]["close_run_id"] == run_id
    assert "ICP-Brasil" in package.json()["manifest"]["disclaimer"]
    events = client.get("/v1/audit-events", headers=_auth(tokens["approver"]))
    assert any(item["event_type"] == "document_exported" and item["target_ref"] == run_id for item in events.json()["items"])
    denied = _post(
        client,
        tokens["preparer"],
        "/v1/journals",
        _journal_body(period_id="le_test-2026-08", entry_date="2026-08-10", description="Depois do fechamento"),
    )
    assert denied.status_code == 409


def test_reopen_preserves_snapshot_and_starts_another_run(client, tokens, world):
    del world
    run_id = _ready_run(client, tokens, "le_test-2026-09")
    closed = _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close")
    assert closed.status_code == 200, closed.text
    digest = closed.json()["snapshot_sha256"]
    request = _post(client, tokens["preparer"], "/v1/periods/le_test-2026-09/reopen-requests", {"reason": "Ajuste de competência"})
    assert request.status_code == 201, request.text
    approved = _post(client, tokens["approver"], f"/v1/reopen-requests/{request.json()['reopen_request_id']}/approve")
    assert approved.status_code == 200
    previous = client.get(f"/v1/close-runs/{run_id}", headers=_auth(tokens["approver"]))
    assert previous.status_code == 200
    assert previous.json()["status"] == "reopened"
    assert previous.json()["snapshot_sha256"] == digest
    second = _post(client, tokens["approver"], "/v1/periods/le_test-2026-09/close-runs", {})
    assert second.status_code == 201, second.text
    assert second.json()["run_number"] == 2
    assert second.json()["close_run_id"] != run_id


def test_snapshot_rejects_update(client, tokens, world):
    del world
    run_id = _ready_run(client, tokens, "le_test-2026-08")
    assert _post(client, tokens["approver"], f"/v1/close-runs/{run_id}/close").status_code == 200
    try:
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE close_snapshots SET sha256 = 'x' WHERE close_run_id = :id"), {"id": run_id})
    except Exception as exc:
        assert "immutable" in str(exc).lower()
        return
    raise AssertionError("o snapshot aceitou alteração")
