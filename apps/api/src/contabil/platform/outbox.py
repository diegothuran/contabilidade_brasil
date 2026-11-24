from __future__ import annotations

from enum import Enum

from sqlalchemy.orm import Session

from contabil.platform.ids import new_id
from contabil.tables import OutboxEvent


class HandlerOutcome(Enum):
    """O que um handler do outbox pode devolver ao relay. `None` (o normal) conclui a operação."""

    # O handler fez uma parte e enfileirou a continuação; a operação segue `running`.
    CONTINUES = "continues"


def enqueue(session: Session, *, tenant_id: str, event_type: str, payload: dict) -> None:
    session.add(
        OutboxEvent(
            id=new_id("obx"),
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
        )
    )
