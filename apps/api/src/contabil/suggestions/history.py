from __future__ import annotations

import re
import unicodedata
from collections import Counter
from collections.abc import Mapping, Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session, aliased

from contabil.platform.constants import EFFECTIVE_JOURNAL_STATUSES
from contabil.suggestions.types import CONFIDENCES, Suggestion
from contabil.tables import Account, BankAccount, BankTransaction, JournalEntry, JournalLine, ReconciliationCase

PROVIDER_VERSION = "history-1"
MAX_SUGGESTIONS = 3
HIGH_USES = 3
MIN_SHARED_WORDS = 2
JUSTIFICATION_LIMIT = 300
# Casos passados lidos por pedido; os mais recentes valem mais que um histórico longo.
_HISTORY_LIMIT = 2000


def normalize_description(text: str) -> str:
    """Maiúsculas, sem acento e sem pontuação. Número solto (data, documento, parcela) sai."""
    plain = unicodedata.normalize("NFKD", text or "").encode("ascii", "ignore").decode("ascii").upper()
    words = [word for word in re.split(r"[^A-Z0-9]+", plain) if word and not word.isdigit()]
    return " ".join(words)


def _words(normalized: str) -> set[str]:
    # Palavra de uma ou duas letras (DE, DA, E) não indica semelhança.
    return {word for word in normalized.split() if len(word) > 2}


def rank_history(
    tx_description: str,
    past: Sequence[tuple[str, str]],
    accounts: Mapping[str, tuple[str, str]],
) -> list[Suggestion]:
    """Ordena as contrapartidas usadas antes. `past` traz (descrição normalizada, conta da contrapartida)."""
    target = normalize_description(tx_description)
    if not target:
        return []
    target_words = _words(target)
    exact: Counter[str] = Counter()
    partial: Counter[str] = Counter()
    partial_label: dict[str, Counter[str]] = {}
    for description, account_id in past:
        if account_id not in accounts:
            continue
        if description == target:
            exact[account_id] += 1
        elif len(target_words & _words(description)) >= MIN_SHARED_WORDS:
            partial[account_id] += 1
            partial_label.setdefault(account_id, Counter())[description] += 1
    ranked: list[tuple[int, int, str, Suggestion]] = []
    for account_id, uses in exact.items():
        confidence = "alta" if uses >= HIGH_USES else "média"
        ranked.append((CONFIDENCES.index(confidence), -uses, accounts[account_id][0], _build(account_id, accounts, confidence, uses, target)))
    for account_id, uses in partial.items():
        if account_id in exact:
            continue
        label = partial_label[account_id].most_common(1)[0][0]
        ranked.append((CONFIDENCES.index("baixa"), -uses, accounts[account_id][0], _build(account_id, accounts, "baixa", uses, label)))
    ranked.sort(key=lambda item: item[:3])
    return [item[3] for item in ranked[:MAX_SUGGESTIONS]]


def _build(account_id: str, accounts: Mapping[str, tuple[str, str]], confidence: str, uses: int, description: str) -> Suggestion:
    code, name = accounts[account_id]
    return Suggestion(
        account_id=account_id,
        code=code,
        name=name,
        confidence=confidence,  # type: ignore[arg-type]
        justification=f"Usada {uses} vez(es) para '{description}'"[:JUSTIFICATION_LIMIT],
        source="history",
        provider_version=PROVIDER_VERSION,
    )


def history_suggestions(
    session: Session,
    tenant_id: str,
    case: ReconciliationCase,
    transaction: BankTransaction,
    bank: BankAccount,
) -> list[Suggestion]:
    """Contrapartidas usadas em casos da mesma empresa, com journal de banco efetivo e mesma direção."""
    past_bank = aliased(BankAccount)
    rows = session.execute(
        select(BankTransaction.description, JournalLine.account_id)
        .select_from(ReconciliationCase)
        .join(past_bank, past_bank.id == ReconciliationCase.bank_account_id)
        .join(BankTransaction, BankTransaction.id == ReconciliationCase.transaction_id)
        .join(JournalEntry, JournalEntry.id == ReconciliationCase.journal_id)
        .join(JournalLine, JournalLine.journal_id == JournalEntry.id)
        .where(
            ReconciliationCase.tenant_id == tenant_id,
            ReconciliationCase.id != case.id,
            past_bank.tenant_id == tenant_id,
            past_bank.legal_entity_id == bank.legal_entity_id,
            BankTransaction.tenant_id == tenant_id,
            BankTransaction.direction == transaction.direction,
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == bank.legal_entity_id,
            JournalEntry.source_type == "bank",
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
            JournalLine.tenant_id == tenant_id,
            # A contrapartida é a linha que não é da conta banco do caso passado.
            JournalLine.account_id != past_bank.account_id,
        )
        .order_by(ReconciliationCase.created_at.desc())
        .limit(_HISTORY_LIMIT)
    ).all()
    if not rows:
        return []
    account_ids = {account_id for _description, account_id in rows}
    accounts = {
        row.id: (row.code, row.name)
        for row in session.scalars(
            select(Account).where(
                Account.tenant_id == tenant_id,
                Account.legal_entity_id == bank.legal_entity_id,
                Account.id.in_(account_ids),
                Account.active.is_(True),
                Account.postable.is_(True),
            )
        ).all()
    }
    past = [(normalize_description(description), account_id) for description, account_id in rows]
    return rank_history(transaction.description, past, accounts)
