from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.audit.service import append_event
from contabil.imports.service import operation_dict
from contabil.platform.correlation import correlation_id
from contabil.platform.errors import DomainError
from contabil.platform.ids import new_id
from contabil.platform.outbox import enqueue
from contabil.platform.principal import Principal, ensure_role
from contabil.platform.settings import get_settings
from contabil.suggestions.history import history_suggestions
from contabil.suggestions.types import suggestion_dict
from contabil.suggestions.worker import EVENT_TYPE, pending_cases, scope_of, used_today
from contabil.tables import Account, AccountSuggestion, BankAccount, BankTransaction, Operation, ReconciliationCase

OPERATION_KIND = "counterpart_suggestions"


def request_counterpart_suggestions(session: Session, principal: Principal, bank_account_id: str, period_id: str) -> dict:
    """Pede ao worker a sugestão por modelo para os casos pendentes da conta na competência (ADR 035)."""
    ensure_role(principal, "preparer", "approver", "admin")
    settings = get_settings()
    if not settings.claude_api_key:
        raise DomainError(503, "Sugestão por IA indisponível", "Este ambiente não tem a chave do modelo configurada.")
    bank, period = scope_of(session, principal.tenant_id, bank_account_id, period_id)
    if bank is None:
        raise DomainError(404, "Não encontrado", "Conta banco não encontrada.")
    if period is None:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    # Só recusa quando o teto do dia já acabou; com saldo, o worker manda o que couber e
    # conclui com o aviso `limite_diario` (ADR 035).
    if used_today(session, principal.tenant_id) >= settings.suggestion_daily_limit:
        raise DomainError(
            429,
            "Limite diário de sugestões por IA atingido",
            "O escritório já enviou o máximo de transações ao modelo hoje. Tente amanhã ou siga sem a sugestão.",
        )
    pending = len(pending_cases(session, principal.tenant_id, bank, period))
    operation = Operation(
        id=new_id("op"),
        tenant_id=principal.tenant_id,
        kind=OPERATION_KIND,
        status="accepted",
        correlation_id=correlation_id.get() or "",
        target_ref=bank.id,
    )
    session.add(operation)
    session.flush()
    enqueue(
        session,
        tenant_id=principal.tenant_id,
        event_type=EVENT_TYPE,
        payload={
            "bank_account_id": bank.id,
            "period_id": period.id,
            "operation_id": operation.id,
            "legal_entity_id": bank.legal_entity_id,
        },
    )
    append_event(
        session,
        tenant_id=principal.tenant_id,
        event_type="other",
        actor_ref=principal.user_id,
        target_type="bank_account",
        target_ref=bank.id,
        metadata={"action": "counterpart_suggestions_requested", "period_id": period.id, "pending_cases": pending},
    )
    return operation_dict(operation)


def counterpart_suggestions(
    session: Session,
    tenant_id: str,
    case: ReconciliationCase,
    transaction: BankTransaction,
    bank: BankAccount,
) -> list[dict]:
    """Histórico primeiro (calculado na leitura), depois a sugestão mais recente do modelo, sem repetir conta."""
    items = [suggestion_dict(item) for item in history_suggestions(session, tenant_id, case, transaction, bank)]
    seen = {item["account_id"] for item in items}
    latest = session.execute(
        select(AccountSuggestion, Account)
        .join(Account, Account.id == AccountSuggestion.account_id)
        .where(
            AccountSuggestion.tenant_id == tenant_id,
            AccountSuggestion.case_id == case.id,
            AccountSuggestion.legal_entity_id == bank.legal_entity_id,
            Account.tenant_id == tenant_id,
            Account.legal_entity_id == bank.legal_entity_id,
        )
        .order_by(AccountSuggestion.created_at.desc(), AccountSuggestion.id.desc())
        .limit(1)
    ).first()
    if latest is not None:
        suggestion, account = latest
        if account.active and account.postable and account.id not in seen:
            items.append(
                {
                    "account_id": account.id,
                    "code": account.code,
                    "name": account.name,
                    "confidence": suggestion.confidence,
                    "justification": suggestion.justification,
                    "source": "model",
                    "provider_version": suggestion.provider_version,
                }
            )
    return items
