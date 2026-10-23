from __future__ import annotations

import json
from uuid import uuid4

import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import text

from contabil.platform.db import get_admin_engine

from tests.integration.test_phase_a import _auth, _journal_body, _post, _publish, _schemas
from tests.integration.test_phase_b import _relay


def _validate(name: str, payload: dict) -> None:
    schema = json.loads((_schemas() / name).read_text(encoding="utf-8"))
    Draft202012Validator(schema, format_checker=FormatChecker()).validate(payload)


def _drain() -> None:
    for _ in range(6):
        if _relay() == 0:
            return


def _upload(client, token: str, content: bytes, name: str) -> str:
    response = client.post(
        "/v1/documents",
        files={"file": (name, content, "application/octet-stream")},
        data={"document_type": "bank_statement", "legal_entity_id": "le_test", "competence": "2026-09"},
        headers=_auth(token, uuid4().hex),
    )
    assert response.status_code in {200, 201}, response.text
    return response.json()["document_id"]


def _bank(client, token: str) -> str:
    created = _post(
        client,
        token,
        "/v1/bank-accounts",
        {
            "legal_entity_id": "le_test",
            "account_id": "le_test-1.1.02",
            "name": "Conta teste",
            "bank_code": "001",
            "branch": "1234",
            "account_number_masked": "6789",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["bank_account_id"]


def _statement(client, token: str, bank_id: str, content: bytes, name: str) -> dict:
    document_id = _upload(client, token, content, name)
    created = _post(client, token, f"/v1/bank-accounts/{bank_id}/statements", {"document_id": document_id})
    assert created.status_code == 202, created.text
    _drain()
    statement = client.get(f"/v1/bank-statements/{created.json()['statement_id']}", headers=_auth(token))
    assert statement.status_code == 200, statement.text
    return statement.json()


def _cases(client, token: str, bank_id: str) -> list[dict]:
    response = client.get("/v1/reconciliation-cases", params={"bank_account_id": bank_id}, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["items"]


OFX = (
    "OFXHEADER:100\nCHARSET:1252\n\n<OFX>\n"
    "<STMTTRN>\n<DTPOSTED>20260915\n<TRNAMT>300.00\n<FITID>fit-a\n<MEMO>Recebimento cliente\n</STMTTRN>\n"
    "<STMTTRN>\n<DTPOSTED>20260915\n<TRNAMT>300.00\n<FITID>fit-b\n<MEMO>Recebimento cliente\n</STMTTRN>\n"
    "<STMTTRN>\n<DTPOSTED>20260916\n<TRNAMT>-45.90\n<FITID>fit-fee\n<MEMO>TARIFA\n</STMTTRN>\n"
    "</OFX>\n"
).encode("cp1252")


def test_statement_suggests_reimport_and_summary(client, tokens, world):
    del world
    _publish(
        client,
        tokens,
        _journal_body(
            description="Recebimento cliente",
            entry_date="2026-09-15",
            lines=[
                {"account_id": "le_test-1.1.02", "side": "debit", "amount": "300.00", "description": "Recebimento cliente"},
                {"account_id": "le_test-3.1.01", "side": "credit", "amount": "300.00", "description": "Capital"},
            ],
        ),
    )
    bank_id = _bank(client, tokens["preparer"])
    first = _statement(client, tokens["preparer"], bank_id, OFX, "extrato.ofx")
    assert first["status"] == "parsed"
    assert first["transactions_new"] == 3
    assert first["transactions_duplicate"] == 0
    cases = _cases(client, tokens["preparer"], bank_id)
    assert len(cases) == 3
    suggested = [item for item in cases if item["bank_transaction"]["external_id"] == "fit-a"][0]
    duplicate = [item for item in cases if item["bank_transaction"]["external_id"] == "fit-b"][0]
    fee = [item for item in cases if item["bank_transaction"]["external_id"] == "fit-fee"][0]
    assert suggested["status"] == "suggested"
    assert "Valor idêntico" in suggested["candidates"][0]["explanation"]
    assert fee["status"] == "open"
    assert fee["candidates"] == []
    _validate("reconciliation-case.schema.json", suggested)
    _validate("reconciliation-case.schema.json", fee)
    again = _statement(client, tokens["preparer"], bank_id, OFX, "extrato-de-novo.ofx")
    assert again["transactions_new"] == 0
    assert again["transactions_duplicate"] == 3
    assert len(_cases(client, tokens["preparer"], bank_id)) == 3
    before = client.get(
        f"/v1/bank-accounts/{bank_id}/summary",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    assert before.status_code == 200, before.text
    assert before.json()["pending_inflow_count"] == 2
    assert before.json()["pending_outflow_count"] == 1
    assert before.json()["unmatched_ledger_count"] == 1
    denied = _post(
        client,
        tokens["preparer"],
        f"/v1/reconciliation-cases/{suggested['case_id']}/approve",
        {"candidate_id": suggested["candidates"][0]["candidate_id"]},
    )
    assert denied.status_code == 403
    approved = _post(
        client,
        tokens["approver"],
        f"/v1/reconciliation-cases/{suggested['case_id']}/approve",
        {"candidate_id": suggested["candidates"][0]["candidate_id"]},
    )
    assert approved.status_code == 200, approved.text
    assert approved.json()["status"] == "approved"
    assert approved.json()["approved_by"] == "approver"
    assert approved.json()["selected_candidate_id"]
    assert approved.json()["audit_event_id"]
    _validate("reconciliation-case.schema.json", approved.json())
    events = client.get("/v1/audit-events", headers=_auth(tokens["approver"]))
    assert any(item["event_id"] == approved.json()["audit_event_id"] and item["event_type"] == "reconciliation_approved" for item in events.json()["items"])
    conflict = _post(
        client,
        tokens["approver"],
        f"/v1/reconciliation-cases/{duplicate['case_id']}/approve",
        {"candidate_id": suggested["candidates"][0]["candidate_id"]},
    )
    assert conflict.status_code == 409
    with get_admin_engine().connect() as connection:
        before_count = int(connection.execute(text("SELECT count(*) FROM bank_transactions")).scalar_one())
    rejected = _post(client, tokens["preparer"], f"/v1/reconciliation-cases/{fee['case_id']}/reject", {"reason": "Não é esta tarifa"})
    assert rejected.status_code == 200, rejected.text
    assert rejected.json()["status"] == "rejected"
    with get_admin_engine().connect() as connection:
        assert int(connection.execute(text("SELECT count(*) FROM bank_transactions")).scalar_one()) == before_count
    ignored = _post(client, tokens["preparer"], f"/v1/reconciliation-cases/{duplicate['case_id']}/ignore", {"reason": "Lançamento já ligado"})
    assert ignored.status_code == 200, ignored.text
    after = client.get(
        f"/v1/bank-accounts/{bank_id}/summary",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    assert after.json()["pending_inflow_count"] == 0
    assert after.json()["pending_outflow_count"] == 0
    assert after.json()["unmatched_ledger_count"] == 0
    reversed_case = _post(client, tokens["approver"], f"/v1/reconciliation-cases/{suggested['case_id']}/reverse", {"reason": "Ligação indevida"})
    assert reversed_case.status_code == 200, reversed_case.text
    assert reversed_case.json()["status"] == "reversed"
    with get_admin_engine().connect() as connection:
        active = int(connection.execute(text("SELECT count(*) FROM reconciliation_matches WHERE active")).scalar_one())
    assert active == 0
    suggested_again = _post(client, tokens["preparer"], f"/v1/reconciliation-cases/{suggested['case_id']}/resuggest")
    assert suggested_again.status_code == 200, suggested_again.text
    assert suggested_again.json()["status"] == "suggested"


def test_duplicate_without_fitid_is_counted(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    content = "date;description;amount;external_id\n2026-09-10;Tarifa;-10.00;\n2026-09-10;Tarifa;-10.00;\n".encode()
    statement = _statement(client, tokens["preparer"], bank_id, content, "extrato.csv")
    assert statement["transactions_received"] == 2
    assert statement["transactions_new"] == 1
    assert statement["transactions_duplicate"] == 1
    assert len(_cases(client, tokens["preparer"], bank_id)) == 1


def test_journal_from_case_resolves_when_published(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    content = (
        "OFXHEADER:100\n\n<OFX>\n<STMTTRN>\n<DTPOSTED>20260916\n<TRNAMT>-45.90\n<FITID>fee-only\n<MEMO>TARIFA\n</STMTTRN>\n</OFX>\n"
    ).encode()
    _statement(client, tokens["preparer"], bank_id, content, "tarifa.ofx")
    case = _cases(client, tokens["preparer"], bank_id)[0]
    assert case["status"] == "open"
    created = _post(
        client,
        tokens["preparer"],
        f"/v1/reconciliation-cases/{case['case_id']}/journal",
        {"counterpart_account_id": "le_test-5.1.01", "description": "Tarifa bancária"},
    )
    assert created.status_code == 201, created.text
    journal_id = created.json()["journal_id"]
    assert created.json()["source"]["source_type"] == "bank"
    assert _post(client, tokens["preparer"], f"/v1/journals/{journal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/approve").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/publish").status_code == 200
    _drain()
    resolved = client.get(f"/v1/reconciliation-cases/{case['case_id']}", headers=_auth(tokens["preparer"]))
    assert resolved.status_code == 200, resolved.text
    assert resolved.json()["status"] == "approved"
    assert resolved.json()["approved_by"] == "approver"
    assert resolved.json()["candidates"][0]["explanation"] == ["Lançamento criado a partir desta transação e publicado"]
    _validate("reconciliation-case.schema.json", resolved.json())


def test_bank_transaction_is_immutable_and_hidden_across_tenants(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(
        client,
        tokens["preparer"],
        bank_id,
        b"date;description;amount;external_id\n2026-09-10;Pix;15.00;pix-1\n",
        "pix.csv",
    )
    hidden = client.get(
        f"/v1/bank-accounts/{bank_id}/summary",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["outsider"]),
    )
    assert hidden.status_code == 404
    assert client.get("/v1/reconciliation-cases", params={"bank_account_id": bank_id}, headers=_auth(tokens["outsider"])).status_code == 404
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("UPDATE bank_transactions SET description = 'trocada'"))
    with pytest.raises(Exception, match="immutable"):
        with get_admin_engine().begin() as connection:
            connection.execute(text("DELETE FROM bank_transactions"))
