"""Handler do outbox para `CounterpartSuggestionRequested` (ADR 035).

O mapeamento ref → caso fica só na memória deste handler. O log leva ids, contagens e
stop_reason; nunca prompt, resposta, descrição ou nome.
"""
from __future__ import annotations

import logging
from datetime import datetime, time, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from contabil.imports.service import mark_operation_running
from contabil.platform.clock import BRASILIA, brasilia_today
from contabil.platform.ids import new_id
from contabil.platform.outbox import HandlerOutcome, enqueue
from contabil.platform.settings import get_settings
from contabil.suggestions.history import history_suggestions
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.suggestions.model import (
    BATCH_SIZE,
    INCOMPLETE_STOPS,
    PROMPT_VERSION,
    AnthropicModelClient,
    ModelClient,
    build_prompt,
    validate_picks,
)
from contabil.tables import (
    Account,
    AccountingPeriod,
    AccountSuggestion,
    BankAccount,
    BankTransaction,
    Operation,
    ReconciliationCase,
    SuggestionRun,
)

logger = logging.getLogger("contabil.suggestions")

PENDING_STATUSES = frozenset({"open", "suggested", "reversed"})
# Operação concluída com aviso (operations.error_code), mostrado na tela.
LIMIT_WARNING = "limite_diario"
EVENT_TYPE = "CounterpartSuggestionRequested"
INCOMPLETE_WARNING = "resposta_incompleta"


def used_today(session: Session, tenant_id: str, now: datetime | None = None) -> int:
    """Transações reservadas para o modelo pelo escritório desde 00:00 de Brasília."""
    start = datetime.combine(brasilia_today(now), time.min, tzinfo=BRASILIA).astimezone(timezone.utc)
    total = session.scalar(
        select(func.coalesce(func.sum(SuggestionRun.transactions_sent), 0)).where(
            SuggestionRun.tenant_id == tenant_id,
            SuggestionRun.created_at >= start,
        )
    )
    return int(total or 0)


def pending_cases(
    session: Session,
    tenant_id: str,
    bank: BankAccount,
    period: AccountingPeriod,
) -> list[tuple[ReconciliationCase, BankTransaction]]:
    """Casos pendentes da conta na competência que o histórico não resolve com confiança alta."""
    rows = session.execute(
        select(ReconciliationCase, BankTransaction)
        .join(BankTransaction, BankTransaction.id == ReconciliationCase.transaction_id)
        .where(
            ReconciliationCase.tenant_id == tenant_id,
            ReconciliationCase.bank_account_id == bank.id,
            ReconciliationCase.status.in_(PENDING_STATUSES),
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.transaction_date >= period.start_date,
            BankTransaction.transaction_date <= period.end_date,
        )
        .order_by(BankTransaction.transaction_date, ReconciliationCase.id)
    ).all()
    pending: list[tuple[ReconciliationCase, BankTransaction]] = []
    for case, transaction in rows:
        history = history_suggestions(session, tenant_id, case, transaction, bank)
        if any(item.confidence == "alta" for item in history):
            continue
        pending.append((case, transaction))
    return pending


def scope_of(session: Session, tenant_id: str, bank_account_id: str, period_id: str, legal_entity_id: str | None = None):
    bank = session.scalar(select(BankAccount).where(BankAccount.id == bank_account_id, BankAccount.tenant_id == tenant_id))
    if bank is None or (legal_entity_id is not None and bank.legal_entity_id != legal_entity_id):
        return None, None
    period = session.scalar(
        select(AccountingPeriod).where(AccountingPeriod.id == period_id, AccountingPeriod.tenant_id == tenant_id)
    )
    if period is None or period.legal_entity_id != bank.legal_entity_id:
        return bank, None
    return bank, period


def _autonomous(tenant_id: str, rows: list) -> None:
    """Grava numa transação própria, que sobrevive ao rollback do handler (custo e teto garantidos)."""
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant_id)
        session.add_all(rows)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _run(
    tenant_id: str,
    operation_id: str,
    model: str,
    sent: int,
    stop_reason: str,
    input_tokens: int = 0,
    output_tokens: int = 0,
) -> SuggestionRun:
    return SuggestionRun(
        id=new_id("sgrun"),
        tenant_id=tenant_id,
        operation_id=operation_id,
        model=model[:80],
        prompt_version=PROMPT_VERSION,
        transactions_sent=sent,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        stop_reason=(stop_reason or "unknown")[:40],
        created_at=datetime.now(timezone.utc),
    )


def _cursor_key(case: ReconciliationCase, transaction: BankTransaction) -> tuple[str, str]:
    # Ordem própria do handler (data ISO, id do caso), comparada em Python e não pela collation do banco.
    return (transaction.transaction_date.isoformat(), case.id)


def _cursor_of(payload: dict) -> tuple[str, str] | None:
    cursor = payload.get("cursor")
    if not isinstance(cursor, dict) or not cursor.get("date") or not cursor.get("case_id"):
        return None
    return (str(cursor["date"]), str(cursor["case_id"]))


def _warn(session: Session, tenant_id: str, operation_id: str, warning: str) -> None:
    """O limite diário prevalece; `resposta_incompleta` não apaga um aviso já gravado."""
    operation = session.scalar(select(Operation).where(Operation.id == operation_id, Operation.tenant_id == tenant_id))
    if operation is None:
        return
    if warning == LIMIT_WARNING or operation.error_code is None:
        operation.error_code = warning
        operation.updated_at = datetime.now(timezone.utc)


def run_counterpart_suggestions(
    session: Session,
    tenant_id: str,
    payload: dict,
    client: ModelClient | None = None,
) -> HandlerOutcome | None:
    """Um lote por despacho (ADR 035).

    A chamada ao modelo roda dentro da transação do relay; com um lote só, o relay não fica preso
    por minutos. Se restarem casos e o teto deixar, enfileira a continuação com o mesmo
    `operation_id` e um cursor, e devolve `HandlerOutcome.CONTINUES` para a operação seguir `running`.
    """
    operation_id = payload.get("operation_id")
    mark_operation_running(session, tenant_id, operation_id)
    bank, period = scope_of(
        session,
        tenant_id,
        str(payload.get("bank_account_id") or ""),
        str(payload.get("period_id") or ""),
        payload.get("legal_entity_id"),
    )
    if bank is None or period is None or not operation_id:
        logger.info("counterpart suggestions skipped tenant=%s operation=%s reason=scope", tenant_id, operation_id)
        return None
    cursor = _cursor_of(payload)
    ordered = sorted(pending_cases(session, tenant_id, bank, period), key=lambda item: _cursor_key(*item))
    if cursor is not None:
        ordered = [item for item in ordered if _cursor_key(*item) > cursor]
    if not ordered:
        logger.info("counterpart suggestions nothing to send tenant=%s operation=%s", tenant_id, operation_id)
        return None
    # A janela do despacho é fixada antes de tirar os casos já sugeridos: a reentrega do mesmo
    # despacho cai na mesma janela, não paga de novo e não invade o lote seguinte.
    window = ordered[:BATCH_SIZE]
    rest = ordered[BATCH_SIZE:]
    done = set(
        session.scalars(
            select(AccountSuggestion.case_id).where(
                AccountSuggestion.tenant_id == tenant_id,
                AccountSuggestion.operation_id == operation_id,
            )
        ).all()
    )
    settings = get_settings()
    to_send = [item for item in window if item[0].id not in done]
    capacity = settings.suggestion_daily_limit - used_today(session, tenant_id)
    if to_send and capacity <= 0:
        logger.info(
            "counterpart suggestions daily limit tenant=%s operation=%s pending=%s",
            tenant_id,
            operation_id,
            len(to_send) + len(rest),
        )
        _warn(session, tenant_id, operation_id, LIMIT_WARNING)
        return None
    # Manda o que couber no teto; o que sobrar fica para outro pedido, com aviso.
    trimmed = len(to_send) > capacity
    batch = to_send[:capacity] if trimmed else to_send
    if batch:
        _send_batch(session, tenant_id, operation_id, bank, batch, settings, client)
    if trimmed:
        logger.info(
            "counterpart suggestions daily limit tenant=%s operation=%s pending=%s",
            tenant_id,
            operation_id,
            len(to_send) - len(batch) + len(rest),
        )
        _warn(session, tenant_id, operation_id, LIMIT_WARNING)
        return None
    if not rest:
        return None
    if used_today(session, tenant_id) >= settings.suggestion_daily_limit:
        logger.info(
            "counterpart suggestions daily limit tenant=%s operation=%s pending=%s",
            tenant_id,
            operation_id,
            len(rest),
        )
        _warn(session, tenant_id, operation_id, LIMIT_WARNING)
        return None
    last_case, last_transaction = window[-1]
    date_key, case_key = _cursor_key(last_case, last_transaction)
    enqueue(
        session,
        tenant_id=tenant_id,
        event_type=EVENT_TYPE,
        payload={
            "bank_account_id": bank.id,
            "period_id": period.id,
            "operation_id": operation_id,
            "legal_entity_id": bank.legal_entity_id,
            "cursor": {"date": date_key, "case_id": case_key},
        },
    )
    return HandlerOutcome.CONTINUES


def _send_batch(
    session: Session,
    tenant_id: str,
    operation_id: str,
    bank: BankAccount,
    batch: list[tuple[ReconciliationCase, BankTransaction]],
    settings,
    client: ModelClient | None,
) -> None:
    model = settings.suggestion_model
    accounts = session.scalars(
        select(Account)
        .where(
            Account.tenant_id == tenant_id,
            Account.legal_entity_id == bank.legal_entity_id,
            Account.active.is_(True),
            Account.postable.is_(True),
            Account.id != bank.account_id,
        )
        .order_by(Account.code)
    ).all()
    accounts_by_code = {account.code: account for account in accounts}
    chart = [(account.code, account.name, account.account_type) for account in accounts]
    if client is None:
        client = AnthropicModelClient(settings.claude_api_key, model)
    provider_version = f"{model}/{PROMPT_VERSION}"[:120]
    refs = {f"t{index + 1}": case.id for index, (case, _transaction) in enumerate(batch)}
    txs = [
        (f"t{index + 1}", transaction.direction, str(transaction.amount), transaction.description)
        for index, (_case, transaction) in enumerate(batch)
    ]
    system, user = build_prompt(chart, txs)
    # A reserva entra antes da chamada: o teto conta o lote mesmo que a chamada falhe.
    _autonomous(tenant_id, [_run(tenant_id, operation_id, model, len(batch), "reserved")])
    try:
        result = client.suggest(system=system, user=user)
    except Exception as exc:
        _autonomous(tenant_id, [_run(tenant_id, operation_id, model, 0, "error")])
        logger.warning(
            "counterpart suggestions batch failed tenant=%s operation=%s sent=%s error=%s",
            tenant_id,
            operation_id,
            len(batch),
            exc.__class__.__name__,
        )
        raise
    picks = validate_picks(result.answer, refs, accounts_by_code) if result.answer is not None else []
    if result.answer is None or result.stop_reason in INCOMPLETE_STOPS:
        _warn(session, tenant_id, operation_id, INCOMPLETE_WARNING)
    now = datetime.now(timezone.utc)
    rows: list = [_run(tenant_id, operation_id, model, 0, result.stop_reason, result.input_tokens, result.output_tokens)]
    rows.extend(
        AccountSuggestion(
            id=new_id("sugg"),
            tenant_id=tenant_id,
            legal_entity_id=bank.legal_entity_id,
            case_id=case_id,
            account_id=account.id,
            confidence=confidence,
            justification=justification,
            source="model",
            provider_version=provider_version,
            operation_id=operation_id,
            created_at=now,
        )
        for case_id, account, confidence, justification in picks
    )
    _autonomous(tenant_id, rows)
    logger.info(
        "counterpart suggestions batch tenant=%s operation=%s sent=%s saved=%s stop_reason=%s",
        tenant_id,
        operation_id,
        len(batch),
        len(picks),
        result.stop_reason,
    )
