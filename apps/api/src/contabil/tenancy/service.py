from __future__ import annotations

import base64
from datetime import datetime

from sqlalchemy import select, tuple_
from sqlalchemy.orm import Session

from contabil.platform.errors import DomainError
from contabil.tables import LegalEntity


def require_entity(session: Session, tenant_id: str, legal_entity_id: str) -> LegalEntity:
    entity = session.scalar(select(LegalEntity).where(LegalEntity.id == legal_entity_id, LegalEntity.tenant_id == tenant_id))
    if entity is None:
        raise DomainError(404, "Não encontrado", "Empresa não encontrada.")
    return entity


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
