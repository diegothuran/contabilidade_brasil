from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone
from statistics import median

from sqlalchemy import any_, literal, select

from contabil.platform.auth import apply_tenant, format_utc
from contabil.platform.db import session_factory
from contabil.tables import AccountingPeriod, AuditEvent, DocumentRequest, LegalEntity, Membership

# Brasília não tem horário de verão desde 2019; o prazo é lido nesse fuso.
_BRASILIA = timezone(timedelta(hours=-3))
_ACTIONS = {
    "document_request_opened": "opened_at",
    "document_request_received": "received_at",
    "document_request_confirmed": "closed_at",
    "document_request_cancelled": "closed_at",
}
COLUMNS = (
    "empresa",
    "pedido",
    "competencia",
    "prazo",
    "estado",
    "aberto_em",
    "recebido_em",
    "enviado_por",
    "encerrado_em",
    "dias_ate_receber",
    "dias_ate_confirmar",
    "no_prazo",
)


@dataclass(frozen=True)
class _Request:
    id: str
    title: str
    due_on: date
    status: str
    received_by: str | None
    company: str
    period: str


def _days(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 86400, 1)


def request_cycles(requests, events, client_users: set[str], today: date) -> list[dict]:
    moments: dict[str, dict[str, datetime]] = {}
    for event in sorted(events, key=lambda item: item.occurred_at):
        field = _ACTIONS.get((event.details or {}).get("action"))
        if field is not None:
            moments.setdefault(event.target_ref, {}).setdefault(field, event.occurred_at)
    cycles = []
    for request in requests:
        seen = moments.get(request.id, {})
        opened = seen.get("opened_at")
        received = seen.get("received_at")
        closed = seen.get("closed_at")
        if received is not None:
            on_time: bool | None = received.astimezone(_BRASILIA).date() <= request.due_on
        elif request.status == "open":
            on_time = False if today > request.due_on else None
        else:
            on_time = None
        if request.received_by is None:
            sent_by = None
        else:
            sent_by = "cliente" if request.received_by in client_users else "escritorio"
        cycles.append(
            {
                "empresa": request.company,
                "pedido": request.title,
                "competencia": request.period,
                "prazo": request.due_on,
                "estado": request.status,
                "aberto_em": opened,
                "recebido_em": received,
                "enviado_por": sent_by,
                "encerrado_em": closed,
                "dias_ate_receber": _days(opened, received),
                "dias_ate_confirmar": _days(received, closed) if request.status == "confirmed" else None,
                "no_prazo": on_time,
            }
        )
    return cycles


def summarize(cycles: list[dict]) -> dict:
    received = [item for item in cycles if item["recebido_em"] is not None]
    to_receive = [item["dias_ate_receber"] for item in received if item["dias_ate_receber"] is not None]
    to_confirm = [item["dias_ate_confirmar"] for item in cycles if item["dias_ate_confirmar"] is not None]
    return {
        "pedidos": len(cycles),
        "enviados_pelo_cliente": sum(1 for item in received if item["enviado_por"] == "cliente"),
        "recebidos_no_prazo": f"{sum(1 for item in received if item['no_prazo'])}/{len(received)}",
        "mediana_dias_ate_receber": median(to_receive) if to_receive else None,
        "mediana_dias_ate_confirmar": median(to_confirm) if to_confirm else None,
        "abertos": sum(1 for item in cycles if item["estado"] in {"open", "received"}),
        "abertos_vencidos": sum(1 for item in cycles if item["estado"] == "open" and item["no_prazo"] is False),
    }


def _cell(value) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "sim" if value else "nao"
    if isinstance(value, datetime):
        return format_utc(value)
    if isinstance(value, date):
        return value.isoformat()
    return str(value).replace(";", ",")


def load_cycles(tenant_id: str, since: date | None = None) -> list[dict]:
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant_id)
        stmt = (
            select(DocumentRequest, LegalEntity.name, AccountingPeriod.fiscal_year, AccountingPeriod.month)
            .join(LegalEntity, LegalEntity.id == DocumentRequest.legal_entity_id)
            .join(AccountingPeriod, AccountingPeriod.id == DocumentRequest.period_id)
            .where(DocumentRequest.tenant_id == tenant_id)
            .order_by(LegalEntity.name, DocumentRequest.due_on, DocumentRequest.id)
        )
        if since is not None:
            stmt = stmt.where(DocumentRequest.created_at >= datetime.combine(since, datetime.min.time(), _BRASILIA))
        rows = session.execute(stmt).all()
        requests = [
            _Request(row.id, row.title, row.due_on, row.status, row.received_by, name, f"{month:02d}/{year}")
            for row, name, year, month in rows
        ]
        events = session.scalars(
            select(AuditEvent).where(
                AuditEvent.tenant_id == tenant_id,
                AuditEvent.target_type == "document_request",
                AuditEvent.target_ref.in_([item.id for item in requests]),
            )
        ).all()
        clients = set(
            session.scalars(
                select(Membership.user_id).where(Membership.tenant_id == tenant_id, literal("client") == any_(Membership.roles))
            ).all()
        )
        return request_cycles(requests, events, clients, datetime.now(_BRASILIA).date())
    finally:
        session.close()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Mostra o ciclo de cada pedido de documento do escritório.")
    parser.add_argument("--tenant-id", required=True)
    parser.add_argument("--since", type=date.fromisoformat, default=None, help="AAAA-MM-DD; pedidos abertos a partir dessa data.")
    args = parser.parse_args(argv)
    cycles = load_cycles(args.tenant_id, args.since)
    print(";".join(COLUMNS))
    for item in cycles:
        print(";".join(_cell(item[column]) for column in COLUMNS))
    for key, value in summarize(cycles).items():
        print(f"resumo {key}={_cell(value)}")


if __name__ == "__main__":
    main(sys.argv[1:])
