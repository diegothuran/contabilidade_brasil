"""Cadastro da escrituração da ECD por empresa (ADR 031).

Guarda o que o razão não sabe e o 0000 e o I030 pedem: UF e município da sede, onde o livro é
registrado (Junta Comercial com NIRE, ou cartório de pessoas jurídicas sem NIRE), a data do
arquivamento dos atos constitutivos, a situação especial e o número de ordem do livro.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.platform.auth import format_utc
from contabil.platform.clock import brasilia_today
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.principal import Principal, ensure_office, ensure_role
from contabil.regulatory.registry import layouts, uf_codes
from contabil.tables import EcdRegistration
from contabil.tenancy.service import require_entity

REGISTRY_KINDS = ("junta", "cartorio")
_MUNICIPALITY = re.compile(r"^[0-9]{7}$")
_NIRE = re.compile(r"^[0-9]{11}$")


@dataclass(frozen=True)
class RegistrationInput:
    uf: str
    municipality_ibge: str
    registry_kind: str
    nire: str | None
    registry_date: date | None
    special_situation: str | None
    book_number: int


def _digits(value: str | None) -> str:
    return re.sub(r"\D", "", value or "")


def _special_situations() -> dict[str, str]:
    known = layouts("ecd")
    return known[-1].codes.get("IND_SIT_ESP", {}) if known else {}


def validate_registration(data: RegistrationInput, today: date | None = None) -> RegistrationInput:
    """Normaliza e confere o cadastro. Junta a lista de erros numa resposta só."""
    errors: list[dict] = []
    uf = (data.uf or "").strip().upper()
    codes = uf_codes()
    if uf not in codes:
        errors.append({"loc": ["uf"], "msg": "UF desconhecida."})
    municipality = _digits(data.municipality_ibge)
    if not _MUNICIPALITY.match(municipality):
        errors.append({"loc": ["municipality_ibge"], "msg": "O código IBGE do município tem 7 dígitos."})
    elif uf in codes and not municipality.startswith(codes[uf]):
        errors.append({"loc": ["municipality_ibge"], "msg": f"O município não é da UF {uf}: o código deveria começar com {codes[uf]}."})
    kind = (data.registry_kind or "").strip()
    nire = _digits(data.nire) or None
    if kind not in REGISTRY_KINDS:
        errors.append({"loc": ["registry_kind"], "msg": "Use junta (Junta Comercial) ou cartorio (cartório de pessoas jurídicas)."})
    elif kind == "junta":
        if nire is None:
            errors.append({"loc": ["nire"], "msg": "Empresa registrada na Junta Comercial precisa do NIRE."})
        elif not _NIRE.match(nire):
            errors.append({"loc": ["nire"], "msg": "O NIRE tem 11 dígitos."})
        elif uf in codes and not nire.startswith(codes[uf]):
            errors.append({"loc": ["nire"], "msg": f"O NIRE não é da Junta da UF {uf}: deveria começar com {codes[uf]}."})
    elif nire is not None:
        errors.append({"loc": ["nire"], "msg": "Sociedade registrada em cartório não tem NIRE. Deixe o campo vazio."})
    reference = today or brasilia_today()
    if data.registry_date is not None and data.registry_date > reference:
        errors.append({"loc": ["registry_date"], "msg": "A data do arquivamento não pode ser futura."})
    special = (data.special_situation or "").strip() or None
    if special is not None and special not in _special_situations():
        errors.append({"loc": ["special_situation"], "msg": "Situação especial fora da tabela do leiaute."})
    if not isinstance(data.book_number, int) or data.book_number < 1:
        errors.append({"loc": ["book_number"], "msg": "O número do livro começa em 1."})
    if errors:
        raise DomainError(400, "Cadastro da escrituração inválido", "Confira os campos destacados.", errors=errors)
    return RegistrationInput(
        uf=uf,
        municipality_ibge=municipality,
        registry_kind=kind,
        nire=nire if kind == "junta" else None,
        registry_date=data.registry_date,
        special_situation=special,
        book_number=data.book_number,
    )


def registration_row(session: Session, tenant_id: str, legal_entity_id: str) -> EcdRegistration | None:
    return session.scalar(
        select(EcdRegistration).where(EcdRegistration.tenant_id == tenant_id, EcdRegistration.legal_entity_id == legal_entity_id)
    )


def registration_dict(legal_entity_id: str, row: EcdRegistration | None) -> dict:
    if row is None:
        return {
            "legal_entity_id": legal_entity_id,
            "configured": False,
            "uf": None,
            "municipality_ibge": None,
            "registry_kind": None,
            "nire": None,
            "registry_date": None,
            "special_situation": None,
            "book_number": None,
            "updated_at": None,
        }
    return {
        "legal_entity_id": legal_entity_id,
        "configured": True,
        "uf": row.uf,
        "municipality_ibge": row.municipality_ibge,
        "registry_kind": row.registry_kind,
        "nire": row.nire,
        "registry_date": row.registry_date.isoformat() if row.registry_date else None,
        "special_situation": row.special_situation,
        "book_number": row.book_number,
        "updated_at": format_utc(row.updated_at) if row.updated_at else None,
    }


def get_registration(session: Session, principal: Principal, legal_entity_id: str) -> dict:
    ensure_office(principal)
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    return registration_dict(entity.id, registration_row(session, principal.tenant_id, entity.id))


def save_registration(session: Session, tenant_id: str, legal_entity_id: str, actor: str, data: RegistrationInput) -> EcdRegistration:
    """Grava o cadastro já validado e registra a auditoria. A rota confere o papel antes."""
    clean = validate_registration(data)
    row = registration_row(session, tenant_id, legal_entity_id)
    now = datetime.now(timezone.utc)
    created = row is None
    if row is None:
        row = EcdRegistration(id=new_id("ecdreg"), tenant_id=tenant_id, legal_entity_id=legal_entity_id)
        session.add(row)
    row.uf = clean.uf
    row.municipality_ibge = clean.municipality_ibge
    row.registry_kind = clean.registry_kind
    row.nire = clean.nire
    row.registry_date = clean.registry_date
    row.special_situation = clean.special_situation
    row.book_number = clean.book_number
    row.updated_by = actor
    row.updated_at = now
    session.flush()
    append_event(
        session,
        tenant_id=tenant_id,
        event_type="other",
        actor_ref=actor,
        target_type="ecd_registration",
        target_ref=legal_entity_id,
        metadata={
            "action": "ecd_registration_created" if created else "ecd_registration_updated",
            "uf": clean.uf,
            "municipality_ibge": clean.municipality_ibge,
            "registry_kind": clean.registry_kind,
            "book_number": clean.book_number,
        },
    )
    return row


def put_registration(session: Session, principal: Principal, legal_entity_id: str, data: RegistrationInput) -> dict:
    ensure_office(principal)
    ensure_role(principal, "admin")
    entity = require_entity(session, principal.tenant_id, legal_entity_id)
    row = save_registration(session, principal.tenant_id, entity.id, principal.user_id, data)
    return registration_dict(entity.id, row)
