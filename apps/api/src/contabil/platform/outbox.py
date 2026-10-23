from __future__ import annotations

from sqlalchemy.orm import Session

from contabil.platform.ids import new_id
from contabil.tables import OutboxEvent


def enqueue(session: Session, *, tenant_id: str, event_type: str, payload: dict) -> None:
    session.add(
        OutboxEvent(
            id=new_id("obx"),
            tenant_id=tenant_id,
            event_type=event_type,
            payload=payload,
        )
    )
