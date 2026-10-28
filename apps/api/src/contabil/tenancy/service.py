from __future__ import annotations

import base64
import re
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.bootstrap import ROLES
from contabil.identity.directory import UserDirectory
from contabil.master_data.starter_chart import ACCOUNT_SPECS, STARTER_CHART_NAME, add_open_year, add_starter_chart
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import AppUser, Establishment, LegalEntity, Membership

_USERNAME = re.compile(r"^[A-Za-z0-9._-]{1,64}$")
_EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def require_entity(session: Session, tenant_id: str, legal_entity_id: str) -> LegalEntity:
    entity = session.scalar(select(LegalEntity).where(LegalEntity.id == legal_entity_id, LegalEntity.tenant_id == tenant_id))
    if entity is None:
        raise DomainError(404, "Não encontrado", "Empresa não encontrada.")
    return entity


def normalize_cnpj(value: str) -> str:
    return "".join(char for char in value if char.isdigit())


def valid_cnpj(value: str) -> bool:
    digits = normalize_cnpj(value)
    if len(digits) != 14 or digits == digits[0] * 14:
        return False
    return cnpj_digits(digits[:12]) == digits


def create_legal_entity(session: Session, principal: Principal, *, name: str, cnpj: str, fiscal_year: int) -> dict:
    digits = normalize_cnpj(cnpj)
    if not valid_cnpj(digits):
        raise DomainError(400, "CNPJ inválido", "Informe um CNPJ com dígitos verificadores válidos.")
    existing = session.scalar(
        select(LegalEntity).where(LegalEntity.tenant_id == principal.tenant_id, LegalEntity.cnpj == digits)
    )
    if existing is not None:
        raise DomainError(409, "CNPJ já cadastrado", "Este escritório já tem uma empresa com este CNPJ.")
    entity_id = new_id("le")
    entity = LegalEntity(
        id=entity_id,
        tenant_id=principal.tenant_id,
        name=name.strip(),
        cnpj=digits,
        currency="BRL",
    )
    session.add(entity)
    session.flush()
    establishment = Establishment(
        id=new_id("est"),
        tenant_id=principal.tenant_id,
        legal_entity_id=entity_id,
        name="Matriz",
    )
    session.add(establishment)
    chart_id = new_id("chart")
    add_starter_chart(
        session,
        tenant_id=principal.tenant_id,
        legal_entity_id=entity_id,
        chart_id=chart_id,
        chart_name=STARTER_CHART_NAME,
        account_id=lambda code: f"{entity_id}-{code}",
    )
    periods_created = add_open_year(
        session,
        tenant_id=principal.tenant_id,
        legal_entity_id=entity_id,
        year=fiscal_year,
        period_id=lambda year, month: f"{entity_id}-{year}-{month:02d}",
    )
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="legal_entity",
        target_ref=entity_id,
        metadata={"action": "legal_entity_created"},
    )
    payload = entity_dict(entity)
    payload["chart_id"] = chart_id
    payload["accounts_created"] = len(ACCOUNT_SPECS)
    payload["periods_created"] = periods_created
    return payload


def invite_user(
    session: Session,
    principal: Principal,
    directory: UserDirectory,
    *,
    username: str,
    display_name: str,
    email: str,
    roles: list[str],
    legal_entity_id: str | None = None,
) -> dict:
    if _USERNAME.fullmatch(username) is None:
        raise DomainError(
            400,
            "Nome de usuário inválido",
            "Use de 1 a 64 caracteres: letras, números, ponto, hífen ou sublinhado.",
        )
    if _EMAIL.fullmatch(email) is None or len(email) > 200:
        raise DomainError(400, "E-mail inválido", "Informe um e-mail para o convite.")
    chosen = list(dict.fromkeys(roles))
    if "client" in chosen:
        if chosen != ["client"]:
            raise DomainError(400, "Papel inválido", "O cliente da empresa não combina com papel do escritório.")
        if not legal_entity_id:
            raise DomainError(400, "Empresa obrigatória", "O cliente precisa estar ligado a uma empresa.")
    elif legal_entity_id:
        raise DomainError(400, "Empresa indevida", "Só o cliente da empresa fica ligado a uma empresa.")
    elif not chosen or any(role not in ROLES for role in chosen):
        raise DomainError(400, "Papel inválido", "Escolha ao menos um papel: preparer, approver, admin, viewer.")
    if any(role not in ROLES for role in chosen):
        raise DomainError(400, "Papel inválido", "Escolha ao menos um papel: preparer, approver, admin, viewer ou client.")
    visible_name = display_name.strip()
    if not visible_name or len(visible_name) > 200:
        raise DomainError(400, "Nome inválido", "Informe o nome de exibição.")
    if legal_entity_id:
        require_entity(session, principal.tenant_id, legal_entity_id)
    existing = session.scalar(
        select(Membership).where(Membership.tenant_id == principal.tenant_id, Membership.user_id == username)
    )
    if existing is not None:
        same_client = (
            chosen == ["client"]
            and list(existing.roles) == ["client"]
            and existing.legal_entity_id == legal_entity_id
        )
        if not same_client:
            raise DomainError(409, "Usuário já faz parte do escritório", "Este nome de usuário já tem acesso ao escritório.")
        directory.create_user(username, email, visible_name, principal.tenant_id)
        append_event(
            session,
            tenant_id=principal.tenant_id,
            event_type="other",
            actor_ref=principal.user_id,
            target_type="user",
            target_ref=username,
            metadata={"action": "client_login_completed", "roles": chosen},
        )
        user = session.get(AppUser, username)
        return {
            "user_id": username,
            "display_name": user.display_name if user is not None else visible_name,
            "roles": chosen,
        }
    directory.create_user(username, email, visible_name, principal.tenant_id)
    if session.get(AppUser, username) is None:
        session.add(AppUser(id=username, display_name=visible_name))
        session.flush()
    session.add(
        Membership(
            id=new_id("mem"),
            tenant_id=principal.tenant_id,
            user_id=username,
            roles=chosen,
            legal_entity_id=legal_entity_id,
        )
    )
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="user",
        target_ref=username,
        metadata={"action": "user_invited", "roles": chosen},
    )
    return {"user_id": username, "display_name": visible_name, "roles": chosen}


def list_users(session: Session, principal: Principal) -> dict:
    rows = session.execute(
        select(Membership, AppUser.display_name)
        .join(AppUser, AppUser.id == Membership.user_id)
        .where(Membership.tenant_id == principal.tenant_id)
        .order_by(AppUser.display_name, Membership.user_id)
    ).all()
    return {
        "items": [
            {
                "user_id": membership.user_id,
                "display_name": name,
                "roles": list(membership.roles),
                **({"legal_entity_id": membership.legal_entity_id} if membership.legal_entity_id else {}),
            }
            for membership, name in rows
        ]
    }


def entity_dict(entity: LegalEntity) -> dict:
    return {
        "legal_entity_id": entity.id,
        "name": entity.name,
        "cnpj": entity.cnpj,
        "currency": entity.currency,
    }


def decode_cursor(cursor: str) -> tuple[datetime, str]:
    try:
        raw = base64.urlsafe_b64decode(cursor.encode()).decode()
        stamp, row_id = raw.split("|", 1)
        return datetime.fromisoformat(stamp), row_id
    except (ValueError, UnicodeError) as exc:
        raise DomainError(400, "Cursor inválido", "O cursor de paginação não é válido.") from exc


def encode_cursor(moment: datetime, row_id: str) -> str:
    return base64.urlsafe_b64encode(f"{moment.isoformat()}|{row_id}".encode()).decode()


def page_limit(limit: int) -> int:
    if limit < 1 or limit > 100:
        raise DomainError(400, "Limite inválido", "O limite deve estar entre 1 e 100.")
    return limit


def before_cursor(column_time, column_id, cursor: str | None):
    if cursor is None:
        return None
    moment, row_id = decode_cursor(cursor)
    return tuple_(column_time, column_id) < tuple_(moment, row_id)
