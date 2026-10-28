from __future__ import annotations

import argparse
import sys

from sqlalchemy import select

from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import AppUser, Membership, Tenant

ROLES = frozenset({"preparer", "approver", "admin", "viewer", "client"})


def bootstrap(
    tenant_id: str,
    tenant_name: str,
    user_id: str,
    display_name: str,
    roles: list[str],
    legal_entity_id: str | None = None,
) -> None:
    user_id = user_id.strip().lower()
    unknown = [role for role in roles if role not in ROLES]
    if not roles or unknown:
        raise ValueError("Papéis aceitos: preparer, approver, admin, viewer, client.")
    if "client" in roles and (roles != ["client"] or not legal_entity_id):
        raise ValueError("O cliente fica ligado a uma empresa e não acumula papel do escritório.")
    session = session_factory(admin=True)()
    try:
        if session.get(Tenant, tenant_id) is None:
            session.add(Tenant(id=tenant_id, name=tenant_name))
            session.flush()
        if session.get(AppUser, user_id) is None:
            session.add(AppUser(id=user_id, display_name=display_name))
            session.flush()
        apply_tenant(session, tenant_id)
        existing = session.scalar(
            select(Membership).where(Membership.tenant_id == tenant_id, Membership.user_id == user_id)
        )
        if existing is None:
            session.add(
                Membership(
                    id=f"mem_{tenant_id}_{user_id}",
                    tenant_id=tenant_id,
                    user_id=user_id,
                    roles=roles,
                    legal_entity_id=legal_entity_id if "client" in roles else None,
                )
            )
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cria o escritório e o primeiro usuário do piloto.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--tenant-name", required=True)
    parser.add_argument("--user-id", required=True)
    parser.add_argument("--display-name", required=True)
    parser.add_argument("--roles", required=True, help="Papéis separados por vírgula.")
    args = parser.parse_args(argv)
    roles = [item.strip() for item in args.roles.split(",") if item.strip()]
    try:
        bootstrap(args.tenant_id, args.tenant_name, args.user_id, args.display_name, roles)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc


if __name__ == "__main__":
    main(sys.argv[1:])
