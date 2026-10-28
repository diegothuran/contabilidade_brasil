from __future__ import annotations

from uuid import uuid4

from sqlalchemy.orm import Session

from contabil.seed.cnpj import cnpj_digits
from contabil.platform.db import session_factory
from contabil.worker import relay_once
from tests.integration.test_document_requests import _ask
from tests.integration.test_phase_a import _auth, _post


def _relay() -> None:
    session: Session = session_factory(admin=True)()
    try:
        relay_once(session)
        session.commit()
    finally:
        session.close()


def test_queue_stays_inside_the_office_and_orders_by_due_date(client, tokens, world):
    del world
    later = _ask(client, tokens["preparer"], title="Pedido mais tarde", due_on="2026-09-28")
    earlier = _ask(client, tokens["preparer"], title="Pedido mais cedo", due_on="2026-09-02")
    queue = client.get("/v1/document-requests/queue", headers=_auth(tokens["viewer"]))
    assert queue.status_code == 200, queue.text
    titles = [item["title"] for item in queue.json()["items"]]
    assert titles.index("Pedido mais cedo") < titles.index("Pedido mais tarde")
    assert earlier["document_request_id"]
    assert later["document_request_id"]
    assert all(item["blocks_close"] for item in queue.json()["items"] if item["title"].startswith("Pedido mais"))
    outsider = client.get("/v1/document-requests/queue", headers=_auth(tokens["outsider"]))
    assert outsider.status_code == 200
    assert "Pedido mais cedo" not in [item["title"] for item in outsider.json()["items"]]
    denied = client.get("/v1/document-requests/queue", headers=_auth(tokens["cliente"]))
    assert denied.status_code == 403


def test_client_sees_only_the_own_company_and_ignores_the_other_office(client, tokens, world):
    del world
    own = _ask(client, tokens["preparer"], title="Pedido do cliente", due_on="2026-09-15")
    number = cnpj_digits("910000000006")
    created = _post(
        client,
        tokens["admin"],
        "/v1/legal-entities",
        {"name": "Outra Empresa Ltda.", "cnpj": number, "fiscal_year": 2026},
    )
    assert created.status_code == 201, created.text
    other_id = created.json()["legal_entity_id"]
    period_id = f"{other_id}-2026-09"
    other = _post(
        client,
        tokens["preparer"],
        "/v1/document-requests",
        {
            "legal_entity_id": other_id,
            "period_id": period_id,
            "document_type": "receipt",
            "title": "Pedido de outra empresa",
            "due_on": "2026-09-20",
        },
    )
    assert other.status_code == 201, other.text
    listed = client.get("/v1/portal/document-requests", headers=_auth(tokens["cliente"]))
    assert listed.status_code == 200, listed.text
    titles = [item["title"] for item in listed.json()["items"]]
    assert "Pedido do cliente" in titles
    assert "Pedido de outra empresa" not in titles
    office = client.get("/v1/journals?legal_entity_id=le_test", headers=_auth(tokens["cliente"]))
    assert office.status_code == 403
    me = client.get("/v1/me", headers={**_auth(tokens["cliente"]), "X-Tenant-Id": "tenant_other"})
    assert me.status_code == 200, me.text
    assert me.json()["tenant_id"] == "tenant_demo"
    assert me.json()["legal_entity_id"] == "le_test"
    assert client.get("/v1/portal/document-requests", headers=_auth(tokens["preparer"])).status_code == 403
    uploaded = client.post(
        f"/v1/portal/document-requests/{own['document_request_id']}/content",
        files={"file": ("recibo-cliente.txt", b"arquivo do cliente\n", "text/plain")},
        headers=_auth(tokens["cliente"], uuid4().hex),
    )
    assert uploaded.status_code == 200, uploaded.text
    assert uploaded.json()["status"] == "received"
    foreign = client.post(
        f"/v1/portal/document-requests/{other.json()['document_request_id']}/content",
        files={"file": ("alheio.txt", b"nao deve entrar\n", "text/plain")},
        headers=_auth(tokens["cliente"], uuid4().hex),
    )
    assert foreign.status_code == 404


def test_client_history_stays_inside_the_company(client, tokens, world):
    del world
    own = _ask(client, tokens["preparer"], title="Pedido encerrado do cliente", due_on="2026-09-12")
    cancelled = _post(
        client,
        tokens["preparer"],
        f"/v1/document-requests/{own['document_request_id']}/cancel",
        {"reason": "O cliente entregou o documento por outro canal."},
    )
    assert cancelled.status_code == 200, cancelled.text
    number = cnpj_digits("910000000007")
    created = _post(
        client,
        tokens["admin"],
        "/v1/legal-entities",
        {"name": "Empresa do Histórico Ltda.", "cnpj": number, "fiscal_year": 2026},
    )
    assert created.status_code == 201, created.text
    other_id = created.json()["legal_entity_id"]
    other = _post(
        client,
        tokens["preparer"],
        "/v1/document-requests",
        {
            "legal_entity_id": other_id,
            "period_id": f"{other_id}-2026-09",
            "document_type": "receipt",
            "title": "Pedido encerrado de outra empresa",
            "due_on": "2026-09-18",
        },
    )
    assert other.status_code == 201, other.text
    _post(
        client,
        tokens["preparer"],
        f"/v1/document-requests/{other.json()['document_request_id']}/cancel",
        {"reason": "Este pedido pertence a outra empresa do escritório."},
    )
    history = client.get(
        "/v1/portal/document-requests",
        params={"status": "confirmed,cancelled"},
        headers=_auth(tokens["cliente"]),
    )
    assert history.status_code == 200, history.text
    titles = [item["title"] for item in history.json()["items"]]
    assert "Pedido encerrado do cliente" in titles
    assert "Pedido encerrado de outra empresa" not in titles
    own_item = next(item for item in history.json()["items"] if item["title"] == "Pedido encerrado do cliente")
    assert own_item["cancel_reason"]
    assert own_item["period"]
    assert history.json()["summary"]["open"] >= 0


def test_export_is_hashed_and_hidden_from_the_other_office(client, tokens, world):
    del world
    created = _post(
        client,
        tokens["preparer"],
        "/v1/legal-entities/le_test/exports",
        {"period_id": "le_test-2026-09", "kind": "operational_v1"},
    )
    assert created.status_code == 202, created.text
    export_id = created.json()["export_id"]
    waiting = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"]))
    assert waiting.status_code == 409
    _relay()
    ready = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"]))
    assert ready.status_code == 200, ready.text
    assert ready.json()["kind"] == "operational_v1"
    assert ready.json()["sha256"]
    assert ready.json()["trial_balance"]["debit_total"] == ready.json()["trial_balance"]["credit_total"]
    hidden = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["outsider"]))
    assert hidden.status_code == 404
    listed = client.get("/v1/operations?kind=operational_export", headers=_auth(tokens["viewer"]))
    assert listed.status_code == 200, listed.text
    assert any(item["operation_id"] == created.json()["operation_id"] for item in listed.json()["items"])
    assert client.get("/v1/operations", headers=_auth(tokens["cliente"])).status_code == 403
