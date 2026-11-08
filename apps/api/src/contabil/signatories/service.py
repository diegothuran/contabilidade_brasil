"""Leitura dos signatários de uma empresa: o contador responsável e o representante legal (ADR 030).

`signatories_for` é o contrato que as demonstrações e a prévia da ECD (J930) usam.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.signatories.validators import CATEGORY_LABELS, LEGAL_REP_LABELS, crc_label
from contabil.tables import AppUser, EntitySignatories, ProfessionalRegistration


@dataclass(frozen=True)
class Accountant:
    user_id: str
    name: str
    cpf: str
    crc_uf: str
    crc_number: str
    crc_category: str
    regularity_number: str | None
    regularity_valid_until: date | None

    @property
    def crc(self) -> str:
        return crc_label(self.crc_uf, self.crc_number)

    @property
    def caption(self) -> str:
        return f"{CATEGORY_LABELS.get(self.crc_category, self.crc_category)}, {self.crc}"


@dataclass(frozen=True)
class LegalRepresentative:
    name: str
    cpf: str | None
    role: str | None

    @property
    def caption(self) -> str:
        return LEGAL_REP_LABELS.get(self.role or "", "Representante legal")


@dataclass(frozen=True)
class Signatories:
    accountant: Accountant | None
    legal_representative: LegalRepresentative | None


def registration_for(session: Session, tenant_id: str, user_id: str) -> ProfessionalRegistration | None:
    return session.scalar(
        select(ProfessionalRegistration).where(
            ProfessionalRegistration.tenant_id == tenant_id, ProfessionalRegistration.user_id == user_id
        )
    )


def signatories_for(session: Session, tenant_id: str, legal_entity_id: str) -> Signatories | None:
    """Signatários cadastrados, ou None quando a empresa ainda não tem nenhum."""
    row = session.scalar(
        select(EntitySignatories).where(
            EntitySignatories.tenant_id == tenant_id, EntitySignatories.legal_entity_id == legal_entity_id
        )
    )
    if row is None:
        return None
    accountant = None
    if row.accountant_user_id:
        registration = registration_for(session, tenant_id, row.accountant_user_id)
        user = session.get(AppUser, row.accountant_user_id)
        if registration is not None and user is not None:
            accountant = Accountant(
                user_id=user.id,
                name=user.display_name,
                cpf=registration.cpf,
                crc_uf=registration.crc_uf,
                crc_number=registration.crc_number,
                crc_category=registration.crc_category,
                regularity_number=registration.regularity_number,
                regularity_valid_until=registration.regularity_valid_until,
            )
    representative = None
    if row.legal_rep_name:
        representative = LegalRepresentative(name=row.legal_rep_name, cpf=row.legal_rep_cpf, role=row.legal_rep_role)
    if accountant is None and representative is None:
        return None
    return Signatories(accountant=accountant, legal_representative=representative)
