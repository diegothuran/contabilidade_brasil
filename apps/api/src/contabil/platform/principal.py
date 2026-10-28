from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class Principal:
    user_id: str
    tenant_id: str
    roles: frozenset[str]
    display_name: str
    tenant_name: str
    home_tenant_id: str = ""
    legal_entity_id: str | None = None


OFFICE_ROLES = frozenset({"preparer", "approver", "admin", "viewer"})


def is_client(principal: Principal) -> bool:
    return principal.roles == frozenset({"client"})


def ensure_office(principal: Principal) -> None:
    from contabil.platform.errors import DomainError

    if "client" in principal.roles or principal.roles.isdisjoint(OFFICE_ROLES):
        raise DomainError(403, "Ação não permitida", "O acesso de cliente não abre o escritório.")


def ensure_client(principal: Principal) -> None:
    from contabil.platform.errors import DomainError

    if not is_client(principal) or not principal.legal_entity_id:
        raise DomainError(403, "Ação não permitida", "Este acesso é do cliente da empresa.")


def ensure_role(principal: Principal, *roles: str) -> None:
    from contabil.platform.errors import DomainError

    if principal.roles.isdisjoint(roles):
        raise DomainError(403, "Ação não permitida", "Papel insuficiente para esta operação.")
