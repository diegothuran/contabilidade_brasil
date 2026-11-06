from __future__ import annotations

from datetime import date

from sqlalchemy import update

from contabil.platform.db import session_factory
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import AccountingPeriod
from tests.integration.test_phase_a import _auth, _post, _publish


def _company(client, tokens, seed: str) -> str:
    number = cnpj_digits(seed)
    created = _post(
        client,
        tokens["admin"],
        "/v1/legal-entities",
        {"name": f"Empresa {seed}", "cnpj": f"{number[:2]}.{number[2:5]}.{number[5:8]}/{number[8:12]}-{number[12:]}", "fiscal_year": 2026},
    )
    assert created.status_code == 201, created.text
    return created.json()["legal_entity_id"]


def _entry(entity: str, month: int, debit: str, credit: str, amount: str, description: str) -> dict:
    return {
        "legal_entity_id": entity,
        "period_id": f"{entity}-2026-{month:02d}",
        "currency": "BRL",
        "entry_date": date(2026, month, 10).isoformat(),
        "description": description,
        "lines": [
            {"account_id": f"{entity}-{debit}", "side": "debit", "amount": amount, "description": description},
            {"account_id": f"{entity}-{credit}", "side": "credit", "amount": amount, "description": description},
        ],
    }


def _closing(client, token: str, entity: str, account: str = "3.2.01"):
    return _post(
        client,
        token,
        f"/v1/legal-entities/{entity}/year-end-closing",
        {"fiscal_year": 2026, "retained_earnings_account_id": f"{entity}-{account}"},
    )


def _approve_and_publish(client, tokens, journal_id: str, submitter: str = "preparer") -> None:
    assert _post(client, tokens[submitter], f"/v1/journals/{journal_id}/submit").status_code == 200
    assert _post(client, tokens["approver"], f"/v1/journals/{journal_id}/approve").status_code == 200
    published = _post(client, tokens["approver"], f"/v1/journals/{journal_id}/publish")
    assert published.status_code == 200, published.text


def _get(client, tokens, path: str, period_id: str, user: str = "preparer"):
    return client.get(path, params={"period_id": period_id}, headers=_auth(tokens[user]))


def _rows(report: dict, key: str) -> dict[str, str]:
    return {row["code"]: row[key] for section in report["sections"] for group in section["groups"] for row in group["rows"]}


def test_closing_draft_moves_profit_to_retained_earnings_and_statements_follow(client, tokens, world):
    del world
    entity = _company(client, tokens, "910000000101")
    december = f"{entity}-2026-12"
    _publish(client, tokens, _entry(entity, 3, "1.1.02", "4.1.01", "1000.00", "Serviço prestado"))
    _publish(client, tokens, _entry(entity, 6, "5.1.01", "1.1.02", "400.00", "Despesa paga"))

    statement = _get(client, tokens, f"/v1/legal-entities/{entity}/income-statement", december).json()
    assert statement["result"] == {"month": "0", "year_to_date": "600"}
    assert _rows(statement, "year_to_date") == {"4.1.01": "1000", "5.1.01": "400"}
    sheet = _get(client, tokens, f"/v1/legal-entities/{entity}/balance-sheet", december).json()
    assert sheet["total_assets"] == "600"
    assert sheet["sections"][2]["unclosed_result"] == "600"
    assert sheet["difference"] == "0"

    created = _closing(client, tokens["preparer"], entity)
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["result"] == "600"
    assert body["warnings"] == []
    journal = body["journal"]
    assert journal["status"] == "draft"
    assert journal["source"]["source_type"] == "closing"
    lines = {(line["account_id"].removeprefix(f"{entity}-"), line["side"]): line["amount"] for line in journal["lines"]}
    assert lines == {("4.1.01", "debit"): "1000", ("5.1.01", "credit"): "400", ("3.2.01", "credit"): "600"}
    _approve_and_publish(client, tokens, journal["journal_id"])

    balance = _get(client, tokens, f"/v1/legal-entities/{entity}/trial-balance", december).json()
    closing = {row["code"]: row["closing_balance"] for row in balance["rows"]}
    assert closing["4.1.01"] == "0"
    assert closing["5.1.01"] == "0"
    assert closing["3.2.01"] == "-600"

    session = session_factory(admin=True)()
    try:
        session.add(
            AccountingPeriod(
                id=f"{entity}-2027-01",
                tenant_id="tenant_demo",
                legal_entity_id=entity,
                fiscal_year=2027,
                month=1,
                start_date=date(2027, 1, 1),
                end_date=date(2027, 1, 31),
                status="open",
            )
        )
        session.commit()
    finally:
        session.close()
    january = _get(client, tokens, f"/v1/legal-entities/{entity}/trial-balance", f"{entity}-2027-01").json()
    opening = {row["code"]: row["opening_balance"] for row in january["rows"]}
    assert opening["4.1.01"] == "0"
    assert opening["5.1.01"] == "0"
    assert opening["3.2.01"] == "-600"

    after = _get(client, tokens, f"/v1/legal-entities/{entity}/income-statement", december).json()
    assert after["result"]["year_to_date"] == "600"
    sheet = _get(client, tokens, f"/v1/legal-entities/{entity}/balance-sheet", december).json()
    assert sheet["sections"][2]["unclosed_result"] == "0"
    assert _rows(sheet, "balance")["3.2.01"] == "600"
    assert sheet["difference"] == "0"

    repeated = _closing(client, tokens["preparer"], entity)
    assert repeated.status_code == 409
    assert repeated.json()["title"] == "Encerramento já existe"

    reversal = _post(client, tokens["preparer"], f"/v1/journals/{journal['journal_id']}/reverse")
    assert reversal.status_code == 201, reversal.text
    _approve_and_publish(client, tokens, reversal.json()["journal_id"])
    assert _get(client, tokens, f"/v1/legal-entities/{entity}/income-statement", december).json()["result"]["year_to_date"] == "600"
    again = _closing(client, tokens["preparer"], entity)
    assert again.status_code == 201, again.text

    exported = _get(client, tokens, f"/v1/legal-entities/{entity}/income-statement.csv", december)
    assert exported.status_code == 200
    assert exported.headers["content-type"].startswith("text/csv")
    assert exported.headers["content-disposition"].endswith('-2026-12.csv"')
    assert 'filename="dre-' in exported.headers["content-disposition"]
    assert ";Resultado do período;0,00;600,00" in exported.content.decode("utf-8")
    sheet_csv = _get(client, tokens, f"/v1/legal-entities/{entity}/balance-sheet.csv", december)
    assert sheet_csv.status_code == 200
    assert 'filename="balanco-' in sheet_csv.headers["content-disposition"]


def test_closing_records_a_loss_and_refuses_what_it_cannot_close(client, tokens, world):
    del world
    entity = _company(client, tokens, "910000000102")
    empty = _closing(client, tokens["preparer"], entity)
    assert empty.status_code == 409
    assert empty.json()["title"] == "Nada a encerrar"

    _publish(client, tokens, _entry(entity, 5, "5.1.01", "1.1.02", "300.00", "Despesa"))
    pending = _post(client, tokens["preparer"], "/v1/journals", _entry(entity, 7, "5.1.01", "1.1.02", "50.00", "Rascunho"))
    assert pending.status_code == 201
    blocked = _closing(client, tokens["preparer"], entity)
    assert blocked.status_code == 409
    assert blocked.json()["title"] == "Lançamentos pendentes"
    assert pending.json()["journal_id"] in blocked.json()["detail"]
    assert _post(client, tokens["preparer"], f"/v1/journals/{pending.json()['journal_id']}/submit").status_code == 200
    rejected = _post(client, tokens["approver"], f"/v1/journals/{pending.json()['journal_id']}/reject", {"reason": "Não entra no ano"})
    assert rejected.status_code == 200

    wrong_account = _closing(client, tokens["preparer"], entity, account="5.1.01")
    assert wrong_account.status_code == 400
    assert _closing(client, tokens["outsider"], entity).status_code == 404
    assert _closing(client, tokens["viewer"], entity).status_code == 403

    manual = _entry(entity, 12, "5.1.01", "1.1.02", "1.00", "Encerramento manual")
    manual["source_type"] = "closing"
    assert _post(client, tokens["preparer"], "/v1/journals", manual).status_code == 400

    created = _closing(client, tokens["admin"], entity)
    assert created.status_code == 201, created.text
    assert created.json()["result"] == "-300"
    journal = created.json()["journal"]
    lines = {(line["account_id"].removeprefix(f"{entity}-"), line["side"]): line["amount"] for line in journal["lines"]}
    assert lines == {("5.1.01", "credit"): "300", ("3.2.01", "debit"): "300"}
    assert _post(client, tokens["admin"], f"/v1/journals/{journal['journal_id']}/submit").status_code == 200
    own = _post(client, tokens["admin"], f"/v1/journals/{journal['journal_id']}/approve")
    assert own.status_code == 403
    assert own.json()["title"] == "Segregação de funções"


def test_closing_needs_an_open_december(client, tokens, world):
    del world
    entity = _company(client, tokens, "910000000103")
    _publish(client, tokens, _entry(entity, 2, "1.1.02", "4.1.01", "80.00", "Receita"))
    session = session_factory(admin=True)()
    try:
        session.execute(update(AccountingPeriod).where(AccountingPeriod.id == f"{entity}-2026-12").values(status="closed"))
        session.commit()
    finally:
        session.close()
    refused = _closing(client, tokens["preparer"], entity)
    assert refused.status_code == 409
    assert refused.json()["title"] == "Período fechado"
