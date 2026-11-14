"""fix-8: fora de desenvolvimento, configuração de exemplo recusa a subida."""
from __future__ import annotations

import pytest
from pydantic import ValidationError

from contabil.platform.settings import Settings

PILOT = {
    "environment": "pilot",
    "database_url": "postgres://app:segredo@db.example.com:5432/contabil",
    "oidc_issuer": "https://cognito-idp.us-east-2.amazonaws.com/POOL",
    "oidc_audience": "client-id",
    "oidc_jwks_url": "https://cognito-idp.us-east-2.amazonaws.com/POOL/.well-known/jwks.json",
    "oidc_username_claim": "cognito:username",
    "oidc_tenant_claim": "custom:tenant_id",
    "object_storage_endpoint": "https://s3.us-east-2.amazonaws.com",
    "object_storage_access_key": "AKIAEXEMPLO",
    "object_storage_secret_key": "segredo-real",
}


@pytest.fixture(autouse=True)
def _clean_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    # O container de integração exporta as variáveis do compose; o teste olha só o que passa.
    for name in Settings.model_fields:
        monkeypatch.delenv(name.upper(), raising=False)


def _settings(**overrides) -> Settings:
    values = {**PILOT, **overrides}
    return Settings(_env_file=None, **{key: value for key, value in values.items() if value is not None})


def test_pilot_with_full_configuration_starts() -> None:
    assert _settings().environment == "pilot"


def test_development_keeps_local_defaults() -> None:
    settings = Settings(_env_file=None, environment="development")
    assert settings.oidc_username_claim == "preferred_username"


@pytest.mark.parametrize(
    ("field", "value", "fragment"),
    [
        ("database_url", "postgresql+psycopg://contabil_app:dev-only-db-password@localhost:5432/contabil", "DATABASE_URL"),
        ("oidc_issuer", "http://localhost:8080/realms/contabil", "OIDC_ISSUER"),
        ("oidc_jwks_url", "http://localhost:8080/realms/contabil/protocol/openid-connect/certs", "OIDC_JWKS_URL"),
        ("oidc_audience", "contabil-api", "OIDC_AUDIENCE"),
        ("object_storage_access_key", "dev-only-minio", "OBJECT_STORAGE_ACCESS_KEY"),
        ("object_storage_secret_key", "dev-only-minio-secret", "OBJECT_STORAGE_SECRET_KEY"),
        ("object_storage_endpoint", "http://localhost:9000", "OBJECT_STORAGE_ENDPOINT"),
        ("seed_demo", True, "SEED_DEMO"),
    ],
)
def test_pilot_refuses_development_values(field: str, value: object, fragment: str) -> None:
    with pytest.raises(ValidationError, match=fragment):
        _settings(**{field: value})


@pytest.mark.parametrize(("field", "fragment"), [("oidc_username_claim", "OIDC_USERNAME_CLAIM"), ("oidc_tenant_claim", "OIDC_TENANT_CLAIM")])
def test_pilot_requires_explicit_identity_claims(field: str, fragment: str) -> None:
    with pytest.raises(ValidationError, match=fragment):
        _settings(**{field: None})


def test_unknown_environment_is_refused() -> None:
    with pytest.raises(ValidationError):
        _settings(environment="prod")
