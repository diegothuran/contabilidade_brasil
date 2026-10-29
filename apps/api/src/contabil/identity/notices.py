from __future__ import annotations

import logging
from datetime import date, datetime, timedelta, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session
from sqlalchemy import select

from contabil.identity.directory import get_user_directory
from contabil.identity.mailer import UnavailableMailer, get_mailer, notice_text
from contabil.platform.auth import apply_tenant
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal
from contabil.platform.settings import get_settings
from contabil.tables import DocumentRequest, Membership, NotificationLog, Tenant

logger = logging.getLogger(__name__)


def client_preference(session: Session, principal: Principal) -> dict:
    row = _client_membership(session, principal)
    return {"notify_client": bool(row.notify_client)}


def set_client_preference(session: Session, principal: Principal, notify_client: bool) -> dict:
    row = _client_membership(session, principal)
    row.notify_client = notify_client
    session.flush()
    return {"notify_client": bool(row.notify_client)}


def _client_membership(session: Session, principal: Principal) -> Membership:
    from contabil.platform.principal import ensure_client

    ensure_client(principal)
    row = session.scalar(
        select(Membership).where(Membership.tenant_id == principal.tenant_id, Membership.user_id == principal.user_id)
    )
    if row is None:
        from contabil.platform.errors import DomainError

        raise DomainError(403, "Ação não permitida", "O acesso de cliente precisa estar ligado a uma empresa.")
    return row


def reminder_kind(due_on: date, today: date) -> str | None:
    if due_on == today + timedelta(days=3):
        return "due_soon"
    if due_on < today:
        return "overdue"
    return None


def enqueue_notice(session: Session, tenant_id: str, request_id: str, kind: str, notice_date: date) -> None:
    enqueue(
        session,
        tenant_id=tenant_id,
        event_type="DocumentRequestCreated" if kind == "created" else "DocumentRequestReturned",
        payload={"request_id": request_id, "kind": kind, "notice_date": notice_date.isoformat()},
    )


def deliver_notice(session: Session, tenant_id: str, payload: dict) -> None:
    request_id = str(payload.get("request_id") or "")
    kind = str(payload.get("kind") or "")
    raw_date = str(payload.get("notice_date") or "")
    if not request_id or not kind or not raw_date:
        return
    notice_date = date.fromisoformat(raw_date)
    row = session.scalar(
        select(DocumentRequest).where(DocumentRequest.id == request_id, DocumentRequest.tenant_id == tenant_id)
    )
    if row is None:
        return
    _send(session, row, kind, notice_date)


def sweep_reminders(session: Session, today: date) -> int:
    sent = 0
    tenant_ids = list(session.scalars(select(Tenant.id)).all())
    for tenant_id in tenant_ids:
        apply_tenant(session, tenant_id)
        rows = session.scalars(
            select(DocumentRequest).where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.status.in_(("open", "received")),
            )
        ).all()
        for row in rows:
            kind = reminder_kind(row.due_on, today)
            if kind is not None and _send(session, row, kind, row.due_on):
                sent += 1
    return sent


def _send(session: Session, row: DocumentRequest, kind: str, notice_date: date) -> bool:
    mailer = get_mailer()
    if isinstance(mailer, UnavailableMailer):
        logger.info("notice skipped kind=%s request=%s reason=mail_off", kind, row.id)
        return False
    if session.scalar(
        select(NotificationLog.id).where(
            NotificationLog.request_id == row.id,
            NotificationLog.kind == kind,
            NotificationLog.notice_date == notice_date,
        )
    ):
        return False
    members = session.scalars(
        select(Membership).where(
            Membership.tenant_id == row.tenant_id,
            Membership.legal_entity_id == row.legal_entity_id,
            Membership.notify_client.is_(True),
        )
    ).all()
    directory = get_user_directory()
    subject, body = notice_text(row.title, row.due_on.isoformat(), get_settings().portal_base_url)
    delivered = False
    for member in members:
        if "client" not in set(member.roles or []):
            continue
        recipient = directory.get_email(member.user_id)
        if not recipient:
            continue
        if mailer.send(recipient, subject, body):
            delivered = True
    if not delivered:
        logger.info("notice skipped kind=%s request=%s", kind, row.id)
        return False
    try:
        with session.begin_nested():
            session.add(
                NotificationLog(
                    id=new_id("note"),
                    tenant_id=row.tenant_id,
                    request_id=row.id,
                    kind=kind,
                    notice_date=notice_date,
                    created_at=datetime.now(timezone.utc),
                )
            )
            session.flush()
    except IntegrityError:
        return False
    return True
