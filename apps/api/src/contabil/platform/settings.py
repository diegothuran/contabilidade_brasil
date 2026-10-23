from __future__ import annotations

from functools import lru_cache

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


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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


@lru_cache
def get_settings() -> Settings:
    return Settings()
