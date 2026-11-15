from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from contabil.platform.auth import apply_tenant
from contabil.platform.db import get_admin_engine, get_engine, session_factory
from contabil.platform.settings import get_settings
from contabil.suggestions.history import history_suggestions
from contabil.suggestions.model import FakeModelClient
from contabil.suggestions.worker import run_counterpart_suggestions
from contabil.tables import Account, BankAccount, BankTransaction, Operation, ReconciliationCase

from tests.integration.test_phase_a import _auth, _post
from tests.integration.test_phase_c import _drain, _validate
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


def _operation() -> str:
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        operation = Operation(
            id=f"op_{uuid4().hex}",
            tenant_id="tenant_demo",
            kind="counterpart_suggestions",
            status="accepted",
            correlation_id="teste",
            target_ref="teste",
        )
        session.add(operation)
        session.commit()
        return operation.id
    finally:
        session.close()


def _run_worker(bank_id: str, client_fake: FakeModelClient, operation_id: str | None = None) -> str:
    operation_id = operation_id or _operation()
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        payload = {
            "bank_account_id": bank_id,
            "period_id": "le_test-2026-09",
            "operation_id": operation_id,
            "legal_entity_id": "le_test",
        }
        run_counterpart_suggestions(session, "tenant_demo", payload, client=client_fake)
        session.commit()
        return operation_id
    finally:
        session.close()


def _rows(sql: str) -> list:
    with get_admin_engine().connect() as connection:
        return list(connection.execute(text(sql)).all())


@pytest.fixture
def settings_env(monkeypatch):
    get_settings.cache_clear()
    yield monkeypatch
    monkeypatch.undo()
    get_settings.cache_clear()


def test_worker_saves_valid_suggestions(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90"), ("2026-09-06", "PIX RECEBIDO ANA", "120.00")])
    fake = FakeModelClient({"t1": ("5.1.01", "alta"), "t2": ("3.1.01", "palpite")})
    operation_id = _run_worker(bank_id, fake)
    assert fake.calls == 1
    saved = _rows("SELECT account_id, confidence, source, provider_version, operation_id FROM account_suggestions ORDER BY account_id")
    assert {(row[0], row[1], row[2]) for row in saved} == {("le_test-5.1.01", "alta", "model"), ("le_test-3.1.01", "baixa", "model")}
    assert all(row[3] == f"{get_settings().suggestion_model}/contrapartida-1" and row[4] == operation_id for row in saved)
    runs = _rows("SELECT transactions_sent, input_tokens, output_tokens, stop_reason, prompt_version FROM suggestion_runs")
    assert runs == [(2, 100, 20, "end_turn", "contrapartida-1")]
    assert _rows(f"SELECT status FROM operations WHERE id = '{operation_id}'") == [("running",)]


def test_worker_discards_other_entity_account(client, tokens, world):
    del world
    add_entity("le_second", "tenant_demo", "Segunda Empresa", "100000000002")
    session = session_factory(admin=True)()
    try:
        session.add(
            Account(
                id="le_second-9.9.99",
                tenant_id="tenant_demo",
                legal_entity_id="le_second",
                chart_id="chart_le_second",
                code="9.9.99",
                name="Conta só da outra empresa",
                account_type="expense",
                postable=True,
                active=True,
            )
        )
        session.commit()
    finally:
        session.close()
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    fake = FakeModelClient({"t1": ("9.9.99", "alta"), "t7": ("5.1.01", "alta")})
    _run_worker(bank_id, fake)
    assert fake.calls == 1
    assert _rows("SELECT count(*) FROM account_suggestions") == [(0,)]
    assert _rows("SELECT transactions_sent FROM suggestion_runs") == [(1,)]


def test_worker_stops_at_daily_limit(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90"), ("2026-09-06", "ALUGUEL", "-900.00")])
    settings_env.setenv("SUGGESTION_DAILY_LIMIT", "1")
    get_settings.cache_clear()
    fake = FakeModelClient({"t1": ("5.1.01", "alta")})
    _run_worker(bank_id, fake)
    assert fake.calls == 0
    assert _rows("SELECT count(*) FROM suggestion_runs") == [(0,)]
    assert _rows("SELECT count(*) FROM account_suggestions") == [(0,)]


def test_worker_batches_of_40(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    rows = [(f"2026-09-{(index % 28) + 1:02d}", f"COMPRA LOJA {chr(65 + index % 26)}{index // 26}", f"-{index + 1}.00") for index in range(45)]
    _statement(client, tokens["preparer"], bank_id, rows)
    assert len(_cases(client, tokens["preparer"], bank_id)) == 45
    fake = FakeModelClient({})
    _run_worker(bank_id, fake)
    assert fake.calls == 2
    assert fake.sizes == [40, 5]
    assert sorted(row[0] for row in _rows("SELECT transactions_sent FROM suggestion_runs")) == [5, 40]


def _request(client, token: str, bank_id: str):
    return _post(client, token, f"/v1/bank-accounts/{bank_id}/counterpart-suggestions", {"period_id": "le_test-2026-09"})


def _suggestion_operations() -> int:
    return _rows("SELECT count(*) FROM operations WHERE kind = 'counterpart_suggestions'")[0][0]


def _with_key(settings_env, limit: int | None = None) -> None:
    settings_env.setenv("CLAUDE_API_KEY", "chave-de-teste-sem-uso")
    if limit is not None:
        settings_env.setenv("SUGGESTION_DAILY_LIMIT", str(limit))
    get_settings.cache_clear()


def test_request_without_key_is_503(client, tokens, world, settings_env):
    del world
    settings_env.setenv("CLAUDE_API_KEY", "")
    get_settings.cache_clear()
    bank_id = _bank(client, tokens["preparer"])
    response = _request(client, tokens["preparer"], bank_id)
    assert response.status_code == 503, response.text
    assert response.json()["title"] == "Sugestão por IA indisponível"
    assert _suggestion_operations() == 0


def test_request_over_limit_is_429_and_creates_no_operation(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90"), ("2026-09-06", "ALUGUEL", "-900.00")])
    _with_key(settings_env, limit=1)
    response = _request(client, tokens["preparer"], bank_id)
    assert response.status_code == 429, response.text
    assert response.json()["title"] == "Limite diário de sugestões por IA atingido"
    assert _suggestion_operations() == 0
    assert _rows("SELECT count(*) FROM outbox_events WHERE event_type = 'CounterpartSuggestionRequested'") == [(0,)]


def test_request_creates_operation_and_event(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    _with_key(settings_env)
    # Nenhum teste chama a rede: o worker recebe um cliente falso no lugar do SDK.
    settings_env.setattr(
        "contabil.suggestions.worker.AnthropicModelClient",
        lambda api_key, model: FakeModelClient({"t1": ("5.1.01", "média")}),
    )
    key = uuid4().hex
    path = f"/v1/bank-accounts/{bank_id}/counterpart-suggestions"
    response = _post(client, tokens["preparer"], path, {"period_id": "le_test-2026-09"}, key)
    assert response.status_code == 202, response.text
    body = response.json()
    assert body["status"] == "accepted" and body["kind"] == "counterpart_suggestions"
    replay = _post(client, tokens["preparer"], path, {"period_id": "le_test-2026-09"}, key)
    assert replay.json()["operation_id"] == body["operation_id"]
    assert _suggestion_operations() == 1
    events = _rows("SELECT payload FROM outbox_events WHERE event_type = 'CounterpartSuggestionRequested'")
    assert events == [
        ({"bank_account_id": bank_id, "period_id": "le_test-2026-09", "operation_id": body["operation_id"], "legal_entity_id": "le_test"},)
    ]
    audit = _rows("SELECT metadata FROM audit_events WHERE metadata->>'action' = 'counterpart_suggestions_requested'")
    assert len(audit) == 1
    _drain()
    assert _rows(f"SELECT status FROM operations WHERE id = '{body['operation_id']}'") == [("completed",)]
    case = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE")
    assert case["model_suggestions_enabled"] is True
    assert [(item["account_id"], item["source"], item["confidence"]) for item in case["counterpart_suggestions"]] == [
        ("le_test-5.1.01", "model", "média")
    ]
    _validate("reconciliation-case.schema.json", case)


def test_case_shows_history_then_model_without_duplicates(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE SERVICOS", "-45.90")])
    first = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE SERVICOS")
    _resolve_with(client, tokens, first["case_id"], "le_test-5.1.01")
    _statement(client, tokens["preparer"], bank_id, [("2026-09-20", "TARIFA PACOTE SERVICOS", "-45.90")])
    second_id = [item["case_id"] for item in _cases(client, tokens["preparer"], bank_id) if item["case_id"] != first["case_id"]][0]
    _run_worker(bank_id, FakeModelClient({"t1": ("2.1.01", "baixa")}))
    case = client.get(f"/v1/reconciliation-cases/{second_id}", headers=_auth(tokens["preparer"])).json()
    assert case["model_suggestions_enabled"] is False
    assert [(item["account_id"], item["source"]) for item in case["counterpart_suggestions"]] == [
        ("le_test-5.1.01", "history"),
        ("le_test-2.1.01", "model"),
    ]
    _validate("reconciliation-case.schema.json", case)
    _run_worker(bank_id, FakeModelClient({"t1": ("5.1.01", "alta")}))
    case = client.get(f"/v1/reconciliation-cases/{second_id}", headers=_auth(tokens["preparer"])).json()
    assert [(item["account_id"], item["source"]) for item in case["counterpart_suggestions"]] == [("le_test-5.1.01", "history")]
    resolved = client.get(f"/v1/reconciliation-cases/{first['case_id']}", headers=_auth(tokens["preparer"])).json()
    assert resolved["counterpart_suggestions"] == []


def test_journal_records_suggestion_source(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    case = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE")
    path = f"/v1/reconciliation-cases/{case['case_id']}/journal"
    invalid = _post(client, tokens["preparer"], path, {"counterpart_account_id": "le_test-5.1.01", "suggestion_source": "palpite"})
    assert invalid.status_code == 422
    created = _post(
        client,
        tokens["preparer"],
        path,
        {"counterpart_account_id": "le_test-5.1.01", "suggestion_source": "history", "suggestion_rank": 1},
    )
    assert created.status_code == 201, created.text
    events = _rows("SELECT metadata FROM audit_events WHERE metadata->>'action' = 'reconciliation_counterpart_chosen'")
    assert events == [
        (
            {
                "action": "reconciliation_counterpart_chosen",
                "case_id": case["case_id"],
                "journal_id": created.json()["journal_id"],
                "suggestion_source": "history",
                "suggestion_rank": 1,
            },
        )
    ]


def test_client_cannot_request(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _with_key(settings_env)
    assert _request(client, tokens["cliente"], bank_id).status_code == 403
    assert _request(client, tokens["viewer"], bank_id).status_code == 403
    assert _request(client, tokens["outsider"], bank_id).status_code == 404
    assert _suggestion_operations() == 0
