from __future__ import annotations

import logging
from typing import Protocol

import boto3
from botocore.exceptions import ClientError

from contabil.platform.errors import DomainError
from contabil.platform.settings import get_settings

logger = logging.getLogger(__name__)


class UserDirectory(Protocol):
    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None: ...


class UnavailableDirectory:
    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None:
        del username, email, display_name, tenant_id
        raise DomainError(
            503,
            "Diretório de usuários não configurado",
            "O convite por e-mail ainda não está ligado neste ambiente.",
        )


def parse_cognito_issuer(issuer: str) -> tuple[str, str] | None:
    prefix = "https://cognito-idp."
    marker = ".amazonaws.com/"
    if not issuer.startswith(prefix) or marker not in issuer:
        return None
    region, _, pool = issuer[len(prefix) :].partition(marker)
    pool = pool.strip("/")
    if not region or not pool or "/" in pool:
        return None
    return region, pool


class CognitoDirectory:
    def __init__(self, client, user_pool_id: str) -> None:
        self._client = client
        self._pool = user_pool_id

    def create_user(self, username: str, email: str, display_name: str, tenant_id: str) -> None:
        del display_name
        try:
            self._client.admin_create_user(
                UserPoolId=self._pool,
                Username=username,
                UserAttributes=[
                    {"Name": "email", "Value": email},
                    {"Name": "email_verified", "Value": "true"},
                    {"Name": "custom:tenant_id", "Value": tenant_id},
                ],
                DesiredDeliveryMediums=["EMAIL"],
            )
        except ClientError as exc:
            if _error_code(exc) == "UsernameExistsException":
                self._require_same_office(username, tenant_id)
                return
            if _error_code(exc) == "AliasExistsException":
                raise DomainError(409, "E-mail já usado", "Este e-mail já está ligado a outro usuário.") from exc
            logger.warning("cognito admin_create_user code=%s", _error_code(exc))
            raise DomainError(502, "Falha ao convidar", "O diretório não concluiu o convite.") from exc

    def _require_same_office(self, username: str, tenant_id: str) -> None:
        try:
            current = self._client.admin_get_user(UserPoolId=self._pool, Username=username)
        except ClientError as exc:
            logger.warning("cognito admin_get_user code=%s", _error_code(exc))
            raise DomainError(502, "Falha ao convidar", "O diretório não concluiu o convite.") from exc
        attributes = {item["Name"]: item["Value"] for item in current.get("UserAttributes", [])}
        if attributes.get("custom:tenant_id") != tenant_id:
            raise DomainError(409, "Usuário de outro escritório", "Este nome de usuário já pertence a outro escritório.")


def _error_code(exc: ClientError) -> str:
    return str(exc.response.get("Error", {}).get("Code", ""))


def get_user_directory() -> UserDirectory:
    settings = get_settings()
    access_key = settings.cognito_admin_access_key.strip()
    secret_key = settings.cognito_admin_secret_key.strip()
    parsed = parse_cognito_issuer(settings.oidc_issuer)
    if not access_key or not secret_key or parsed is None:
        return UnavailableDirectory()
    region, pool_id = parsed
    client = boto3.client(
        "cognito-idp",
        region_name=region,
        aws_access_key_id=access_key,
        aws_secret_access_key=secret_key,
    )
    return CognitoDirectory(client, pool_id)
