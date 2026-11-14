from __future__ import annotations

from functools import lru_cache
from typing import Literal

from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


def _postgres_url(value: object) -> object:
    if not isinstance(value, str) or not value:
        return value
    if value.startswith("postgres://"):
        return "postgresql+psycopg://" + value[len("postgres://") :]
    if value.startswith("postgresql://"):
        return "postgresql+psycopg://" + value[len("postgresql://") :]
    return value


_DEVELOPMENT_MARKERS = ("dev-only", "localhost", "127.0.0.1")


def _looks_local(value: str | None) -> bool:
    return any(marker in (value or "") for marker in _DEVELOPMENT_MARKERS)


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # development aceita os padrões de localhost. pilot e production recusam a subida
    # com valor de exemplo; a imagem do piloto (Dockerfile da raiz) fixa ENVIRONMENT=pilot.
    environment: Literal["development", "pilot", "production"] = "development"
    database_url: str = "postgresql+psycopg://contabil_app:dev-only-db-password@localhost:5432/contabil"
    database_admin_url: str | None = None
    oidc_issuer: str = "http://localhost:8080/realms/contabil"
    oidc_audience: str = "contabil-api"
    oidc_jwks_url: str = "http://localhost:8080/realms/contabil/protocol/openid-connect/certs"
    oidc_token_url: str = "http://localhost:8080/realms/contabil/protocol/openid-connect/token"
    oidc_username_claim: str = "preferred_username"
    oidc_tenant_claim: str = "tenant_id"
    cors_origins: str = "http://localhost:5173"
    schemas_dir: str = ""
    dev_user_password: str = "dev-only-password"
    app_home: str = "/app"
    object_storage_endpoint: str = "http://localhost:9000"
    object_storage_bucket: str = "contabil-dev"
    object_storage_access_key: str = "dev-only-minio"
    object_storage_secret_key: str = "dev-only-minio-secret"
    object_storage_region: str = "us-east-1"
    max_upload_bytes: int = 52_428_800
    max_import_rows: int = 100_000
    reconciliation_date_tolerance_days: int = 3
    outbox_in_process: bool = False
    static_dir: str = ""
    seed_demo: bool = False
    object_storage_create_buckets: bool = False
    cognito_admin_access_key: str = ""
    cognito_admin_secret_key: str = ""
    mail_from: str = ""
    ses_access_key: str = ""
    ses_secret_key: str = ""
    portal_base_url: str = ""

    @field_validator("database_url", "database_admin_url", mode="before")
    @classmethod
    def normalize_database_url(cls, value: object) -> object:
        if value == "":
            return None
        return _postgres_url(value)

    @model_validator(mode="after")
    def default_admin_url(self) -> "Settings":
        if not self.database_admin_url:
            self.database_admin_url = self.database_url
        return self

    @model_validator(mode="after")
    def refuse_development_values_outside_development(self) -> "Settings":
        if self.environment == "development":
            return self
        problems: list[str] = []
        for name in (
            "database_url",
            "database_admin_url",
            "oidc_issuer",
            "oidc_jwks_url",
            "object_storage_endpoint",
            "object_storage_access_key",
            "object_storage_secret_key",
        ):
            if _looks_local(getattr(self, name)):
                problems.append(f"{name.upper()} usa valor de desenvolvimento")
        if self.oidc_audience == "contabil-api":
            problems.append("OIDC_AUDIENCE usa valor de desenvolvimento")
        for name in ("oidc_username_claim", "oidc_tenant_claim"):
            if name not in self.model_fields_set:
                problems.append(f"{name.upper()} precisa ser definido")
        if self.seed_demo:
            problems.append("SEED_DEMO não pode estar ligado")
        if problems:
            raise ValueError(f"configuração inválida para {self.environment}: " + "; ".join(problems))
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
