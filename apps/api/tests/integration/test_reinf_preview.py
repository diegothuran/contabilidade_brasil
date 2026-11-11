"""Pagamentos com retenção e prévia da EFD-Reinf R-4000 de ponta a ponta (ADR 032). Dados fictícios."""

from __future__ import annotations

import io
import zipfile
from uuid import uuid4

from lxml import etree

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.regulatory.reinf_preview import EVENTS, xsd_errors
from contabil.seed.cnpj import cnpj_digits
from contabil.seed.cpf import cpf_digits
from contabil.tables import AccountingPeriod, AuditEvent
from tests.integration.test_ecd_preview import _drain, _post, _signatories
from tests.integration.test_phase_a import _auth
from tests.integration.test_year_end import _company

SUPPLIER = cnpj_digits("112223330001")
PERSON = cpf_digits("123456789")
NOTICE = "Prévia para conferência. Não assinar nem transmitir."


def _period(entity: str, month: int = 10) -> str:
    return f"{entity}-2026-{month:02d}"


def _company_payment(entity: str, **overrides) -> dict:
    body = {
        "period_id": _period(entity),
        "payment_date": "2026-10-20",
        "beneficiary_kind": "pj",
        "beneficiary_document": f"{SUPPLIER[:2]}.{SUPPLIER[2:5]}.{SUPPLIER[5:8]}/{SUPPLIER[8:12]}-{SUPPLIER[12:]}",
        "beneficiary_name": "Consultoria Fictícia Ltda.",
        "nature_code": "15014",
        "gross_amount": "10000.00",
        "ir_base": "10000.00",
        "ir_amount": "150.00",
        "csrf_base": "10000.00",
        "csrf_amount": "465.00",
        "description": "Consultoria de outubro",
    }
    body.update(overrides)
    return body


def _person_payment(entity: str, **overrides) -> dict:
    body = {
        "period_id": _period(entity),
        "payment_date": "2026-10-05",
        "beneficiary_kind": "pf",
        "beneficiary_document": PERSON,
        "beneficiary_name": "Locador Fictício",
        "nature_code": "13002",
        "gross_amount": "6000.00",
        "ir_base": "6000.00",
        "ir_amount": "1000.00",
        "csrf_base": None,
        "csrf_amount": None,
    }
    body.update(overrides)
    return body


def _payments_path(entity: str) -> str:
    return f"/v1/legal-entities/{entity}/withholding-payments"


def _close_directly(period_id: str) -> None:
    """Fecha a competência direto no banco: o fechamento com checklist é testado em test_close_runs."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        period = session.get(AccountingPeriod, period_id)
        period.status = "closed"
        session.commit()
    finally:
        session.close()


def _preview(client, tokens, entity: str, period_id: str) -> tuple[str, dict]:
    created = _post(client, tokens["preparer"], f"/v1/legal-entities/{entity}/exports", {"kind": "reinf_r4000_preview_v1", "period_id": period_id})
    assert created.status_code == 202, created.text
    export_id = created.json()["export_id"]
    assert client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"])).status_code == 409
    _drain()
    ready = client.get(f"/v1/exports/{export_id}", headers=_auth(tokens["viewer"]))
    assert ready.status_code == 200, ready.text
    operation = client.get(f"/v1/operations/{created.json()['operation_id']}", headers=_auth(tokens["viewer"]))
    assert operation.json()["status"] == "completed"
    return export_id, ready.json()


def test_payments_are_listed_created_and_deleted_with_audit(client, tokens, world):
    del world
    entity = _company(client, tokens, "940000000101")
    path = _payments_path(entity)
    created = _post(client, tokens["preparer"], path, _company_payment(entity))
    assert created.status_code == 201, created.text
    payment = created.json()
    assert payment["id"].startswith("whp_")
    assert payment["beneficiary_document"] == SUPPLIER
    assert payment["gross_amount"] == "10000.00" and payment["ir_amount"] == "150.00" and payment["csrf_amount"] == "465.00"
    person = _post(client, tokens["approver"], path, _person_payment(entity, ir_amount=None))
    assert person.status_code == 201, person.text
    assert person.json()["ir_amount"] is None and person.json()["csrf_base"] is None

    listed = client.get(f"{path}?period_id={_period(entity)}", headers=_auth(tokens["viewer"]))
    assert listed.status_code == 200
    assert [item["nature_code"] for item in listed.json()["items"]] == ["13002", "15014"]
    assert client.get(f"{path}?period_id={_period(entity, 9)}", headers=_auth(tokens["viewer"])).json()["items"] == []

    key = uuid4().hex
    deleted = client.delete(f"{path}/{person.json()['id']}", headers=_auth(tokens["admin"], key))
    assert deleted.status_code == 204 and deleted.content == b""
    replay = client.delete(f"{path}/{person.json()['id']}", headers=_auth(tokens["admin"], key))
    assert replay.status_code == 204
    again = client.delete(f"{path}/{person.json()['id']}", headers=_auth(tokens["admin"], uuid4().hex))
    assert again.status_code == 404

    session = session_factory(admin=True)()
    try:
        apply_tenant(session, "tenant_demo")
        events = session.query(AuditEvent).filter_by(target_type="withholding_payment").order_by(AuditEvent.occurred_at).all()
    finally:
        session.close()
    assert [event.details["action"] for event in events] == [
        "withholding_payment_created",
        "withholding_payment_created",
        "withholding_payment_deleted",
    ]
    trail = " ".join(str(event.details) for event in events)
    assert SUPPLIER not in trail and PERSON not in trail and "Fictício" not in trail


def test_payment_validation_roles_and_closed_period(client, tokens, world):
    del world
    entity = _company(client, tokens, "940000000102")
    path = _payments_path(entity)
    wrong = _post(
        client,
        tokens["preparer"],
        path,
        _company_payment(entity, beneficiary_document="11.222.333/0001-00", nature_code="13002", payment_date="2026-11-02", gross_amount="0"),
    )
    assert wrong.status_code == 400, wrong.text
    locs = {error["loc"][0] for error in wrong.json()["errors"]}
    assert {"beneficiary_document", "nature_code", "payment_date", "gross_amount"} <= locs
    pf_csrf = _post(client, tokens["preparer"], path, _person_payment(entity, csrf_base="100.00"))
    assert pf_csrf.status_code == 400
    assert pf_csrf.json()["errors"][0]["loc"] == ["csrf_base"]
    assert _post(client, tokens["viewer"], path, _company_payment(entity)).status_code == 403
    assert _post(client, tokens["cliente"], path, _company_payment(entity)).status_code == 403
    assert client.get(path, headers=_auth(tokens["cliente"])).status_code == 403
    assert _post(client, tokens["outsider"], path, _company_payment(entity)).status_code in {403, 404}
    no_key = client.post(path, json=_company_payment(entity), headers=_auth(tokens["preparer"]))
    assert no_key.status_code == 400

    created = _post(client, tokens["preparer"], path, _company_payment(entity, period_id=_period(entity, 1), payment_date="2026-01-15"))
    assert created.status_code == 201, created.text
    _close_directly(_period(entity, 1))
    late = _post(client, tokens["preparer"], path, _company_payment(entity, period_id=_period(entity, 1), payment_date="2026-01-20"))
    assert late.status_code == 409
    gone = client.delete(f"{path}/{created.json()['id']}", headers=_auth(tokens["preparer"], uuid4().hex))
    assert gone.status_code == 409


def test_natures_endpoint_filters_by_beneficiary(client, tokens, world):
    del world
    company = client.get("/v1/regulatory/reinf/natures?beneficiary_kind=pj", headers=_auth(tokens["viewer"]))
    assert company.status_code == 200
    assert company.json()["version"]
    assert {item["beneficiary_kind"] for item in company.json()["items"]} == {"pj"}
    assert "15015" in {item["code"] for item in company.json()["items"]}
    person = client.get("/v1/regulatory/reinf/natures?beneficiary_kind=pf", headers=_auth(tokens["viewer"]))
    assert {item["code"] for item in person.json()["items"]} == {"10002", "13002"}
    assert client.get("/v1/regulatory/reinf/natures?beneficiary_kind=xx", headers=_auth(tokens["viewer"])).status_code == 400
    assert client.get("/v1/regulatory/reinf/natures", headers=_auth(tokens["cliente"])).status_code == 403


def test_preview_builds_events_that_pass_the_official_xsd(client, tokens, world):
    del world
    entity = _company(client, tokens, "940000000103")
    _signatories(entity)
    path = _payments_path(entity)
    assert _post(client, tokens["preparer"], path, _company_payment(entity)).status_code == 201
    assert _post(client, tokens["preparer"], path, _company_payment(entity, payment_date="2026-10-28", nature_code="15015")).status_code == 201
    assert _post(client, tokens["preparer"], path, _person_payment(entity)).status_code == 201

    export_id, payload = _preview(client, tokens, entity, _period(entity))
    assert payload["kind"] == "reinf_r4000_preview_v1"
    assert payload["period_id"] == _period(entity)
    assert payload["competence"] == "2026-10"
    assert payload["layout_version"] == "2.1.2"
    assert payload["notice"] == NOTICE
    assert payload["transmittable"] is False
    assert payload["file_name"].startswith("REINF-R4000-PREVIA-") and payload["file_name"].endswith("-202610.zip")
    assert payload["counts"] == {"R-4010": 1, "R-4020": 1, "R-4099": 1}
    assert payload["checks"] == {"xsd_valid": True, "ir_matches_ledger": None}
    issues = {issue["code"]: issue for issue in payload["issues"]}
    assert not [issue for issue in payload["issues"] if issue["severity"] == "blocker"], payload["issues"]
    assert issues["out_of_scope_ir_ledger"]["severity"] == "out_of_scope"
    assert issues["assumption_dtfg"]["severity"] == "assumption"
    assert issues["responsible_contact_missing"]["fix"] == "signatories"
    assert set(payload["issues"][0]) == {"code", "severity", "message", "event", "fix"}

    downloaded = client.get(f"/v1/exports/{export_id}/file", headers=_auth(tokens["viewer"]))
    assert downloaded.status_code == 200, downloaded.text
    assert downloaded.headers["content-type"].startswith("application/zip")
    assert payload["file_name"] in downloaded.headers["content-disposition"]
    with zipfile.ZipFile(io.BytesIO(downloaded.content)) as archive:
        assert archive.namelist() == ["LEIA-ME.txt", "R-4010-001.xml", "R-4020-001.xml", "R-4099-001.xml"]
        files = {name: archive.read(name) for name in archive.namelist()}
    assert "NÃO ASSINAR NEM TRANSMITIR" in files["LEIA-ME.txt"].decode("utf-8")
    for name, kind in (("R-4010-001.xml", "R-4010"), ("R-4020-001.xml", "R-4020"), ("R-4099-001.xml", "R-4099")):
        assert b"Signature" not in files[name]
        assert xsd_errors(kind, files[name]) == [], name
    company = etree.fromstring(files["R-4020-001.xml"])
    ns = {"r": EVENTS["R-4020"]["ns"]}
    assert [node.text for node in company.iterfind(".//r:natRend", ns)] == ["15014", "15015"]
    assert company.findtext(".//r:vlrAgreg", namespaces=ns) == "465,00"
    assert client.get(f"/v1/exports/{export_id}/file", headers=_auth(tokens["outsider"])).status_code == 404


def test_preview_without_payments_or_signers_lists_blockers(client, tokens, world):
    del world
    entity = _company(client, tokens, "940000000104")
    _, payload = _preview(client, tokens, entity, _period(entity, 3))
    issues = {issue["code"]: issue for issue in payload["issues"]}
    assert issues["no_payments"]["severity"] == "blocker"
    assert issues["no_payments"]["fix"] == "withholding_payments"
    assert issues["legal_rep_missing"]["fix"] == "signatories"
    assert payload["counts"] == {"R-4010": 0, "R-4020": 0, "R-4099": 0}
    assert payload["checks"]["xsd_valid"] is False
    missing = _post(client, tokens["preparer"], f"/v1/legal-entities/{entity}/exports", {"kind": "reinf_r4000_preview_v1"})
    assert missing.status_code == 400
    viewer = _post(client, tokens["viewer"], f"/v1/legal-entities/{entity}/exports", {"kind": "reinf_r4000_preview_v1", "period_id": _period(entity, 3)})
    assert viewer.status_code == 403
