from __future__ import annotations

import pytest
from botocore.exceptions import ClientError

from contabil.identity.directory import CognitoDirectory, UnavailableDirectory, parse_cognito_issuer
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal
from contabil.tenancy.service import invite_user


class _UnusedSession:
    def scalar(self, *_args, **_kwargs):
        raise AssertionError("a validação acontece antes da consulta")


class _Recorder:
    def __init__(self) -> None:
        self.added: list[object] = []

    def scalar(self, *_args, **_kwargs):
        return None

    def add(self, row: object) -> None:
        self.added.append(row)


class _OtherOffice:
    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None:
        del username, email, display_name, tenant_id
        raise DomainError(409, "Usuário de outro escritório", "Este nome de usuário já pertence a outro escritório.")


def _principal() -> Principal:
    return Principal("admin", "escritorio", frozenset({"admin"}), "Admin", "Escritório piloto")


def _client_error(code: str) -> ClientError:
    return ClientError({"Error": {"Code": code, "Message": "falha"}}, "AdminCreateUser")


class _Cognito:
    def __init__(self, existing_tenant: str | None = None, code: str | None = None) -> None:
        self.existing_tenant = existing_tenant
        self.code = code
        self.created: list[str] = []

    def admin_create_user(self, **kwargs):
        if self.code == "UsernameExistsException" or self.existing_tenant is not None:
            raise _client_error("UsernameExistsException")
        if self.code:
            raise _client_error(self.code)
        self.created.append(kwargs["Username"])
        assert kwargs["DesiredDeliveryMediums"] == ["EMAIL"]
        names = {item["Name"]: item["Value"] for item in kwargs["UserAttributes"]}
        assert "email" in names
        assert names["custom:tenant_id"] == "escritorio"

    def admin_get_user(self, **kwargs):
        del kwargs
        return {"UserAttributes": [{"Name": "custom:tenant_id", "Value": self.existing_tenant}]}


def test_parse_cognito_issuer() -> None:
    assert parse_cognito_issuer("https://cognito-idp.us-east-2.amazonaws.com/us-east-2_pool") == ("us-east-2", "us-east-2_pool")
    assert parse_cognito_issuer("http://localhost:8080/realms/contabil") is None


def test_missing_directory_is_unavailable() -> None:
    with pytest.raises(DomainError) as caught:
        UnavailableDirectory().create_user("ana", "ana@example.com", "Ana", "escritorio")
    assert caught.value.status_code == 503


def test_invalid_invite_does_not_touch_the_session() -> None:
    with pytest.raises(DomainError) as caught:
        invite_user(
            _UnusedSession(),  # type: ignore[arg-type]
            _principal(),
            UnavailableDirectory(),
            username="Ana Silva",
            display_name="Ana",
            email="ana@example.com",
            roles=["viewer"],
        )
    assert caught.value.status_code == 400
    with pytest.raises(DomainError) as caught:
        invite_user(
            _UnusedSession(),  # type: ignore[arg-type]
            _principal(),
            UnavailableDirectory(),
            username="ana",
            display_name="Ana",
            email="ana@example.com",
            roles=[],
        )
    assert caught.value.title == "Papel inválido"


def test_other_office_does_not_write_membership() -> None:
    session = _Recorder()
    with pytest.raises(DomainError) as caught:
        invite_user(
            session,  # type: ignore[arg-type]
            _principal(),
            _OtherOffice(),
            username="ana",
            display_name="Ana",
            email="ana@example.com",
            roles=["viewer"],
        )
    assert caught.value.status_code == 409
    assert session.added == []


def test_cognito_keeps_a_user_from_another_office() -> None:
    directory = CognitoDirectory(_Cognito(existing_tenant="outro"), "pool")
    with pytest.raises(DomainError) as caught:
        directory.create_user("ana", "ana@example.com", "Ana", "escritorio")
    assert caught.value.status_code == 409


def test_cognito_accepts_an_existing_user_of_the_same_office() -> None:
    client = _Cognito(existing_tenant="escritorio")
    CognitoDirectory(client, "pool").create_user("ana", "ana@example.com", "Ana", "escritorio")
    assert client.created == []


def test_cognito_hides_provider_failures() -> None:
    directory = CognitoDirectory(_Cognito(code="InvalidParameterException"), "pool")
    with pytest.raises(DomainError) as caught:
        directory.create_user("ana", "ana@example.com", "Ana", "escritorio")
    assert caught.value.status_code == 502
    assert "InvalidParameter" not in caught.value.detail
