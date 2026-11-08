"""Registro profissional (CRC) e signatários da DRE e do Balanço (ADR 030)."""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.seed.cpf import cpf_digits
from contabil.tables import AuditEvent, EntitySignatories, ProfessionalRegistration
from tests.integration.test_phase_a import _auth

PERIOD = "le_test-2026-09"


def _put(client, token: str, path: str, body: dict):
    return client.put(path, json=body, headers=_auth(token, uuid4().hex))


def _register(client, token: str, *, cpf: str, number: str, category: str = "contador", uf: str = "PE"):
    return _put(
        client,
        token,
        "/v1/me/professional-registration",
        {"cpf": cpf, "crc_uf": uf, "crc_number": number, "crc_category": category, "regularity_number": "PE/2026/000123"},
    )


def _signatories(client, token: str, entity: str = "le_test", **overrides):
    body = {
        "accountant_user_id": "approver",
        "legal_rep_name": "Sócia Fictícia",
        "legal_rep_cpf": cpf_digits("800000010"),
        "legal_rep_role": "socio_administrador",
        **overrides,
    }
    return _put(client, token, f"/v1/legal-entities/{entity}/signatories", body)


def test_user_registers_own_crc_and_client_is_refused(client, tokens, world):
    del world
    empty = client.get("/v1/me/professional-registration", headers=_auth(tokens["approver"]))
    assert empty.status_code == 200, empty.text
    assert empty.json()["registration"] is None

    bad_cpf = _register(client, tokens["approver"], cpf="529.982.247-24", number="012345/O")
    assert bad_cpf.status_code == 400
    bad_uf = _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O", uf="XX")
    assert bad_uf.status_code == 400
    bad_number = _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="CRC-PE 1")
    assert bad_number.status_code == 400
    bad_category = _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O", category="auditor")
    assert bad_category.status_code == 400

    saved = _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number=" 012345/o ")
    assert saved.status_code == 200, saved.text
    registration = saved.json()["registration"]
    assert registration["crc"] == "CRC-PE 012345/O"
    assert registration["caption"] == "Contador, CRC-PE 012345/O"
    assert registration["regularity_number"] == "PE/2026/000123"
    again = _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O-8")
    assert again.status_code == 200
    assert again.json()["registration"]["crc_number"] == "012345/O-8"

    for method in ("get", "put"):
        if method == "get":
            refused = client.get("/v1/me/professional-registration", headers=_auth(tokens["cliente"]))
        else:
            refused = _register(client, tokens["cliente"], cpf=cpf_digits("800000004"), number="1")
        assert refused.status_code == 403, refused.text

    session = session_factory(admin=True)()
    try:
        rows = session.scalars(select(ProfessionalRegistration).where(ProfessionalRegistration.user_id == "approver")).all()
        assert len(rows) == 1
        events = session.scalars(
            select(AuditEvent).where(AuditEvent.tenant_id == "tenant_demo", AuditEvent.target_ref == "approver")
        ).all()
        assert [event.details["action"] for event in events] == ["professional_registration_updated"] * 2
        # A trilha não guarda o CPF.
        assert all(cpf_digits("800000001") not in str(event.details) for event in events)
    finally:
        session.close()


def test_only_admin_sets_signatories_and_accountant_must_be_an_office_contador(client, tokens, world):
    del world
    assert _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O").status_code == 200
    assert _register(client, tokens["preparer"], cpf=cpf_digits("800000003"), number="034567/T", category="tecnico").status_code == 200
    assert _register(client, tokens["outsider"], cpf=cpf_digits("800000005"), number="045678/O").status_code == 200

    assert _signatories(client, tokens["viewer"]).status_code == 403
    assert _signatories(client, tokens["approver"]).status_code == 403
    assert _signatories(client, tokens["cliente"]).status_code == 403

    for accountant in ("viewer", "outsider", "preparer", "cliente", "ninguem"):
        refused = _signatories(client, tokens["admin"], accountant_user_id=accountant)
        assert refused.status_code == 400, (accountant, refused.text)
    assert _signatories(client, tokens["admin"], legal_rep_cpf="111.111.111-11").status_code == 400
    assert _signatories(client, tokens["admin"], legal_rep_role="gerente").status_code == 400
    assert _signatories(client, tokens["admin"], legal_rep_name="", legal_rep_role="titular").status_code == 400

    saved = _signatories(client, tokens["admin"])
    assert saved.status_code == 200, saved.text
    body = saved.json()
    assert body["accountant"]["user_id"] == "approver"
    assert body["accountant"]["caption"] == "Contador, CRC-PE 012345/O"
    expected_cpf = cpf_digits("800000010")
    assert body["legal_representative"]["cpf"] == f"{expected_cpf[:3]}.{expected_cpf[3:6]}.{expected_cpf[6:9]}-{expected_cpf[9:]}"
    assert body["legal_representative"]["caption"] == "Sócio-administrador"
    options = {item["user_id"]: item["eligible"] for item in body["accountant_options"]}
    assert options == {"approver": True, "preparer": False}

    seen = client.get("/v1/legal-entities/le_test/signatories", headers=_auth(tokens["viewer"]))
    assert seen.status_code == 200
    viewer_body = seen.json()
    assert viewer_body["legal_representative"]["cpf"] == f"***.{expected_cpf[3:6]}.{expected_cpf[6:9]}-**"
    assert "accountant_options" not in viewer_body
    assert client.get("/v1/legal-entities/le_test/signatories", headers=_auth(tokens["cliente"])).status_code == 403

    cleared = _signatories(client, tokens["admin"], accountant_user_id=None, legal_rep_name=None, legal_rep_cpf=None, legal_rep_role=None)
    assert cleared.status_code == 200
    assert cleared.json()["accountant"] is None
    assert cleared.json()["legal_representative"] is None

    session = session_factory(admin=True)()
    try:
        updates = session.scalar(
            select(func.count()).select_from(AuditEvent).where(
                AuditEvent.tenant_id == "tenant_demo", AuditEvent.target_type == "legal_entity", AuditEvent.target_ref == "le_test"
            )
        )
        assert updates == 2
    finally:
        session.close()


def test_signatories_stay_inside_the_office(client, tokens, world):
    del world
    assert _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O").status_code == 200
    assert _signatories(client, tokens["admin"]).status_code == 200

    other = client.get("/v1/legal-entities/le_test/signatories", headers=_auth(tokens["outsider"]))
    assert other.status_code == 404
    # O contador do Escritório Demo não assina pela empresa de outro escritório.
    assert _signatories(client, tokens["admin"], entity="le_other").status_code == 404

    session = session_factory()()
    try:
        apply_tenant(session, "tenant_other")
        assert session.scalar(select(func.count()).select_from(EntitySignatories)) == 0
        assert session.scalar(select(func.count()).select_from(ProfessionalRegistration)) == 0
        apply_tenant(session, "tenant_demo")
        assert session.scalar(select(func.count()).select_from(EntitySignatories)) == 1
    finally:
        session.rollback()
        session.close()


def test_statements_and_csv_carry_the_signatories(client, tokens, world):
    del world
    params = {"period_id": PERIOD}
    before = client.get("/v1/legal-entities/le_test/income-statement", params=params, headers=_auth(tokens["preparer"]))
    assert before.status_code == 200, before.text
    assert before.json()["signatories"] is None
    missing = client.get("/v1/legal-entities/le_test/balance-sheet.csv", params=params, headers=_auth(tokens["preparer"]))
    assert missing.status_code == 200
    assert "Responsável técnico não cadastrado" in missing.text
    assert "Representante legal não cadastrado" in missing.text

    assert _register(client, tokens["approver"], cpf=cpf_digits("800000001"), number="012345/O").status_code == 200
    assert _signatories(client, tokens["admin"]).status_code == 200

    expected = {
        "accountant": {"name": "Aprovador", "caption": "Contador, CRC-PE 012345/O"},
        "legal_representative": {"name": "Sócia Fictícia", "caption": "Sócio-administrador"},
    }
    for path in ("income-statement", "balance-sheet"):
        report = client.get(f"/v1/legal-entities/le_test/{path}", params=params, headers=_auth(tokens["viewer"]))
        assert report.status_code == 200, report.text
        assert report.json()["signatories"] == expected
        content = client.get(f"/v1/legal-entities/le_test/{path}.csv", params=params, headers=_auth(tokens["viewer"])).text
        assert "Responsável técnico;Aprovador — Contador, CRC-PE 012345/O" in content
        assert "Representante legal;Sócia Fictícia;Sócio-administrador" in content
        # O CPF não sai na demonstração.
        assert cpf_digits("800000010") not in content
