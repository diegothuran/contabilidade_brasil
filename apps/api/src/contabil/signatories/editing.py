"""Cadastro do registro profissional (CRC) e dos signatários da empresa (ADR 030).

A leitura que as demonstrações e a ECD usam fica em `service.signatories_for`.
Nenhuma função aqui consulta o CRC ou a Receita: o número e a certidão são declarados pelo usuário.
"""

from __future__ import annotations

from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import OFFICE_ROLES, Principal
from contabil.signatories.service import Signatories, registration_for, signatories_for
from contabil.signatories.validators import (
    CATEGORY_LABELS,
    CRC_CATEGORIES,
    LEGAL_REP_LABELS,
    LEGAL_REP_ROLES,
    UFS,
    cpf_digits,
    crc_label,
    formatted_cpf,
    masked_cpf,
    normalize_crc_number,
    valid_cpf,
    valid_crc_number,
)
from contabil.tables import AppUser, EntitySignatories, Membership, ProfessionalRegistration
from contabil.tenancy.service import require_entity


def _now() -> datetime:
    return datetime.now(timezone.utc)


def _registration_body(row: ProfessionalRegistration | None) -> dict | None:
    if row is None:
        return None
    return {
        "cpf": formatted_cpf(row.cpf),
        "crc_uf": row.crc_uf,
        "crc_number": row.crc_number,
        "crc_category": row.crc_category,
        "crc": crc_label(row.crc_uf, row.crc_number),
        "caption": f"{CATEGORY_LABELS.get(row.crc_category, row.crc_category)}, {crc_label(row.crc_uf, row.crc_number)}",
        "regularity_number": row.regularity_number,
        "regularity_valid_until": row.regularity_valid_until.isoformat() if row.regularity_valid_until else None,
        "updated_at": row.updated_at.isoformat() if row.updated_at else None,
    }


def my_registration(session: Session, principal: Principal) -> dict:
    return {
        "user_id": principal.user_id,
        "display_name": principal.display_name,
        "registration": _registration_body(registration_for(session, principal.tenant_id, principal.user_id)),
    }


def save_registration(
    session: Session,
    principal: Principal,
    *,
    cpf: str,
    crc_uf: str,
    crc_number: str,
    crc_category: str,
    regularity_number: str | None,
    regularity_valid_until: date | None,
) -> dict:
    digits = cpf_digits(cpf)
    if not valid_cpf(digits):
        raise DomainError(400, "CPF inválido", "Informe um CPF com dígitos verificadores válidos.")
    uf = (crc_uf or "").strip().upper()
    if uf not in UFS:
        raise DomainError(400, "UF inválida", "Informe a UF do conselho regional, como PE.")
    number = normalize_crc_number(crc_number)
    if not valid_crc_number(number):
        raise DomainError(400, "Número do CRC inválido", "Use o número como o CRC imprime, por exemplo 012345/O-8.")
    if crc_category not in CRC_CATEGORIES:
        raise DomainError(400, "Categoria inválida", "A categoria é contador ou técnico em contabilidade.")
    certificate = (regularity_number or "").strip() or None
    row = registration_for(session, principal.tenant_id, principal.user_id)
    if row is None:
        row = ProfessionalRegistration(id=new_id("preg"), tenant_id=principal.tenant_id, user_id=principal.user_id)
        session.add(row)
    row.cpf = digits
    row.crc_uf = uf
    row.crc_number = number
    row.crc_category = crc_category
    row.regularity_number = certificate
    row.regularity_valid_until = regularity_valid_until
    row.updated_at = _now()
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="user",
        target_ref=principal.user_id,
        # O CPF não entra na trilha (AGENTS.md: CPF desnecessário fica fora de log).
        metadata={"action": "professional_registration_updated", "crc_uf": uf, "crc_category": crc_category},
    )
    return my_registration(session, principal)


def summary(found: Signatories | None) -> dict | None:
    """O que a DRE e o Balanço imprimem: nome e legenda de cada signatário, sem CPF."""
    if found is None:
        return None
    accountant = found.accountant
    representative = found.legal_representative
    return {
        "accountant": {"name": accountant.name, "caption": accountant.caption} if accountant else None,
        "legal_representative": {"name": representative.name, "caption": representative.caption} if representative else None,
    }


def statement_signatories(session: Session, tenant_id: str, legal_entity_id: str) -> dict | None:
    return summary(signatories_for(session, tenant_id, legal_entity_id))


def _accountant_options(session: Session, tenant_id: str) -> list[dict]:
    rows = session.execute(
        select(ProfessionalRegistration, AppUser.display_name, Membership.roles)
        .join(AppUser, AppUser.id == ProfessionalRegistration.user_id)
        .join(
            Membership,
            (Membership.user_id == ProfessionalRegistration.user_id) & (Membership.tenant_id == ProfessionalRegistration.tenant_id),
        )
        .where(ProfessionalRegistration.tenant_id == tenant_id)
        .order_by(AppUser.display_name)
    ).all()
    options = []
    for registration, name, roles in rows:
        if OFFICE_ROLES.isdisjoint(roles or []) or "client" in (roles or []):
            continue
        options.append(
            {
                "user_id": registration.user_id,
                "display_name": name,
                "crc": crc_label(registration.crc_uf, registration.crc_number),
                "crc_category": registration.crc_category,
                "eligible": registration.crc_category == "contador",
                "regularity_valid_until": registration.regularity_valid_until.isoformat() if registration.regularity_valid_until else None,
            }
        )
    return options


def entity_signatories(session: Session, principal: Principal, legal_entity_id: str) -> dict:
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    admin = "admin" in principal.roles
    row = session.scalar(
        select(EntitySignatories).where(EntitySignatories.tenant_id == principal.tenant_id, EntitySignatories.legal_entity_id == entity.id)
    )
    found = signatories_for(session, principal.tenant_id, entity.id)
    accountant = found.accountant if found else None
    representative = found.legal_representative if found else None
    rep_cpf = representative.cpf if representative and representative.cpf else ""
    body: dict = {
        "legal_entity_id": entity.id,
        "accountant": (
            {
                "user_id": accountant.user_id,
                "name": accountant.name,
                "crc": accountant.crc,
                "caption": accountant.caption,
                "regularity_number": accountant.regularity_number,
                "regularity_valid_until": accountant.regularity_valid_until.isoformat() if accountant.regularity_valid_until else None,
            }
            if accountant
            else None
        ),
        "legal_representative": (
            {
                "name": representative.name,
                "cpf": (formatted_cpf(rep_cpf) if admin else masked_cpf(rep_cpf)) or None,
                "role": representative.role,
                "caption": representative.caption,
            }
            if representative
            else None
        ),
        "updated_at": row.updated_at.isoformat() if row is not None and row.updated_at else None,
    }
    if admin:
        body["accountant_options"] = _accountant_options(session, principal.tenant_id)
    return body


def save_entity_signatories(
    session: Session,
    principal: Principal,
    legal_entity_id: str,
    *,
    accountant_user_id: str | None,
    legal_rep_name: str | None,
    legal_rep_cpf: str | None,
    legal_rep_role: str | None,
) -> dict:
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    accountant_id = (accountant_user_id or "").strip() or None
    if accountant_id is not None:
        membership = session.scalar(
            select(Membership).where(Membership.tenant_id == principal.tenant_id, Membership.user_id == accountant_id)
        )
        if membership is None or "client" in membership.roles or OFFICE_ROLES.isdisjoint(membership.roles):
            raise DomainError(400, "Contador inválido", "O responsável técnico precisa ser alguém do escritório.")
        registration = registration_for(session, principal.tenant_id, accountant_id)
        if registration is None:
            raise DomainError(400, "Contador sem registro", "Essa pessoa ainda não cadastrou o CRC no perfil.")
        if registration.crc_category != "contador":
            raise DomainError(400, "Categoria do CRC", "O responsável técnico precisa ter registro de contador.")
    name = (legal_rep_name or "").strip() or None
    cpf = cpf_digits(legal_rep_cpf or "") or None
    role = (legal_rep_role or "").strip() or None
    if name is None and (cpf or role):
        raise DomainError(400, "Representante sem nome", "Informe o nome do representante legal.")
    if name is not None:
        if cpf is None or not valid_cpf(cpf):
            raise DomainError(400, "CPF inválido", "Informe o CPF do representante legal com dígitos verificadores válidos.")
        if role not in LEGAL_REP_ROLES:
            raise DomainError(400, "Cargo inválido", "Escolha o cargo: " + ", ".join(LEGAL_REP_LABELS.values()).lower() + ".")
    row = session.scalar(
        select(EntitySignatories).where(EntitySignatories.tenant_id == principal.tenant_id, EntitySignatories.legal_entity_id == entity.id)
    )
    if row is None:
        row = EntitySignatories(id=new_id("sig"), tenant_id=principal.tenant_id, legal_entity_id=entity.id)
        session.add(row)
    row.accountant_user_id = accountant_id
    row.legal_rep_name = name
    row.legal_rep_cpf = cpf
    row.legal_rep_role = role
    row.updated_by = principal.user_id
    row.updated_at = _now()
    session.flush()
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="legal_entity",
        target_ref=entity.id,
        metadata={
            "action": "entity_signatories_updated",
            "accountant_user_id": accountant_id,
            "legal_representative": name is not None,
        },
    )
    return entity_signatories(session, principal, entity.id)
