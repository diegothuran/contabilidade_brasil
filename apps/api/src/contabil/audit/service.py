from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contabil.audit.hash import canonical_payload, chain_hash
from contabil.platform.auth import format_utc
from contabil.platform.constants import SCHEMA_VERSION
from contabil.platform.ids import new_id
from contabil.tables import AuditEvent


def append_event(
    session: Session,
    *,
    tenant_id: str,
    event_type: str,
    actor_ref: str,
    target_type: str,
    target_ref: str,
    reason: str | None = None,
    metadata: dict | None = None,
    actor_kind: str = "user",
) -> AuditEvent:
    session.execute(text("SELECT pg_advisory_xact_lock(hashtext(:tenant_id))"), {"tenant_id": tenant_id})
    previous_row = session.execute(
        select(AuditEvent.event_hash, AuditEvent.occurred_at)
        .where(AuditEvent.tenant_id == tenant_id)
        .order_by(AuditEvent.occurred_at.desc())
        .limit(1)
    ).one_or_none()
    previous = previous_row[0] if previous_row else None
    occurred = datetime.now(timezone.utc)
    if previous_row is not None and occurred <= previous_row[1]:
        occurred = previous_row[1] + timedelta(microseconds=1)
    event_id = new_id("aud")
    occurred_text = format_utc(occurred)
    details = metadata or {}
    canonical = canonical_payload(
        schema_version=SCHEMA_VERSION,
        event_id=event_id,
        tenant_id=tenant_id,
        event_type=event_type,
        actor_kind=actor_kind,
        actor_ref=actor_ref,
        occurred_at=occurred_text,
        target_type=target_type,
        target_ref=target_ref,
        reason=reason,
        metadata=details,
    )
    event = AuditEvent(
        id=event_id,
        schema_version=SCHEMA_VERSION,
        tenant_id=tenant_id,
        event_type=event_type,
        actor_kind=actor_kind,
        actor_ref=actor_ref,
        occurred_at=occurred,
        target_type=target_type,
        target_ref=target_ref,
        reason=reason,
        details=details,
        event_hash=chain_hash(previous, canonical),
        previous_hash=previous,
    )
    session.add(event)
    session.flush()
    return event


def to_dict(event: AuditEvent) -> dict:
    return {
        "schema_version": event.schema_version,
        "event_id": event.id,
        "tenant_id": event.tenant_id,
        "event_type": event.event_type,
        "actor": {"kind": event.actor_kind, "ref": event.actor_ref},
        "occurred_at": format_utc(event.occurred_at),
        "target": {"type": event.target_type, "ref": event.target_ref},
        "reason": event.reason,
        "metadata": event.details or {},
        "integrity": {"event_hash": event.event_hash, "previous_hash": event.previous_hash},
    }


def verify_chain(session: Session, tenant_id: str) -> dict:
    events = session.scalars(
        select(AuditEvent).where(AuditEvent.tenant_id == tenant_id).order_by(AuditEvent.occurred_at.asc(), AuditEvent.id.asc())
    ).all()
    previous: str | None = None
    for index, event in enumerate(events, start=1):
        canonical = canonical_payload(
            schema_version=event.schema_version,
            event_id=event.id,
            tenant_id=event.tenant_id,
            event_type=event.event_type,
            actor_kind=event.actor_kind,
            actor_ref=event.actor_ref,
            occurred_at=format_utc(event.occurred_at),
            target_type=event.target_type,
            target_ref=event.target_ref,
            reason=event.reason,
            metadata=event.details or {},
        )
        expected = chain_hash(previous, canonical)
        if event.previous_hash != previous or event.event_hash != expected:
            return {"valid": False, "checked": index, "broken_event_id": event.id}
        previous = event.event_hash
    return {"valid": True, "checked": len(events), "broken_event_id": None}
