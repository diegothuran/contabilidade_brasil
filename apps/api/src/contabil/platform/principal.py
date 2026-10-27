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


def ensure_role(principal: Principal, *roles: str) -> None:
    from contabil.platform.errors import DomainError

    if principal.roles.isdisjoint(roles):
        raise DomainError(403, "Ação não permitida", "Papel insuficiente para esta operação.")
