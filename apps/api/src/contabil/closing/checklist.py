from __future__ import annotations

from dataclasses import dataclass

CHECKLIST_VERSION = "2026.10-1"
CLOSE_SCHEMA_VERSION = "1.1.0"
# Same pending set as reconciliation.service: open, suggested and reversed stay in the match queue.
PENDING_RECONCILIATION = frozenset({"open", "suggested", "reversed"})
_DONE = frozenset({"completed", "not_applicable"})


@dataclass(frozen=True)
class ItemSpec:
    item_id: str
    category: str
    title: str
    blocking: bool
    kind: str
    href: str
    reference: str
    count_key: str | None = None


@dataclass(frozen=True)
class ItemDecision:
    status: str
    reason: str | None
    decided_by: str | None


ITEMS: tuple[ItemSpec, ...] = (
    ItemSpec(
        "journals_pending_approval",
        "approval",
        "Lançamentos aguardando aprovação",
        True,
        "count",
        "/app/rastro/ledger",
        "ITG 2000 (R1), itens 31 a 36",
        "journals_pending_approval",
    ),
    ItemSpec(
        "journals_approved",
        "approval",
        "Lançamentos aprovados e ainda não publicados",
        True,
        "count",
        "/app/rastro/ledger",
        "ITG 2000 (R1), itens 31 a 36",
        "journals_approved",
    ),
    ItemSpec(
        "journals_draft",
        "reports",
        "Rascunhos na competência",
        False,
        "count",
        "/app/rastro/ledger",
        "ITG 2000 (R1), item 5",
        "journals_draft",
    ),
    ItemSpec(
        "import_batches_open",
        "subledger",
        "Lotes de importação ainda não publicados",
        True,
        "count",
        "/app/rastro/migracoes",
        "ITG 2000 (R1), item 5, alínea e",
        "import_batches_open",
    ),
    ItemSpec(
        "reconciliation_pending",
        "bank",
        "Conciliação bancária pendente",
        True,
        "count",
        "/app/rastro/conciliacao",
        "ITG 2000 (R1), item 14",
        "reconciliation_pending",
    ),
    ItemSpec(
        "trial_balance",
        "reports",
        "Balancete equilibrado",
        True,
        "balance",
        "/app/trial-balance",
        "ITG 2000 (R1), itens 6 e 15",
    ),
    ItemSpec(
        "trial_balance_review",
        "approval",
        "Revisão do balancete",
        True,
        "manual",
        "/app/trial-balance",
        "ITG 2000 (R1), item 12",
    ),
    ItemSpec(
        "documents",
        "documents",
        "Documentos da competência",
        False,
        "info",
        "/app/rastro/biblioteca",
        "Código Civil, art. 1.194; CTN, art. 195, parágrafo único",
        "documents",
    ),
)

BY_ID = {item.item_id: item for item in ITEMS}


def decision_error(spec: ItemSpec, status: str, reason: str | None) -> str | None:
    if status not in {"completed", "not_applicable"}:
        return "A decisão precisa concluir o item ou marcá-lo como não aplicável."
    if status == "completed" and spec.kind != "manual":
        return "Este item é calculado pelo sistema. Para dispensá-lo, marque como não aplicável e informe o motivo."
    if status == "not_applicable" and (reason is None or len(reason.strip()) < 10):
        return "Informe um motivo com pelo menos 10 caracteres."
    return None


def evaluate(counts: dict, decisions: dict[str, ItemDecision]) -> list[dict]:
    items = []
    for spec in ITEMS:
        decision = decisions.get(spec.item_id)
        waived = decision is not None and decision.status == "not_applicable"
        count = _count(spec, counts)
        status, detail = _status(spec, counts, count, decision, waived)
        items.append(
            {
                "item_id": spec.item_id,
                "category": spec.category,
                "status": status,
                "title": spec.title,
                "blocking": spec.blocking,
                "detail": detail,
                "count": count,
                "not_applicable_reason": decision.reason if waived and decision is not None else None,
                "decided_by": decision.decided_by if decision is not None and (waived or decision.status == "completed") else None,
                "owner_id": decision.decided_by if decision is not None else None,
                "evidence_ref": None,
                "href": spec.href,
                "reference": spec.reference,
            }
        )
    return items


def blocking_pending(items: list[dict]) -> list[dict]:
    return [item for item in items if item["blocking"] and item["status"] not in _DONE]


def _count(spec: ItemSpec, counts: dict) -> int | None:
    if spec.count_key is None:
        if spec.kind == "balance":
            return 0 if counts["trial_debit"] == counts["trial_credit"] else 1
        return None
    return int(counts[spec.count_key])


def _status(
    spec: ItemSpec,
    counts: dict,
    count: int | None,
    decision: ItemDecision | None,
    waived: bool,
) -> tuple[str, str]:
    if waived and decision is not None:
        return "not_applicable", f"Marcado como não aplicável: {decision.reason}"
    if spec.kind == "manual":
        if decision is not None and decision.status == "completed":
            return "completed", f"Revisão registrada por {decision.decided_by}."
        return "pending", "A revisão do balancete ainda não foi registrada."
    if spec.kind == "balance":
        debit = counts["trial_debit"]
        credit = counts["trial_credit"]
        if debit == credit:
            return "completed", f"O balancete fecha: débitos {debit} e créditos {credit}."
        return "blocked", f"O balancete não fecha: débitos {debit} e créditos {credit}."
    if spec.kind == "info":
        total = count or 0
        if total == 0:
            return "completed", "Nenhum documento está ligado a esta competência."
        return "completed", f"{total} documento(s) nesta competência."
    total = count or 0
    if total == 0:
        return "completed", f"Nenhum caso em «{spec.title.lower()}»."
    if spec.blocking:
        return "blocked", f"{total} caso(s) em «{spec.title.lower()}»."
    return "pending", f"{total} caso(s) em «{spec.title.lower()}». Não bloqueia o fechamento."
