from __future__ import annotations

import string

import pytest
from botocore.exceptions import ClientError

from contabil.identity.directory import CognitoDirectory
from contabil.pilot_round import fictitious_email, round_requests, temporary_password
from contabil.platform.errors import DomainError


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "falha"}}, "AdminCreateUser")


class _Cognito:
    def __init__(self, code: str | None = None, existing_tenant: str = "escritorio") -> None:
        self.code = code
        self.existing_tenant = existing_tenant
        self.calls: list[dict] = []

    def admin_create_user(self, **kwargs):
        self.calls.append(kwargs)
        if self.code:
            raise _client_error(self.code)

    def admin_get_user(self, **kwargs):
        del kwargs
        return {"UserAttributes": [{"Name": "custom:tenant_id", "Value": self.existing_tenant}]}


def test_temporary_password_meets_the_default_policy() -> None:
    for _ in range(50):
        value = temporary_password()
        assert len(value) == 16
        assert any(char in string.ascii_uppercase for char in value)
        assert any(char in string.ascii_lowercase for char in value)
        assert any(char in string.digits for char in value)
        assert any(not char.isalnum() for char in value)
    assert temporary_password() != temporary_password()


def test_fictitious_email_uses_the_reserved_domain() -> None:
    assert fictitious_email("cliente-andamento", "escritorio") == "cliente-andamento.escritorio@example.com"


def test_round_requests_follow_the_scenario_and_month() -> None:
    padaria = round_requests("andamento", 11)
    assert padaria[0] == ("bank_statement", "Rodada: extrato bancário de novembro")
    assert padaria[1][0] == "invoice"
    assert round_requests("clinica", 11)[1] == ("contract", "Rodada: contrato social e última alteração")
    assert round_requests("desconhecido", 1) == [("bank_statement", "Rodada: extrato bancário de janeiro")]


def test_test_login_sets_the_password_and_suppresses_the_email() -> None:
    cognito = _Cognito()
    assert CognitoDirectory(cognito, "pool").create_test_login("cliente-banco", "x@example.com", "escritorio", "Aa1!aaaaaaaaaaaa")
    call = cognito.calls[0]
    assert call["MessageAction"] == "SUPPRESS"
    assert call["TemporaryPassword"] == "Aa1!aaaaaaaaaaaa"
    assert "DesiredDeliveryMediums" not in call
    names = {item["Name"]: item["Value"] for item in call["UserAttributes"]}
    assert names == {"email": "x@example.com", "email_verified": "true", "custom:tenant_id": "escritorio"}


def test_existing_login_keeps_its_password() -> None:
    directory = CognitoDirectory(_Cognito("UsernameExistsException"), "pool")
    assert directory.create_test_login("cliente-banco", "x@example.com", "escritorio", "Aa1!aaaaaaaaaaaa") is False


def test_existing_login_from_another_office_is_refused() -> None:
    directory = CognitoDirectory(_Cognito("UsernameExistsException", existing_tenant="outro"), "pool")
    with pytest.raises(DomainError) as caught:
        directory.create_test_login("cliente-banco", "x@example.com", "escritorio", "Aa1!aaaaaaaaaaaa")
    assert caught.value.status_code == 409


def test_password_policy_refusal_is_reported() -> None:
    directory = CognitoDirectory(_Cognito("InvalidPasswordException"), "pool")
    with pytest.raises(DomainError) as caught:
        directory.create_test_login("cliente-banco", "x@example.com", "escritorio", "fraca")
    assert caught.value.status_code == 400
