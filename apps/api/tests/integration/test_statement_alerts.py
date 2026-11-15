from __future__ import annotations

from contabil.platform.db import session_factory
from contabil.tables import Account

from tests.integration.test_phase_a import _auth, _post
from tests.integration.test_phase_b import _upload
from tests.integration.test_phase_c import _bank, _cases, _drain, _statement
from tests.integration.world import add_entity


def _ofx(*rows: tuple[str, str, str, str]) -> bytes:
    body = "OFXHEADER:100\nCHARSET:1252\n\n<OFX>\n"
    for posted, amount, fitid, memo in rows:
        body += f"<STMTTRN>\n<DTPOSTED>{posted}\n<TRNAMT>{amount}\n<FITID>{fitid}\n<MEMO>{memo}\n</STMTTRN>\n"
    return (body + "</OFX>\n").encode("cp1252")


def _second_bank(client, token: str, entity_id: str, account_id: str) -> str:
    created = _post(
        client,
        token,
        "/v1/bank-accounts",
        {
            "legal_entity_id": entity_id,
            "account_id": account_id,
            "name": "Segunda conta",
            "bank_code": "237",
            "branch": "4321",
            "account_number_masked": "1111",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()["bank_account_id"]


def _statement_of(client, token: str, bank_id: str, content: bytes, entity_id: str) -> None:
    uploaded = _upload(client, token, content, document_type="bank_statement", legal_entity_id=entity_id)
    assert uploaded.status_code == 201, uploaded.text
    created = _post(client, token, f"/v1/bank-accounts/{bank_id}/statements", {"document_id": uploaded.json()["document_id"]})
    assert created.status_code == 202, created.text
    _drain()


def _add_bank_ledger_account(entity_id: str, code: str) -> str:
    session = session_factory(admin=True)()
    try:
        parent = session.get(Account, f"{entity_id}-1.1.02")
        account = Account(
            id=f"{entity_id}-{code}",
            tenant_id=parent.tenant_id,
            legal_entity_id=entity_id,
            chart_id=parent.chart_id,
            code=code,
            name="Banco 2",
            account_type="asset",
            postable=True,
            active=True,
        )
        session.add(account)
        session.commit()
        return account.id
    finally:
        session.close()


DUP = _ofx(
    ("20260915", "-120.00", "f1", "Pagto Fornecedor Alfa"),
    ("20260917", "-120.00", "f2", "Pagto Fornecedor Alfa"),
)
OUT = _ofx(("20260915", "-500.00", "o1", "Transferencia enviada"))
IN = _ofx(("20260916", "500.00", "i1", "Transferencia recebida"))


def test_case_lists_duplicate_alert(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, DUP, "dup.ofx")
    cases = _cases(client, tokens["preparer"], bank_id)
    assert len(cases) == 2
    for case in cases:
        assert [a["kind"] for a in case["alerts"]] == ["duplicate_payment"]
        assert case["alerts"][0]["rule_version"] == "2026.11-provisorio"
    detail = client.get(f"/v1/reconciliation-cases/{cases[0]['case_id']}", headers=_auth(tokens["preparer"]))
    assert detail.json()["alerts"][0]["kind"] == "duplicate_payment"


def test_own_transfer_alert_across_accounts(client, tokens, world):
    del world
    bank_a = _bank(client, tokens["preparer"])
    bank_b = _second_bank(client, tokens["preparer"], "le_test", _add_bank_ledger_account("le_test", "1.1.03"))
    _statement(client, tokens["preparer"], bank_a, OUT, "out.ofx")
    _statement(client, tokens["preparer"], bank_b, IN, "in.ofx")
    for bank in (bank_a, bank_b):
        cases = _cases(client, tokens["preparer"], bank)
        assert [a["kind"] for a in cases[0]["alerts"]] == ["own_transfer"]


def test_alerts_never_cross_entities(client, tokens, world):
    del world
    add_entity("le_second", "tenant_demo", "Segunda Empresa", "100000000002")
    bank_a = _bank(client, tokens["preparer"])
    bank_b = _second_bank(client, tokens["preparer"], "le_second", "le_second-1.1.02")
    _statement(client, tokens["preparer"], bank_a, OUT, "out.ofx")
    _statement_of(client, tokens["preparer"], bank_b, IN, "le_second")
    for bank in (bank_a, bank_b):
        assert _cases(client, tokens["preparer"], bank)[0]["alerts"] == []


def test_bank_summary_alert_count(client, tokens, world):
    del world
    bank_id = _bank(client, tokens["preparer"])
    _statement(client, tokens["preparer"], bank_id, DUP, "dup.ofx")
    summary = client.get(
        f"/v1/bank-accounts/{bank_id}/summary",
        params={"period_id": "le_test-2026-09"},
        headers=_auth(tokens["preparer"]),
    )
    assert summary.status_code == 200, summary.text
    assert summary.json()["alert_count"] == 1
