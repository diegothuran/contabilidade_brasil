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
from contabil.platform.settings import get_settings
from contabil.suggestions.history import history_suggestions
from contabil.suggestions.model import BATCH_SIZE, PROMPT_VERSION, AnthropicModelClient, ModelClient, build_prompt, validate_picks
from contabil.tables import (
    Account,
    AccountingPeriod,
    AccountSuggestion,
    BankAccount,
    BankTransaction,
    ReconciliationCase,
    SuggestionRun,
)

logger = logging.getLogger("contabil.suggestions")

PENDING_STATUSES = frozenset({"open", "suggested", "reversed"})


def used_today(session: Session, tenant_id: str) -> int:
    """Transações enviadas ao modelo pelo escritório desde 00:00 de Brasília."""
    start = datetime.combine(brasilia_today(), time.min, tzinfo=BRASILIA).astimezone(timezone.utc)
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


def run_counterpart_suggestions(
    session: Session,
    tenant_id: str,
    payload: dict,
    client: ModelClient | None = None,
) -> None:
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
        return
    cases = pending_cases(session, tenant_id, bank, period)
    if not cases:
        logger.info("counterpart suggestions nothing to send tenant=%s operation=%s", tenant_id, operation_id)
        return
    settings = get_settings()
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
        client = AnthropicModelClient(settings.claude_api_key, settings.suggestion_model)
    provider_version = f"{settings.suggestion_model}/{PROMPT_VERSION}"[:120]
    for start in range(0, len(cases), BATCH_SIZE):
        batch = cases[start : start + BATCH_SIZE]
        if used_today(session, tenant_id) + len(batch) > settings.suggestion_daily_limit:
            logger.info(
                "counterpart suggestions daily limit tenant=%s operation=%s pending=%s",
                tenant_id,
                operation_id,
                len(cases) - start,
            )
            break
        refs = {f"t{index + 1}": case.id for index, (case, _transaction) in enumerate(batch)}
        txs = [
            (f"t{index + 1}", transaction.direction, str(transaction.amount), transaction.description)
            for index, (_case, transaction) in enumerate(batch)
        ]
        system, user = build_prompt(chart, txs)
        result = client.suggest(system=system, user=user)
        now = datetime.now(timezone.utc)
        session.add(
            SuggestionRun(
                id=new_id("sgrun"),
                tenant_id=tenant_id,
                operation_id=operation_id,
                model=settings.suggestion_model[:80],
                prompt_version=PROMPT_VERSION,
                transactions_sent=len(batch),
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
                stop_reason=(result.stop_reason or "unknown")[:40],
                created_at=now,
            )
        )
        picks = validate_picks(result.answer, refs, accounts_by_code) if result.answer is not None else []
        for case_id, account, confidence, justification in picks:
            session.add(
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
            )
        session.flush()
        logger.info(
            "counterpart suggestions batch tenant=%s operation=%s sent=%s saved=%s stop_reason=%s",
            tenant_id,
            operation_id,
            len(batch),
            len(picks),
            result.stop_reason,
        )
