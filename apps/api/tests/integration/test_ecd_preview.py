from __future__ import annotations

from datetime import date, datetime, timezone
from decimal import Decimal

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import AuditEvent, EntitySignatories, ProfessionalRegistration
from contabil.worker import relay_once
from tests.integration.test_phase_a import _auth, _publish
from tests.integration.test_year_end import _approve_and_publish, _closing, _company, _entry

RECIFE = {
    "uf": "PE",
    "municipality_ibge": "2611606",
    "registry_kind": "junta",
    "nire": "26200000011",
    "registry_date": "2020-05-04",
    "special_situation": None,
    "book_number": 3,
}


def _put(client, token: str, path: str, body: dict):
    from uuid import uuid4

    return client.put(path, json=body, headers=_auth(token, uuid4().hex))


def _post(client, token: str, path: str, body: dict):
    from uuid import uuid4

    return client.post(path, json=body, headers=_auth(token, uuid4().hex))


def _drain() -> None:
    session = session_factory(admin=True)()
    try:
        while relay_once(session):
            session.commit()
        session.commit()
    finally:
        session.close()


def _signatories(entity: str, *, tenant: str = "tenant_demo") -> None:
    """Contador e representante fictícios, gravados direto (a tela é da frente A)."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant)
        now = datetime.now(timezone.utc)
        if session.query(ProfessionalRegistration).filter_by(tenant_id=tenant, user_id="approver").first() is None:
            session.add(
                ProfessionalRegistration(
                    id=f"preg-{entity}",
                    tenant_id=tenant,
                    user_id="approver",
                    cpf="52998224725",
                    crc_uf="PE",
                    crc_number="012345/O",
                    crc_category="contador",
                    regularity_number="PE/2026/000123",
                    regularity_valid_until=date(2026, 12, 31),
                    updated_at=now,
                )
            )
        session.add(
            EntitySignatories(
                id=f"sig-{entity}",
                tenant_id=tenant,
                legal_entity_id=entity,
                accountant_user_id="approver",
                legal_rep_name="Maria Fictícia",
                legal_rep_cpf="11144477735",
                legal_rep_role="socio_administrador",
                updated_by="admin",
                updated_at=now,
            )
        )
        session.commit()
    finally:
        session.close()


def _preview(client, tokens, entity: str, user: str = "preparer") -> tuple[str, dict]:
    created = _post(client, tokens[user], f"/v1/legal-entities/{entity}/exports", {"kind": "ecd_preview_v1", "fiscal_year": 2026})
    assert created.status_code == 202, created.text
    export_id = created.json()["export_id"]
    waiting = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"]))
    assert waiting.status_code == 409
    _drain()
    ready = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"]))
    assert ready.status_code == 200, ready.text
    operation = client.get(f"/v1/operations/{created.json()['operation_id']}", headers=_auth(tokens["viewer"]))
    assert operation.status_code == 200, operation.text
    assert operation.json()["status"] == "completed"
    return export_id, ready.json()


def _lines(content: str) -> list[list[str]]:
    return [line[1:-1].split("|") for line in content.split("\r\n") if line]


def test_preview_of_a_closed_year_balances_and_follows_the_income_statement(client, tokens, world):
    del world
    entity = _company(client, tokens, "930000000101")
    saved = _put(client, tokens["admin"], f"/v1/legal-entities/{entity}/ecd-registration", RECIFE)
    assert saved.status_code == 200, saved.text
    assert saved.json()["configured"] is True
    _signatories(entity)
    _publish(client, tokens, _entry(entity, 1, "1.1.02", "3.1.01", "5000.00", "Aporte de capital"))
    _publish(client, tokens, _entry(entity, 3, "1.1.02", "4.1.01", "1000.00", "Serviço prestado"))
    _publish(client, tokens, _entry(entity, 6, "5.1.01", "1.1.02", "400.00", "Despesa paga"))
    closing = _closing(client, tokens["preparer"], entity)
    assert closing.status_code == 201, closing.text
    _approve_and_publish(client, tokens, closing.json()["journal"]["journal_id"])

    export_id, payload = _preview(client, tokens, entity)
    assert payload["kind"] == "ecd_preview_v1"
    assert payload["transmittable"] is False
    assert payload["notice"] == "Prévia para conferência no PVA. Não transmitir."
    assert payload["file_name"].startswith("ECD-PREVIA-") and payload["file_name"].endswith("-2026.txt")
    assert payload["result"] == "600"
    assert all(payload["checks"].values()), payload["checks"]
    assert set(payload["checks"]) >= {"i200_matches_i250", "i155_rolls_forward", "i355_matches_income_statement", "j100_balances", "block_counts"}
    codes = {issue["code"] for issue in payload["issues"]}
    assert not codes & {"registration_missing", "accountant_missing", "legal_rep_missing", "closing_missing", "pending_journals"}
    # E-mail e telefone do contador não estão no cadastro: o PVA acusaria (REGRA_OBRIGATORIO_CONTADOR).
    assert "layout_REGRA_OBRIGATORIO_CONTADOR" in codes
    assert "out_of_scope_i051" in codes

    downloaded = client.get(f"/v1/exports/{export_id}/file", headers=_auth(tokens["viewer"]))
    assert downloaded.status_code == 200, downloaded.text
    assert "ECD-PREVIA-" in downloaded.headers["content-disposition"]
    assert downloaded.headers["content-type"].startswith("text/plain")
    content = downloaded.content.decode("iso-8859-1")
    lines = _lines(content)
    assert lines[0][:4] == ["0000", "LECD", "01012026", "31122026"]
    assert lines[0][6] == "PE" and lines[0][8] == "2611606"
    assert ["I010", "G", "9.00"] in lines
    i030 = next(line for line in lines if line[0] == "I030")
    assert i030[3] == "DIARIO GERAL - PREVIA NAO TRANSMITIR"
    assert i030[6] == "26200000011"
    assert i030[4] == str(len(lines))
    kinds = [line[4] for line in lines if line[0] == "I200"]
    assert kinds.count("E") == 1 and kinds.count("N") == 3
    i355 = {line[1]: (Decimal(line[3].replace(",", ".")), line[4]) for line in lines if line[0] == "I355"}
    assert i355 == {"4.1.01": (Decimal("1000.00"), "C"), "5.1.01": (Decimal("400.00"), "D")}
    level_one = {line[5]: line for line in lines if line[0] == "J100" and line[3] == "1"}
    assert level_one["A"][9:11] == ["5600,00", "D"]
    assert level_one["P"][9:11] == ["5600,00", "C"]
    j150_root = next(line for line in lines if line[0] == "J150" and line[4] == "1")
    assert j150_root[9:12] == ["600,00", "C", "R"]
    signers = [line for line in lines if line[0] == "J930"]
    assert [(line[4], line[11]) for line in signers] == [("900", "N"), ("205", "S")]
    assert lines[-1] == ["9999", str(len(lines))]

    hidden = client.get(f"/v1/exports/{export_id}/file", headers=_auth(tokens["outsider"]))
    assert hidden.status_code == 404
    assert client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["outsider"])).status_code == 404


def test_preview_lists_what_is_missing_without_registration_signers_or_closing(client, tokens, world):
    del world
    entity = _company(client, tokens, "930000000102")
    _publish(client, tokens, _entry(entity, 2, "1.1.02", "4.1.01", "80.00", "Receita"))
    pending = _post(client, tokens["preparer"], "/v1/journals", _entry(entity, 4, "5.1.01", "1.1.02", "10.00", "Rascunho"))
    assert pending.status_code == 201
    _, payload = _preview(client, tokens, entity)
    issues = {issue["code"]: issue for issue in payload["issues"]}
    for code in ("registration_missing", "accountant_missing", "legal_rep_missing", "closing_missing", "pending_journals"):
        assert code in issues, code
    assert issues["registration_missing"]["fix"] == "ecd_registration"
    assert issues["accountant_missing"]["fix"] == "signatories"
    assert issues["closing_missing"]["severity"] == "blocker"
    assert "i355_matches_income_statement" not in payload["checks"]
    assert payload["checks"]["block_counts"] is True
    assert payload["checks"]["i200_matches_i250"] is True


def test_registration_is_admin_only_audited_and_checks_the_uf(client, tokens, world):
    del world
    entity = _company(client, tokens, "930000000103")
    empty = client.get(f"/v1/legal-entities/{entity}/ecd-registration", headers=_auth(tokens["viewer"]))
    assert empty.status_code == 200
    assert empty.json()["configured"] is False
    assert _put(client, tokens["preparer"], f"/v1/legal-entities/{entity}/ecd-registration", RECIFE).status_code == 403
    assert _put(client, tokens["cliente"], f"/v1/legal-entities/{entity}/ecd-registration", RECIFE).status_code == 403
    wrong = _put(client, tokens["admin"], f"/v1/legal-entities/{entity}/ecd-registration", {**RECIFE, "municipality_ibge": "3550308"})
    assert wrong.status_code == 400
    assert wrong.json()["errors"][0]["loc"] == ["municipality_ibge"]
    nire = _put(client, tokens["admin"], f"/v1/legal-entities/{entity}/ecd-registration", {**RECIFE, "nire": "35200000011"})
    assert nire.status_code == 400
    cartorio = _put(
        client, tokens["admin"], f"/v1/legal-entities/{entity}/ecd-registration", {**RECIFE, "registry_kind": "cartorio", "nire": None}
    )
    assert cartorio.status_code == 200, cartorio.text
    assert cartorio.json()["nire"] is None
    again = _put(client, tokens["admin"], f"/v1/legal-entities/{entity}/ecd-registration", RECIFE)
    assert again.status_code == 200
    read = client.get(f"/v1/legal-entities/{entity}/ecd-registration", headers=_auth(tokens["viewer"]))
    assert read.json()["nire"] == "26200000011"
    assert read.json()["book_number"] == 3
    assert client.get(f"/v1/legal-entities/{entity}/ecd-registration", headers=_auth(tokens["outsider"])).status_code == 404
    assert _put(client, tokens["outsider"], f"/v1/legal-entities/{entity}/ecd-registration", RECIFE).status_code == 403
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        actions = [
            event.details["action"]
            for event in session.query(AuditEvent).filter_by(target_type="ecd_registration", target_ref=entity).order_by(AuditEvent.occurred_at)
        ]
    finally:
        session.close()
    assert actions == ["ecd_registration_created", "ecd_registration_updated"]


def test_preview_of_another_office_company_is_not_found(client, tokens, world):
    del world
    other = _post(client, tokens["outsider"], "/v1/legal-entities/le_test/exports", {"kind": "ecd_preview_v1", "fiscal_year": 2026})
    assert other.status_code == 404
    missing_year = _post(client, tokens["preparer"], "/v1/legal-entities/le_test/exports", {"kind": "ecd_preview_v1"})
    assert missing_year.status_code == 400
    no_periods = _post(client, tokens["preparer"], "/v1/legal-entities/le_test/exports", {"kind": "ecd_preview_v1", "fiscal_year": 2025})
    assert no_periods.status_code == 409
    viewer = _post(client, tokens["viewer"], "/v1/legal-entities/le_test/exports", {"kind": "ecd_preview_v1", "fiscal_year": 2026})
    assert viewer.status_code == 403
