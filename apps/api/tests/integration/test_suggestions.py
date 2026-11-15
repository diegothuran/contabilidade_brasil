from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from contabil.platform.auth import apply_tenant
from contabil.platform.db import get_engine, session_factory
from contabil.suggestions.history import history_suggestions
from contabil.tables import BankAccount, BankTransaction, ReconciliationCase

from tests.integration.test_phase_a import _auth, _post
from tests.integration.test_phase_c import _drain
from tests.integration.world import add_entity


def _bank(client, token: str, entity: str = "le_test") -> str:
    created = _post(
        client,
        token,
        "/v1/bank-accounts",
        {
            "legal_entity_id": entity,
            "account_id": f"{entity}-1.1.02",
            "name": "Conta teste",
            "bank_code": "001",
            "branch": "1234",
            "account_number_masked": "6789",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["bank_account_id"]


def _csv(rows: list[tuple[str, str, str]]) -> bytes:
    lines = ["date;description;amount;external_id"]
    for index, (day, description, amount) in enumerate(rows):
        lines.append(f"{day};{description};{amount};ext-{uuid4().hex[:8]}-{index}")
    return ("\n".join(lines) + "\n").encode()


def _statement(client, token: str, bank_id: str, rows: list[tuple[str, str, str]], entity: str = "le_test") -> None:
    upload = client.post(
        "/v1/documents",
        files={"file": (f"extrato-{uuid4().hex[:6]}.csv", _csv(rows), "application/octet-stream")},
        data={"document_type": "bank_statement", "legal_entity_id": entity, "competence": "2026-09"},
        headers=_auth(token, uuid4().hex),
    )
    assert upload.status_code in {200, 201}, upload.text
    created = _post(client, token, f"/v1/bank-accounts/{bank_id}/statements", {"document_id": upload.json()["document_id"]})
    assert created.status_code == 202, created.text
    _drain()


def _cases(client, token: str, bank_id: str) -> list[dict]:
    response = client.get("/v1/reconciliation-cases", params={"bank_account_id": bank_id}, headers=_auth(token))
    assert response.status_code == 200, response.text
    return response.json()["items"]


def _case_by_description(client, token: str, bank_id: str, description: str, status: str | None = None) -> dict:
    for item in _cases(client, token, bank_id):
        if item["bank_transaction"]["description"] == description and (status is None or item["status"] == status):
            return item
    raise AssertionError(f"caso não encontrado: {description}")


def _resolve_with(client, tokens, case_id: str, account_id: str, **extra) -> dict:
    created = _post(
        client,
        tokens["preparer"],
        f"/v1/reconciliation-cases/{case_id}/journal",
        {"counterpart_account_id": account_id, **extra},
    )
    assert created.status_code == 201, created.text
    journal_id = created.json()["journal_id"]
    assert _post(client, tokens["preparer"], f"/v1/journals/{journal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/approve").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/publish").status_code == 200
    _drain()
    return created.json()


def _history_for(case_id: str) -> list:
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        case = session.scalar(select(ReconciliationCase).where(ReconciliationCase.id == case_id))
        transaction = session.scalar(select(BankTransaction).where(BankTransaction.id == case.transaction_id))
        bank = session.scalar(select(BankAccount).where(BankAccount.id == case.bank_account_id))
        return history_suggestions(session, "tenant_demo", case, transaction, bank)
    finally:
        session.rollback()
        session.close()


def test_history_suggests_previous_counterpart(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE SERVICOS", "-45.90")])
    first = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE SERVICOS")
    _resolve_with(client, tokens, first["case_id"], "le_test-5.1.01")
    _statement(client, tokens["preparer"], bank_id, [("2026-09-20", "TARIFA PACOTE SERVICOS", "-45.90")])
    second = [
        item
        for item in _cases(client, tokens["preparer"], bank_id)
        if item["case_id"] != first["case_id"]
    ][0]
    suggestions = _history_for(second["case_id"])
    assert [(item.account_id, item.confidence, item.source) for item in suggestions] == [("le_test-5.1.01", "média", "history")]
    assert _history_for(first["case_id"]) == []


def test_history_ignores_other_entity(client, tokens, world):
    del world
    add_entity("le_second", "tenant_demo", "Segunda Empresa", "100000000002")
    other_bank = _bank(client, tokens["preparer"], "le_second")
    _statement(client, tokens["preparer"], other_bank, [("2026-09-05", "TARIFA PACOTE SERVICOS", "-45.90")], "le_second")
    other_case = _case_by_description(client, tokens["preparer"], other_bank, "TARIFA PACOTE SERVICOS")
    _resolve_with(client, tokens, other_case["case_id"], "le_second-5.1.01")
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-20", "TARIFA PACOTE SERVICOS", "-45.90")])
    case = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE SERVICOS")
    assert _history_for(case["case_id"]) == []


@pytest.mark.parametrize("table", ["account_suggestions", "suggestion_runs"])
def test_suggestion_tables_are_insert_only(client, world, table):
    del client, world
    with get_engine().begin() as connection:
        apply = text("SELECT set_config('app.tenant_id', 'tenant_demo', true)")
        connection.execute(apply)
        assert connection.execute(text(f"SELECT count(*) FROM {table}")).scalar_one() == 0
    with pytest.raises(Exception, match="permission denied"):
        with get_engine().begin() as connection:
            connection.execute(text(f"UPDATE {table} SET created_at = now()"))
    with pytest.raises(Exception, match="permission denied"):
        with get_engine().begin() as connection:
            connection.execute(text(f"DELETE FROM {table}"))
