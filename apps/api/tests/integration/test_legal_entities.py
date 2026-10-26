from __future__ import annotations

from uuid import uuid4

from sqlalchemy import func, select

from contabil.platform.db import session_factory
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import Account, AccountingPeriod, AuditEvent, LegalEntity
from tests.integration.test_phase_a import _auth, _journal_body, _post, _publish


def test_admin_creates_company_with_chart_periods_and_audit(client, tokens, world):
    del world
    number = cnpj_digits("910000000001")
    created = _post(
        client,
        tokens["admin"],
        "/v1/legal-entities",
        {"name": "Empresa Nova", "cnpj": f"{number[:2]}.{number[2:5]}.{number[5:8]}/{number[8:12]}-{number[12:]}", "fiscal_year": 2026},
    )
    assert created.status_code == 201, created.text
    body = created.json()
    assert body["accounts_created"] == 11
    assert body["periods_created"] == 12
    assert body["cnpj"] == number
    entity_id = body["legal_entity_id"]
    accounts = client.get(f"/v1/legal-entities/{entity_id}/accounts", headers=_auth(tokens["admin"]))
    periods = client.get(f"/v1/legal-entities/{entity_id}/periods", headers=_auth(tokens["admin"]))
    assert accounts.status_code == 200
    assert len(accounts.json()["items"]) == 11
    assert periods.status_code == 200
    assert len(periods.json()["items"]) == 12
    session = session_factory(admin=True)()
    try:
        event = session.scalar(
            select(AuditEvent).where(AuditEvent.tenant_id == "tenant_demo", AuditEvent.target_ref == entity_id)
        )
        assert event is not None
        assert event.event_type == "other"
        assert event.details["action"] == "legal_entity_created"
    finally:
        session.close()
    published = _publish(
        client,
        tokens,
        _journal_body(
            legal_entity_id=entity_id,
            period_id=f"{entity_id}-2026-09",
            lines=[
                {"account_id": f"{entity_id}-5.1.01", "side": "debit", "amount": "10.00", "description": "Débito"},
                {"account_id": f"{entity_id}-2.1.01", "side": "credit", "amount": "10.00", "description": "Crédito"},
            ],
        ),
    )
    assert published["status"] == "published"


def test_only_admin_creates_a_company(client, tokens, world):
    del world
    body = {"name": "Empresa Bloqueada", "cnpj": cnpj_digits("910000000002"), "fiscal_year": 2026}
    assert _post(client, tokens["viewer"], "/v1/legal-entities", body).status_code == 403
    assert _post(client, tokens["preparer"], "/v1/legal-entities", body).status_code == 403


def test_invalid_and_duplicate_cnpj(client, tokens, world):
    del world
    invalid = _post(client, tokens["admin"], "/v1/legal-entities", {"name": "Ruim", "cnpj": "11111111111111", "fiscal_year": 2026})
    assert invalid.status_code == 400
    assert invalid.json()["title"] == "CNPJ inválido"
    number = cnpj_digits("910000000003")
    body = {"name": "Primeira", "cnpj": number, "fiscal_year": 2026}
    assert _post(client, tokens["admin"], "/v1/legal-entities", body).status_code == 201
    duplicate = _post(client, tokens["admin"], "/v1/legal-entities", {"name": "Segunda", "cnpj": number, "fiscal_year": 2026})
    assert duplicate.status_code == 409
    assert duplicate.json()["title"] == "CNPJ já cadastrado"


def test_same_idempotency_key_replays_the_company(client, tokens, world):
    del world
    key = uuid4().hex
    body = {"name": "Idempotente", "cnpj": cnpj_digits("910000000004"), "fiscal_year": 2026}
    first = _post(client, tokens["admin"], "/v1/legal-entities", body, key)
    second = _post(client, tokens["admin"], "/v1/legal-entities", body, key)
    assert first.status_code == 201
    assert second.status_code == 201
    assert first.json()["legal_entity_id"] == second.json()["legal_entity_id"]
    session = session_factory(admin=True)()
    try:
        count = session.scalar(select(func.count()).select_from(LegalEntity).where(LegalEntity.cnpj == body["cnpj"]))
        assert count == 1
    finally:
        session.close()


def test_other_office_does_not_see_the_company(client, tokens, world):
    del world
    created = _post(
        client,
        tokens["admin"],
        "/v1/legal-entities",
        {"name": "Invisível", "cnpj": cnpj_digits("910000000005"), "fiscal_year": 2026},
    )
    assert created.status_code == 201
    listed = client.get("/v1/legal-entities", headers=_auth(tokens["outsider"]))
    assert listed.status_code == 200
    assert created.json()["legal_entity_id"] not in {item["legal_entity_id"] for item in listed.json()["items"]}
    session = session_factory(admin=True)()
    try:
        accounts = session.scalar(select(func.count()).select_from(Account).where(Account.legal_entity_id == created.json()["legal_entity_id"]))
        periods = session.scalar(
            select(func.count()).select_from(AccountingPeriod).where(AccountingPeriod.legal_entity_id == created.json()["legal_entity_id"])
        )
        assert accounts == 11
        assert periods == 12
    finally:
        session.close()
