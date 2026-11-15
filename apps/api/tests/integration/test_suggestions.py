from __future__ import annotations

from datetime import datetime, timezone
from decimal import Decimal
from uuid import uuid4

import pytest
from sqlalchemy import select, text

from contabil.platform.auth import apply_tenant
from contabil.platform.db import get_admin_engine, get_engine, session_factory
from contabil.platform.outbox import HandlerOutcome
from contabil.platform.settings import get_settings
from contabil.suggestions.history import history_suggestions
from contabil.suggestions.model import FakeModelClient, ModelCallError
from contabil.suggestions.worker import run_counterpart_suggestions, used_today
from contabil.tables import Account, BankAccount, BankTransaction, Operation, ReconciliationCase, SuggestionRun

from tests.integration.test_phase_a import _auth, _post
from tests.integration.test_phase_c import _drain, _validate
from tests.integration.world import add_entity


def _bank(client, token: str, entity: str = "le_test", account_id: str | None = None) -> str:
    created = _post(
        client,
        token,
        "/v1/bank-accounts",
        {
            "legal_entity_id": entity,
            "account_id": account_id or f"{entity}-1.1.02",
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


def _payload(bank_id: str, operation_id: str) -> dict:
    return {
        "bank_account_id": bank_id,
        "period_id": "le_test-2026-09",
        "operation_id": operation_id,
        "legal_entity_id": "le_test",
    }


def _dispatch(payload: dict, client_fake: FakeModelClient):
    """Um despacho do handler, numa transação, como o relay faz."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        outcome = run_counterpart_suggestions(session, "tenant_demo", payload, client=client_fake)
        session.commit()
        return outcome
    finally:
        session.close()


def _next_payload(operation_id: str) -> dict | None:
    """Tira da fila a continuação enfileirada pelo despacho anterior."""
    with get_admin_engine().begin() as connection:
        row = connection.execute(
            text(
                """
                SELECT id, payload FROM outbox_events
                WHERE event_type = 'CounterpartSuggestionRequested' AND dispatched_at IS NULL
                  AND payload->>'operation_id' = :operation_id
                ORDER BY created_at LIMIT 1
                """
            ),
            {"operation_id": operation_id},
        ).first()
        if row is None:
            return None
        connection.execute(text("UPDATE outbox_events SET dispatched_at = now() WHERE id = :id"), {"id": row[0]})
        return row[1]


def _run_worker(bank_id: str, client_fake: FakeModelClient, operation_id: str | None = None, payload: dict | None = None) -> str:
    """Roda o despacho e as continuações até a operação não ter mais lote."""
    operation_id = operation_id or _operation()
    current: dict | None = payload or _payload(bank_id, operation_id)
    while current is not None:
        _dispatch(current, client_fake)
        current = _next_payload(operation_id)
    return operation_id


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
    # Reserva antes da chamada e resultado depois, os dois só de inserção.
    assert sorted(runs) == [(0, 100, 20, "end_turn", "contrapartida-1"), (2, 0, 0, "reserved", "contrapartida-1")]
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{operation_id}'") == [(None,)]
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
    assert sorted(_rows("SELECT transactions_sent, stop_reason FROM suggestion_runs")) == [(0, "end_turn"), (1, "reserved")]


def test_worker_stops_at_daily_limit(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90"), ("2026-09-06", "ALUGUEL", "-900.00")])
    settings_env.setenv("SUGGESTION_DAILY_LIMIT", "1")
    get_settings.cache_clear()
    fake = FakeModelClient({"t1": ("5.1.01", "alta")})
    operation_id = _run_worker(bank_id, fake)
    # Manda o que couber no teto (1 transação) e conclui com aviso.
    assert fake.sizes == [1]
    assert sorted(_rows("SELECT transactions_sent, stop_reason FROM suggestion_runs")) == [(0, "end_turn"), (1, "reserved")]
    assert _rows("SELECT count(*) FROM account_suggestions") == [(1,)]
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{operation_id}'") == [("limite_diario",)]
    again = FakeModelClient({"*": ("5.1.01", "alta")})
    second = _run_worker(bank_id, again)
    assert again.calls == 0
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{second}'") == [("limite_diario",)]


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
    assert sorted(row[0] for row in _rows("SELECT transactions_sent FROM suggestion_runs")) == [0, 0, 5, 40]


def _forty_five(client, tokens) -> str:
    bank_id = _bank(client, tokens["preparer"])
    rows = [(f"2026-09-{(index % 28) + 1:02d}", f"COMPRA LOJA {chr(65 + index % 26)}{index // 26}", f"-{index + 1}.00") for index in range(45)]
    _statement(client, tokens["preparer"], bank_id, rows)
    return bank_id


def _used_today(now=None) -> int:
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        return used_today(session, "tenant_demo", now=now)
    finally:
        session.close()


def test_failed_batch_keeps_runs_and_retry_skips_saved_cases(client, tokens, world):
    del world
    bank_id = _forty_five(client, tokens)
    operation_id = _operation()
    failing = FakeModelClient({"*": ("5.1.01", "média")}, fail_on_calls={2})
    assert _dispatch(_payload(bank_id, operation_id), failing) is HandlerOutcome.CONTINUES
    second = _next_payload(operation_id)
    assert second is not None and second["cursor"]
    with pytest.raises(ModelCallError):
        _dispatch(second, failing)
    assert failing.sizes == [40, 5]
    # O rollback do handler não apaga o que foi gravado na transação autônoma.
    assert sorted(_rows("SELECT transactions_sent, stop_reason FROM suggestion_runs")) == [
        (0, "end_turn"),
        (0, "error"),
        (5, "reserved"),
        (40, "reserved"),
    ]
    assert _rows("SELECT count(*) FROM account_suggestions") == [(40,)]
    assert _used_today() == 45
    # A falha desfez a transação do segundo despacho; a reentrega usa o mesmo payload.
    retry = FakeModelClient({"*": ("5.1.01", "média")})
    _run_worker(bank_id, retry, operation_id, payload=second)
    assert retry.sizes == [5]
    assert _rows("SELECT count(*) FROM account_suggestions") == [(45,)]
    assert _rows(f"SELECT count(DISTINCT case_id) FROM account_suggestions WHERE operation_id = '{operation_id}'") == [(45,)]


def test_daily_limit_counts_reservation_and_stops_before_second_batch(client, tokens, world, settings_env):
    del world
    bank_id = _forty_five(client, tokens)
    settings_env.setenv("SUGGESTION_DAILY_LIMIT", "44")
    get_settings.cache_clear()
    fake = FakeModelClient({"*": ("5.1.01", "média")})
    operation_id = _run_worker(bank_id, fake)
    # O segundo despacho manda o que cabe (4 de 5) e conclui com aviso.
    assert fake.sizes == [40, 4]
    assert _used_today() == 44
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{operation_id}'") == [("limite_diario",)]


def test_incomplete_answer_completes_with_warning(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    operation_id = _run_worker(bank_id, FakeModelClient({"t1": ("5.1.01", "alta")}, stop_reason="max_tokens"))
    assert _rows("SELECT count(*) FROM account_suggestions") == [(0,)]
    assert sorted(_rows("SELECT transactions_sent, input_tokens, stop_reason FROM suggestion_runs")) == [(0, 100, "max_tokens"), (1, 0, "reserved")]
    assert _rows(f"SELECT error_code FROM operations WHERE id = '{operation_id}'") == [("resposta_incompleta",)]


def test_used_today_turns_at_brasilia_midnight(client, world):
    del client, world
    operation_id = _operation()
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        for sent, moment in ((7, datetime(2026, 9, 15, 2, 59, tzinfo=timezone.utc)), (3, datetime(2026, 9, 15, 3, 1, tzinfo=timezone.utc))):
            session.add(
                SuggestionRun(
                    id=f"sgrun_{uuid4().hex}",
                    tenant_id="tenant_demo",
                    operation_id=operation_id,
                    model="teste",
                    prompt_version="contrapartida-1",
                    transactions_sent=sent,
                    input_tokens=0,
                    output_tokens=0,
                    stop_reason="reserved",
                    created_at=moment,
                )
            )
        session.commit()
    finally:
        session.close()
    # 02:59 UTC é 23:59 de 14/09 em Brasília; 03:01 UTC já é 15/09.
    assert _used_today(datetime(2026, 9, 15, 2, 59, 30, tzinfo=timezone.utc)) == 10
    assert _used_today(datetime(2026, 9, 15, 12, 0, tzinfo=timezone.utc)) == 3


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


def _reserve(sent: int) -> None:
    operation_id = _operation()
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        session.add(
            SuggestionRun(
                id=f"sgrun_{uuid4().hex}",
                tenant_id="tenant_demo",
                operation_id=operation_id,
                model="teste",
                prompt_version="contrapartida-1",
                transactions_sent=sent,
                input_tokens=0,
                output_tokens=0,
                stop_reason="reserved",
                created_at=datetime.now(timezone.utc),
            )
        )
        session.commit()
    finally:
        session.close()


def test_request_with_more_pending_than_limit_is_accepted(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-01", "COMPRA LOJA ZERO", "-1.00")])
    _clone_cases(bank_id, 599)
    assert _rows(f"SELECT count(*) FROM reconciliation_cases WHERE bank_account_id = '{bank_id}'") == [(600,)]
    _with_key(settings_env, limit=500)
    assert _used_today() == 0
    response = _request(client, tokens["preparer"], bank_id)
    assert response.status_code == 202, response.text
    audit = _rows("SELECT metadata->>'pending_cases' FROM audit_events WHERE metadata->>'action' = 'counterpart_suggestions_requested'")
    assert audit == [("600",)]


def test_request_over_limit_is_429_and_creates_no_operation(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90"), ("2026-09-06", "ALUGUEL", "-900.00")])
    _with_key(settings_env, limit=3)
    _reserve(3)
    before = _suggestion_operations()
    response = _request(client, tokens["preparer"], bank_id)
    assert response.status_code == 429, response.text
    assert response.json()["title"] == "Limite diário de sugestões por IA atingido"
    assert _suggestion_operations() == before
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
                # Sem sugestão calculada para o caso, a origem declarada vira manual.
                "suggestion_source": "manual",
                "suggestion_rank": None,
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


def test_journal_origin_and_rank_must_agree(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    case = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE")
    path = f"/v1/reconciliation-cases/{case['case_id']}/journal"
    refused = [
        {"suggestion_source": "history", "suggestion_rank": 2},
        {"suggestion_source": "model", "suggestion_rank": 3},
        {"suggestion_source": "model"},
        {"suggestion_source": "manual", "suggestion_rank": 1},
        {"suggestion_rank": 1},
    ]
    for extra in refused:
        response = _post(client, tokens["preparer"], path, {"counterpart_account_id": "le_test-5.1.01", **extra})
        assert response.status_code == 422, (extra, response.text)
    manual = _post(client, tokens["preparer"], path, {"counterpart_account_id": "le_test-5.1.01", "suggestion_source": "manual"})
    assert manual.status_code == 201, manual.text
    events = _rows("SELECT metadata FROM audit_events WHERE metadata->>'action' = 'reconciliation_counterpart_chosen'")
    assert [(item[0]["suggestion_source"], item[0]["suggestion_rank"]) for item in events] == [("manual", None)]


def _clone_cases(bank_id: str, count: int) -> None:
    """Copia o caso do extrato em `count` transações novas, direto no banco (rápido para volume)."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        base = session.scalar(select(BankTransaction).where(BankTransaction.bank_account_id == bank_id))
        case = session.scalar(select(ReconciliationCase).where(ReconciliationCase.transaction_id == base.id))
        for index in range(count):
            transaction = BankTransaction(
                id=f"btx_{uuid4().hex}",
                tenant_id="tenant_demo",
                bank_account_id=bank_id,
                statement_id=base.statement_id,
                transaction_date=base.transaction_date.replace(day=(index % 28) + 1),
                amount=Decimal(index + 2),
                direction="outflow",
                description=f"COMPRA LOJA {chr(65 + index % 26)}{index // 26}",
                external_id=None,
                fingerprint=uuid4().hex,
            )
            session.add(transaction)
            session.flush()
            session.add(
                ReconciliationCase(
                    id=f"rcase_{uuid4().hex}",
                    schema_version=case.schema_version,
                    tenant_id="tenant_demo",
                    bank_account_id=bank_id,
                    account_id=case.account_id,
                    transaction_id=transaction.id,
                    status="open",
                    candidates=[],
                )
            )
        session.commit()
    finally:
        session.close()


def test_request_at_limit_is_429(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    _with_key(settings_env, limit=10)
    _reserve(9)
    assert _request(client, tokens["preparer"], bank_id).status_code == 202
    _reserve(1)
    assert _used_today() == 10
    refused = _request(client, tokens["preparer"], bank_id)
    assert refused.status_code == 429, refused.text


def _relay_once() -> int:
    from contabil.worker import relay_once

    session = session_factory(admin=True)()
    try:
        count = relay_once(session)
        session.commit()
        return count
    finally:
        session.close()


def test_eighty_five_cases_take_three_dispatches(client, tokens, world, settings_env):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-01", "COMPRA LOJA ZERO", "-1.00")])
    _clone_cases(bank_id, 84)
    _with_key(settings_env)
    fake = FakeModelClient({"*": ("5.1.01", "média")})
    settings_env.setattr("contabil.suggestions.worker.AnthropicModelClient", lambda api_key, model: fake)
    response = _request(client, tokens["preparer"], bank_id)
    assert response.status_code == 202, response.text
    operation_id = response.json()["operation_id"]
    statuses = []
    for _ in range(3):
        assert _relay_once() == 1
        statuses.append(_rows(f"SELECT status FROM operations WHERE id = '{operation_id}'")[0][0])
    assert _relay_once() == 0
    assert fake.calls == 3
    assert fake.sizes == [40, 40, 5]
    assert statuses == ["running", "running", "completed"]
    assert _rows(f"SELECT count(DISTINCT case_id) FROM account_suggestions WHERE operation_id = '{operation_id}'") == [(85,)]
    assert _used_today() == 85
    events = _rows(
        "SELECT payload->'cursor' IS NOT NULL, dispatched_at IS NOT NULL FROM outbox_events "
        "WHERE event_type = 'CounterpartSuggestionRequested' ORDER BY created_at"
    )
    assert events == [(False, True), (True, True), (True, True)]


def test_redelivered_dispatch_does_not_pay_again(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-01", "COMPRA LOJA ZERO", "-1.00")])
    _clone_cases(bank_id, 84)
    operation_id = _operation()
    first = _payload(bank_id, operation_id)
    fake = FakeModelClient({"*": ("5.1.01", "média")})
    assert _dispatch(first, fake) is HandlerOutcome.CONTINUES
    # A reentrega do mesmo despacho cai na mesma janela, já sugerida: não chama o modelo.
    assert _dispatch(first, fake) is HandlerOutcome.CONTINUES
    assert fake.sizes == [40]
    assert _used_today() == 40
    # As duas continuações apontam para o mesmo cursor; a segunda também não paga de novo.
    second = _next_payload(operation_id)
    duplicate = _next_payload(operation_id)
    assert second == duplicate
    assert _dispatch(second, fake) is HandlerOutcome.CONTINUES
    assert _dispatch(duplicate, fake) is HandlerOutcome.CONTINUES
    assert fake.sizes == [40, 40]
    _run_worker(bank_id, fake, operation_id, payload=_next_payload(operation_id))
    assert fake.sizes == [40, 40, 5]
    assert _used_today() == 85


def test_history_never_suggests_the_current_bank_account(client, tokens, world):
    del world
    session = session_factory(admin=True)()
    try:
        session.add(
            Account(
                id="le_test-1.1.03",
                tenant_id="tenant_demo",
                legal_entity_id="le_test",
                chart_id="chart_le_test",
                code="1.1.03",
                name="Banco dois",
                account_type="asset",
                postable=True,
                active=True,
            )
        )
        session.commit()
    finally:
        session.close()
    bank_a = _bank(client, tokens["preparer"])
    bank_b = _bank(client, tokens["preparer"], account_id="le_test-1.1.03")
    _statement(client, tokens["preparer"], bank_b, [("2026-09-05", "TRANSF ENTRE CONTAS PROPRIAS", "-300.00")])
    past = _case_by_description(client, tokens["preparer"], bank_b, "TRANSF ENTRE CONTAS PROPRIAS")
    # No banco B, a contrapartida foi a conta contábil do banco A.
    _resolve_with(client, tokens, past["case_id"], "le_test-1.1.02")
    _statement(client, tokens["preparer"], bank_a, [("2026-09-20", "TRANSF ENTRE CONTAS PROPRIAS", "-300.00")])
    current = _case_by_description(client, tokens["preparer"], bank_a, "TRANSF ENTRE CONTAS PROPRIAS")
    assert _history_for(current["case_id"]) == []
    assert current["counterpart_suggestions"] == []


def test_journal_refuses_bank_account_as_counterpart(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-05", "TARIFA PACOTE", "-45.90")])
    case = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE")
    response = _post(
        client,
        tokens["preparer"],
        f"/v1/reconciliation-cases/{case['case_id']}/journal",
        {"counterpart_account_id": "le_test-1.1.02"},
    )
    assert response.status_code == 422, response.text
    assert "A contrapartida não pode ser a própria conta do banco." in response.text
    assert _rows("SELECT count(*) FROM journal_entries WHERE source_type = 'bank'") == [(0,)]


def test_journal_origin_is_checked_against_first_suggestion(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, [("2026-09-02", "TARIFA PACOTE SERVICOS", "-45.90")])
    first = _case_by_description(client, tokens["preparer"], bank_id, "TARIFA PACOTE SERVICOS")
    _resolve_with(client, tokens, first["case_id"], "le_test-5.1.01")
    _statement(
        client,
        tokens["preparer"],
        bank_id,
        [
            ("2026-09-10", "TARIFA PACOTE SERVICOS", "-45.91"),
            ("2026-09-15", "TARIFA PACOTE SERVICOS", "-45.92"),
            ("2026-09-20", "TARIFA PACOTE SERVICOS", "-45.93"),
        ],
    )
    others = sorted(
        (item for item in _cases(client, tokens["preparer"], bank_id) if item["case_id"] != first["case_id"]),
        key=lambda item: item["bank_transaction"]["date"],
    )
    assert [item["counterpart_suggestions"][0]["account_id"] for item in others] == ["le_test-5.1.01"] * 3
    chosen = [
        (others[0], {"counterpart_account_id": "le_test-2.1.01", "suggestion_source": "history", "suggestion_rank": 1}),
        (others[1], {"counterpart_account_id": "le_test-5.1.01", "suggestion_source": "model", "suggestion_rank": 1}),
        (others[2], {"counterpart_account_id": "le_test-5.1.01", "suggestion_source": "history", "suggestion_rank": 1}),
    ]
    journals = []
    for case, body in chosen:
        created = _post(client, tokens["preparer"], f"/v1/reconciliation-cases/{case['case_id']}/journal", body)
        assert created.status_code == 201, created.text
        journals.append(created.json()["journal_id"])
    events = {
        item[0]["journal_id"]: (item[0]["suggestion_source"], item[0]["suggestion_rank"])
        for item in _rows("SELECT metadata FROM audit_events WHERE metadata->>'action' = 'reconciliation_counterpart_chosen'")
    }
    assert [events[journal_id] for journal_id in journals] == [("manual", None), ("manual", None), ("history", 1)]
