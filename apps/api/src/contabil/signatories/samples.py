"""Signatários fictícios do seed local e das amostras do piloto (ADR 030).

O CRC e o CPF são inventados; o CPF tem dígitos verificadores calculados (`seed.cpf`).
Nada é sobrescrito: se o cadastro já existe, a amostra não mexe nele.
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.platform.principal import Principal
from contabil.signatories.editing import save_entity_signatories, save_registration
from contabil.signatories.service import registration_for
from contabil.tables import EntitySignatories


def ensure_registration(session: Session, principal: Principal, *, cpf: str, crc_number: str, category: str, uf: str = "PE") -> None:
    if registration_for(session, principal.tenant_id, principal.user_id) is not None:
        return
    save_registration(
        session,
        principal,
        cpf=cpf,
        crc_uf=uf,
        crc_number=crc_number,
        crc_category=category,
        regularity_number=None,
        regularity_valid_until=None,
    )


def ensure_entity_signatories(
    session: Session,
    principal: Principal,
    legal_entity_id: str,
    *,
    accountant_user_id: str,
    legal_rep_name: str,
    legal_rep_cpf: str,
    legal_rep_role: str = "socio_administrador",
) -> None:
    existing = session.scalar(
        select(EntitySignatories.id).where(
            EntitySignatories.tenant_id == principal.tenant_id, EntitySignatories.legal_entity_id == legal_entity_id
        )
    )
    if existing is not None:
        return
    save_entity_signatories(
        session,
        principal,
        legal_entity_id,
        accountant_user_id=accountant_user_id,
        legal_rep_name=legal_rep_name,
        legal_rep_cpf=legal_rep_cpf,
        legal_rep_role=legal_rep_role,
    )
