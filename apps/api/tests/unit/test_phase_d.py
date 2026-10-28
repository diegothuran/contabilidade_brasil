from __future__ import annotations

from types import SimpleNamespace

import pytest

from contabil.audit.hash import content_hash
from contabil.document_requests.service import blocks_close, queue_statuses
from contabil.exports.service import DISCLAIMER, assemble_operational_package
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal, ensure_client, ensure_office
from contabil.tenancy.service import invite_user


def test_open_and_received_block_the_close() -> None:
    assert blocks_close("open") is True
    assert blocks_close("received") is True
    assert blocks_close("confirmed") is False
    assert blocks_close("cancelled") is False


def test_queue_defaults_to_blocking_statuses() -> None:
    assert queue_statuses(None) == ["open", "received"]
    assert queue_statuses(" confirmed, open ") == ["confirmed", "open"]
    with pytest.raises(DomainError):
        queue_statuses("publicado")


def test_operational_package_hash_is_stable() -> None:
    package = assemble_operational_package(
        generated_at="2026-10-27T00:00:00Z",
        tenant_id="escritorio",
        legal_entity_id="le_teste",
        name="Padaria Aurora Ltda. (teste)",
        cnpj="90000000000191",
        period_id="le_teste-2026-10",
        fiscal_year=2026,
        month=10,
        journals=[{"journal_id": "jr_1", "entry_date": "2026-10-02", "description": "Venda", "status": "published"}],
        documents=[],
        document_requests=[
            {
                "document_request_id": "dreq_1",
                "title": "Recibo",
                "status": "open",
                "due_on": "2026-10-20",
                "blocks_close": True,
            }
        ],
        audit_events=[],
        currency="BRL",
        debit_total="10",
        credit_total="10",
    )
    again = assemble_operational_package(
        generated_at="2026-10-27T00:00:00Z",
        tenant_id="escritorio",
        legal_entity_id="le_teste",
        name="Padaria Aurora Ltda. (teste)",
        cnpj="90000000000191",
        period_id="le_teste-2026-10",
        fiscal_year=2026,
        month=10,
        journals=[{"journal_id": "jr_1", "entry_date": "2026-10-02", "description": "Venda", "status": "published"}],
        documents=[],
        document_requests=[
            {
                "document_request_id": "dreq_1",
                "title": "Recibo",
                "status": "open",
                "due_on": "2026-10-20",
                "blocks_close": True,
            }
        ],
        audit_events=[],
        currency="BRL",
        debit_total="10",
        credit_total="10",
    )
    assert package["sha256"] == again["sha256"]
    assert package["disclaimer"] == DISCLAIMER
    body = {key: value for key, value in package.items() if key != "sha256"}
    assert content_hash(body) == package["sha256"]


def test_client_does_not_open_the_office() -> None:
    client = Principal("cliente", "escritorio", frozenset({"client"}), "Cliente", "Escritório", legal_entity_id="le_teste")
    office = Principal("admin", "escritorio", frozenset({"admin"}), "Admin", "Escritório")
    ensure_client(client)
    ensure_office(office)
    with pytest.raises(DomainError):
        ensure_office(client)
    with pytest.raises(DomainError):
        ensure_client(office)


class _Unused:
    def scalar(self, *_args, **_kwargs):
        raise AssertionError("a validação acontece antes da consulta")


def test_client_invite_needs_the_company_and_no_office_role() -> None:
    principal = Principal("admin", "escritorio", frozenset({"admin"}), "Admin", "Escritório")
    with pytest.raises(DomainError) as missing:
        invite_user(
            _Unused(),
            principal,
            _Unused(),
            username="cliente.padaria",
            display_name="Cliente de teste",
            email="cliente@example.com",
            roles=["client"],
        )
    assert missing.value.title == "Empresa obrigatória"
    with pytest.raises(DomainError) as mixed:
        invite_user(
            _Unused(),
            principal,
            _Unused(),
            username="cliente.padaria",
            display_name="Cliente de teste",
            email="cliente@example.com",
            roles=["client", "viewer"],
            legal_entity_id="le_teste",
        )
    assert mixed.value.title == "Papel inválido"


class _ExistingClient:
    def __init__(self, entity_id: str) -> None:
        self.membership = SimpleNamespace(roles=["client"], legal_entity_id=entity_id)
        self.added: list[object] = []
        self._answers = [SimpleNamespace(id="le_teste"), self.membership]

    def scalar(self, *_args, **_kwargs):
        return self._answers.pop(0)

    def get(self, _model, _key):
        return SimpleNamespace(display_name="Cliente da amostra")

    def add(self, row: object) -> None:
        self.added.append(row)

    def flush(self) -> None:
        pass


class _Directory:
    def __init__(self) -> None:
        self.created: list[str] = []

    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None:
        del email, display_name, tenant_id
        self.created.append(username)


def _invite_existing(session: _ExistingClient, directory: _Directory) -> dict:
    return invite_user(
        session,  # type: ignore[arg-type]
        Principal("admin", "escritorio", frozenset({"admin"}), "Admin", "Escritório"),
        directory,
        username="cliente-fechada",
        display_name="Outro nome",
        email="cliente@example.com",
        roles=["client"],
        legal_entity_id="le_teste",
    )


def test_invite_completes_the_login_of_an_existing_client(monkeypatch: pytest.MonkeyPatch) -> None:
    events: list[dict] = []
    monkeypatch.setattr("contabil.tenancy.service.append_event", lambda _session, **kwargs: events.append(kwargs))
    session, directory = _ExistingClient("le_teste"), _Directory()
    result = _invite_existing(session, directory)
    assert directory.created == ["cliente-fechada"]
    assert session.added == []
    assert result["display_name"] == "Cliente da amostra"
    assert events[0]["metadata"]["action"] == "client_login_completed"


def test_invite_keeps_a_client_of_another_company() -> None:
    session, directory = _ExistingClient("le_outra"), _Directory()
    with pytest.raises(DomainError) as caught:
        _invite_existing(session, directory)
    assert caught.value.status_code == 409
    assert directory.created == []
