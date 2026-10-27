from __future__ import annotations

import logging
import re
from datetime import datetime, timezone

import jwt
from jwt import PyJWKClient
from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal
from contabil.platform.settings import get_settings
from contabil.tables import AppUser, Membership, Tenant

logger = logging.getLogger(__name__)
_jwk_client: PyJWKClient | None = None
_TENANT_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,78}$")


def chosen_tenant(home: str, requested: str | None) -> str:
    value = (requested or "").strip()
    if not value or value == home:
        return home
    if _TENANT_ID.fullmatch(value) is None:
        raise DomainError(403, "Ação não permitida", "Usuário sem acesso a este escritório.")
    return value


def apply_tenant(session: Session, tenant_id: str) -> None:
    session.execute(text("SELECT set_config('app.tenant_id', :tenant_id, true)"), {"tenant_id": tenant_id})


def bind_user(session: Session, user_id: str) -> None:
    session.execute(text("SELECT set_config('app.user_id', :user_id, true)"), {"user_id": user_id})


def format_utc(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).replace(microsecond=0).strftime("%Y-%m-%dT%H:%M:%SZ")


def decode_token(token: str) -> dict:
    global _jwk_client
    settings = get_settings()
    if _jwk_client is None:
        _jwk_client = PyJWKClient(settings.oidc_jwks_url, cache_keys=True, lifespan=300)
    try:
        signing_key = _jwk_client.get_signing_key_from_jwt(token)
        return jwt.decode(
            token,
            signing_key.key,
            algorithms=["RS256"],
            audience=settings.oidc_audience,
            issuer=settings.oidc_issuer,
            leeway=10,
        )
    except jwt.InvalidIssuerError as exc:
        unverified = jwt.decode(token, options={"verify_signature": False})
        logger.warning("issuer rejeitado: %s esperado: %s", unverified.get("iss"), settings.oidc_issuer)
        raise DomainError(401, "Não autenticado", "Token inválido ou expirado.") from exc
    except jwt.InvalidAudienceError as exc:
        unverified = jwt.decode(token, options={"verify_signature": False})
        logger.warning("audience rejeitada: %s esperada: %s", unverified.get("aud"), settings.oidc_audience)
        raise DomainError(401, "Não autenticado", "Token inválido ou expirado.") from exc
    except jwt.PyJWTError as exc:
        raise DomainError(401, "Não autenticado", "Token inválido ou expirado.") from exc


def _claim(payload: dict, name: str) -> object:
    value = payload.get(name)
    if isinstance(value, list):
        return value[0] if value else None
    return value


def authenticate(session: Session, token: str, requested_tenant: str | None = None) -> Principal:
    payload = decode_token(token)
    settings = get_settings()
    username = _claim(payload, settings.oidc_username_claim)
    tenant_id = _claim(payload, settings.oidc_tenant_claim)
    if not isinstance(username, str) or not username:
        logger.warning("token sem a claim %s", settings.oidc_username_claim)
        raise DomainError(401, "Não autenticado", "O token não identifica o usuário.")
    if isinstance(tenant_id, list):
        tenant_id = tenant_id[0] if tenant_id else None
    if not isinstance(tenant_id, str) or not tenant_id:
        logger.warning("token sem a claim %s", settings.oidc_tenant_claim)
        raise DomainError(401, "Não autenticado", "O token não identifica o escritório.")
    chosen = chosen_tenant(tenant_id, requested_tenant)
    apply_tenant(session, tenant_id)
    bind_user(session, username)
    if chosen != tenant_id:
        allowed = session.scalar(
            select(Membership.id).where(Membership.user_id == username, Membership.tenant_id == chosen)
        )
        if allowed is None:
            raise DomainError(403, "Ação não permitida", "Usuário sem acesso a este escritório.")
        apply_tenant(session, chosen)
    row = session.execute(
        select(Membership, AppUser.display_name, Tenant.name)
        .join(AppUser, AppUser.id == Membership.user_id)
        .join(Tenant, Tenant.id == Membership.tenant_id)
        .where(Membership.user_id == username, Membership.tenant_id == chosen)
    ).one_or_none()
    if row is None:
        raise DomainError(403, "Ação não permitida", "Usuário sem acesso a este escritório.")
    membership, display_name, tenant_name = row
    roles = frozenset(membership.roles or [])
    if not roles:
        raise DomainError(403, "Ação não permitida", "Usuário sem papel neste escritório.")
    return Principal(
        user_id=username,
        tenant_id=chosen,
        roles=roles,
        display_name=display_name,
        tenant_name=tenant_name,
    )
