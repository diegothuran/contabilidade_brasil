"""Correções P0 da auditoria de 2026-11-14: isolamento entre escritórios e empresas e guarda do livro."""
from __future__ import annotations

from uuid import uuid4

import pytest
from sqlalchemy import select, text

from contabil.identity.directory import get_user_directory
from contabil.platform.db import get_admin_engine, session_factory
from contabil.tables import Membership
from tests.integration.test_phase_a import _auth, _journal_body, _post, _publish
from tests.integration.test_phase_b import _relay, _upload
from tests.integration.test_user_invites import _OfficeDirectory
from tests.integration.world import add_entity

CONTENT = (
    "external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code\n"
    "ext-1;2026-09-15;Compra;5.1.01;debit;8.00;Despesa;\n"
    "ext-1;2026-09-15;Compra;2.1.01;credit;8.00;Fornecedor;\n"
).encode()


def _imported(entity_id: str) -> int:
    with get_admin_engine().connect() as connection:
        return int(
            connection.execute(
                text("SELECT count(*) FROM journal_entries WHERE source_type = 'import' AND legal_entity_id = :entity"),
                {"entity": entity_id},
            ).scalar_one()
        )


def _import_and_publish(client, tokens, entity_id: str) -> None:
    document = _upload(client, tokens["preparer"], CONTENT, legal_entity_id=entity_id)
    assert document.status_code in (200, 201), document.text
    body = {
        "legal_entity_id": entity_id,
        "source_system": "legado-unico",
        "mode": "dry_run",
        "period_id": f"{entity_id}-2026-09",
        "files": [{"document_id": document.json()["document_id"], "kind": "journal"}],
    }
    created = client.post("/v1/import-batches", json=body, headers=_auth(tokens["preparer"], uuid4().hex))
    assert created.status_code == 202, created.text
    _relay()
    batches = client.get(
        "/v1/import-batches", params={"legal_entity_id": entity_id}, headers=_auth(tokens["preparer"])
    ).json()["items"]
    ready = next(item for item in batches if item["status"] == "ready")
    rows = client.get(
        f"/v1/import-batches/{ready['batch_id']}/rows",
        params={"status": "already_imported"},
        headers=_auth(tokens["viewer"]),
    )
    assert rows.json()["items"] == []
    published = _post(client, tokens["approver"], f"/v1/import-batches/{ready['batch_id']}/publish")
    assert published.status_code == 202, published.text
    _relay()


def test_invite_refuses_username_from_another_office(client, tokens, world, app):
    """fix-1: o convite não toma o login de quem já tem vínculo em outro escritório."""
    del world
    app.dependency_overrides[get_user_directory] = lambda: _OfficeDirectory()
    try:
        response = _post(
            client,
            tokens["admin"],
            "/v1/users",
            {"username": "outsider", "display_name": "Outro", "email": "o@example.com", "roles": ["viewer"]},
        )
        assert response.status_code == 409, response.text
        session = session_factory(admin=True)()
        try:
            stolen = session.scalar(
                select(Membership).where(Membership.tenant_id == "tenant_demo", Membership.user_id == "outsider")
            )
            assert stolen is None
        finally:
            session.close()
    finally:
        app.dependency_overrides.pop(get_user_directory, None)


def test_second_company_imports_same_external_ids(client, tokens, world):
    """fix-2: a memória de importação é por empresa, não por escritório."""
    del world
    add_entity("le_second", "tenant_demo", "Segunda Empresa", "100000000002")
    _import_and_publish(client, tokens, "le_test")
    _import_and_publish(client, tokens, "le_second")
    assert _imported("le_test") == 1
    assert _imported("le_second") == 1


def test_same_file_enters_two_companies(client, tokens, world):
    """D3: o mesmo arquivo pode estar em empresas diferentes, inclusive de escritórios diferentes."""
    del world
    add_entity("le_second", "tenant_demo", "Segunda Empresa", "100000000002")
    first = _upload(client, tokens["preparer"], b"mesmo-arquivo", legal_entity_id="le_test")
    second = _upload(client, tokens["preparer"], b"mesmo-arquivo", legal_entity_id="le_second")
    assert first.status_code == 201, first.text
    assert second.status_code == 201, second.text
    assert first.json()["document_id"] != second.json()["document_id"]
    assert second.json()["legal_entity_id"] == "le_second"
    again = _upload(client, tokens["preparer"], b"mesmo-arquivo", legal_entity_id="le_second")
    assert again.status_code == 200
    assert again.json()["document_id"] == second.json()["document_id"]
    other_office = _upload(client, tokens["outsider"], b"mesmo-arquivo", legal_entity_id="le_other")
    assert other_office.status_code == 201, other_office.text
    downloaded = client.get(f"/v1/documents/{second.json()['document_id']}/content", headers=_auth(tokens["viewer"]))
    assert downloaded.content == b"mesmo-arquivo"


@pytest.mark.parametrize("source_type", ["import", "fiscal_document", "bank", "payable"])
def test_public_route_refuses_subledger_source(client, tokens, world, source_type):
    """fix-3: a tela não declara origem de subledger."""
    del world
    response = _post(client, tokens["preparer"], "/v1/journals", _journal_body(source_type=source_type, source_id="x"))
    assert response.status_code == 400, response.text


def test_public_route_accepts_adjustment(client, tokens, world):
    del world
    response = _post(client, tokens["preparer"], "/v1/journals", _journal_body(source_type="adjustment"))
    assert response.status_code == 201, response.text


def test_line_cannot_leave_published_journal(client, tokens, world):
    """fix-5: UPDATE de journal_id não tira linha de journal publicado."""
    del world
    published = _publish(client, tokens)
    draft = _post(client, tokens["preparer"], "/v1/journals", _journal_body(description="Rascunho"))
    assert draft.status_code == 201
    with pytest.raises(Exception, match="another journal"):
        with get_admin_engine().begin() as connection:
            connection.execute(
                text(
                    "UPDATE journal_lines SET journal_id = :draft "
                    "WHERE id = (SELECT id FROM journal_lines WHERE journal_id = :published LIMIT 1)"
                ),
                {"draft": draft.json()["journal_id"], "published": published["journal_id"]},
            )


@pytest.mark.parametrize("table", ["journal_lines", "journal_entries", "audit_events"])
def test_truncate_is_blocked(client, tokens, world, table):
    """fix-5: TRUNCATE não apaga livro nem trilha."""
    del world
    _publish(client, tokens)
    with pytest.raises(Exception, match="cannot be truncated"):
        with get_admin_engine().begin() as connection:
            connection.execute(text(f"TRUNCATE {table} CASCADE"))
