from __future__ import annotations

import logging
import signal
import threading
import time
from datetime import datetime, timezone

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from contabil.audit.service import verify_chain
from contabil.imports.service import publish_batch, validate_batch
from contabil.exports.service import run_operational_export
from contabil.identity.notices import deliver_notice, sweep_reminders
from contabil.reconciliation.service import import_statement, resolve_case_from_journal
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.tables import Operation, Tenant

logger = logging.getLogger("contabil.worker")
_MAX_ATTEMPTS = 3

HANDLERS = {
    "ImportBatchReceived": validate_batch,
    "ImportBatchPublishRequested": publish_batch,
    "BankStatementReceived": import_statement,
    "JournalPublished": resolve_case_from_journal,
    "OperationalExportRequested": run_operational_export,
    "DocumentRequestCreated": deliver_notice,
    "DocumentRequestReturned": deliver_notice,
}


def _payload(value) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        import json

        try:
            parsed = json.loads(value)
        except json.JSONDecodeError:
            return {}
        return parsed if isinstance(parsed, dict) else {}
    return {}


def _complete_operation(session: Session, tenant_id: str, operation_id: str | None) -> None:
    if not operation_id:
        return
    operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == tenant_id))
    if operation is not None and operation.status in {"accepted", "running"}:
        operation.status = "completed"
        operation.updated_at = datetime.now(timezone.utc)


def _fail_operation(session: Session, tenant_id: str, operation_id: str | None) -> None:
    if not operation_id:
        return
    operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == tenant_id))
    if operation is not None and operation.status != "completed":
        operation.status = "failed"
        operation.error_code = "handler_failed"
        operation.updated_at = datetime.now(timezone.utc)


def relay_once(session: Session) -> int:
    rows = session.execute(
        text(
            """
            SELECT id, tenant_id, event_type, payload, attempts
            FROM outbox_events
            WHERE dispatched_at IS NULL AND dead_at IS NULL
            ORDER BY created_at
            FOR UPDATE SKIP LOCKED
            LIMIT 20
            """
        )
    ).mappings().all()
    if not rows:
        return 0
    dispatched = 0
    for row in rows:
        handler = HANDLERS.get(row["event_type"])
        if handler is None:
            logger.info("outbox dispatched type=%s tenant=%s id=%s", row["event_type"], row["tenant_id"], row["id"])
            session.execute(text("UPDATE outbox_events SET dispatched_at = now() WHERE id = :id"), {"id": row["id"]})
            dispatched += 1
            continue
        payload = _payload(row["payload"])
        apply_tenant(session, row["tenant_id"])
        try:
            with session.begin_nested():
                handler(session, row["tenant_id"], payload)
                _complete_operation(session, row["tenant_id"], payload.get("operation_id"))
            session.execute(text("UPDATE outbox_events SET dispatched_at = now() WHERE id = :id"), {"id": row["id"]})
            dispatched += 1
            logger.info("outbox dispatched type=%s tenant=%s id=%s", row["event_type"], row["tenant_id"], row["id"])
        except Exception as exc:
            attempts = int(row["attempts"] or 0) + 1
            message = exc.__class__.__name__[:500]
            if attempts >= _MAX_ATTEMPTS:
                session.execute(
                    text(
                        """
                        UPDATE outbox_events
                        SET attempts = :attempts, last_error = :error, dead_at = now()
                        WHERE id = :id
                        """
                    ),
                    {"id": row["id"], "attempts": attempts, "error": message},
                )
                _fail_operation(session, row["tenant_id"], payload.get("operation_id"))
            else:
                session.execute(
                    text("UPDATE outbox_events SET attempts = :attempts, last_error = :error WHERE id = :id"),
                    {"id": row["id"], "attempts": attempts, "error": message},
                )
            logger.warning(
                "outbox handler failed type=%s tenant=%s id=%s attempts=%s error=%s",
                row["event_type"],
                row["tenant_id"],
                row["id"],
                attempts,
                exc.__class__.__name__,
            )
    return dispatched


def verify_tenants(session: Session) -> None:
    tenant_ids = session.scalars(select(Tenant.id)).all()
    for tenant_id in tenant_ids:
        apply_tenant(session, tenant_id)
        result = verify_chain(session, tenant_id)
        if not result["valid"]:
            logger.error("audit chain broken tenant=%s event=%s", tenant_id, result["broken_event_id"])


def run_loop(stop: threading.Event) -> None:
    last_verify = 0.0
    last_remind = 0.0
    while not stop.is_set():
        session = session_factory(admin=True)()
        count = 0
        try:
            count = relay_once(session)
            now = time.time()
            if now - last_remind > 3600:
                sweep_reminders(session, datetime.now(timezone.utc).date())
                last_remind = now
            if now - last_verify > 30:
                verify_tenants(session)
                last_verify = now
            session.commit()
        except Exception:
            session.rollback()
            logger.exception("worker cycle failed")
            count = 0
        finally:
            session.close()
        if count == 0 and not stop.is_set():
            stop.wait(1)


def main() -> None:
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
    stop = threading.Event()

    def _handle_stop(signum, frame) -> None:
        del signum, frame
        stop.set()

    signal.signal(signal.SIGTERM, _handle_stop)
    signal.signal(signal.SIGINT, _handle_stop)
    run_loop(stop)


if __name__ == "__main__":
    main()
