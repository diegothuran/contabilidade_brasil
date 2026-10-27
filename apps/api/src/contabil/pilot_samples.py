from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.bootstrap import bootstrap
from contabil.documents.service import store_document
from contabil.ledger.posting import publish_balanced
from contabil.ledger.schemas import JournalCreate, LineIn
from contabil.ledger.service import approve_journal, create_journal, publish_journal, reverse_journal, submit_journal
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.platform.principal import Principal
from contabil.reconciliation.router import BankAccountCreate
from contabil.reconciliation.service import approve_case, create_bank_account, create_statement, ignore_case, import_statement
from contabil.seed.cnpj import cnpj_digits
from contabil.platform.errors import DomainError
from contabil.tables import (
    AccountingPeriod,
    BankAccount,
    BankStatement,
    BankTransaction,
    CostCenter,
    ImportBatch,
    JournalEntry,
    LegalEntity,
    SourceDocument,
    DocumentRequest,
    ReconciliationCase,
    ReopenRequest,
    Tenant,
)
from contabil.tenancy.service import create_legal_entity

PREPARER_ID = "pilot-sample-preparer"
APPROVER_ID = "pilot-sample-approver"

# base e passo mensal, em decimal. O valor do mês é base + passo * mês.
_ACTIVITY_SCALE: dict[str, dict[str, tuple[Decimal, Decimal]]] = {
    "andamento": {"bank": (Decimal("900.00"), Decimal("230.00")), "cash": (Decimal("120.00"), Decimal("74.00")), "expense": (Decimal("200.00"), Decimal("54.00"))},
    "fechada": {"bank": (Decimal("400.00"), Decimal("50.00")), "cash": (Decimal("40.00"), Decimal("11.00")), "expense": (Decimal("180.00"), Decimal("22.00"))},
    "banco": {"bank": (Decimal("2000.00"), Decimal("440.00")), "cash": (Decimal("300.00"), Decimal("35.00")), "expense": (Decimal("1500.00"), Decimal("260.00"))},
    "vazia": {"bank": (Decimal("600.00"), Decimal("120.00")), "cash": (Decimal("80.00"), Decimal("14.00")), "expense": (Decimal("250.00"), Decimal("39.00"))},
    "rascunhos": {"bank": (Decimal("700.00"), Decimal("140.00")), "cash": (Decimal("50.00"), Decimal("8.00")), "expense": (Decimal("400.00"), Decimal("58.00"))},
}

_ACTIVITY_TEXT: dict[str, dict[str, str]] = {
    "andamento": {
        "trade": "Padaria Aurora",
        "bank": "Venda de pão e café no balcão",
        "bank_line": "Receita do balcão",
        "cash": "Venda de salgado no caixa",
        "cash_line": "Receita do caixa",
        "expense": "Compra de farinha e fermento",
        "expense_line": "Moinho",
        "payment": "Pagamento ao moinho",
        "payment_line": "Saída do banco da padaria",
        "capital": "Capital inicial da padaria",
        "capital_line": "Capital social da padaria",
        "capital_amount": "8000.00",
        "marker_file": "comanda-balcao.txt",
        "marker_type": "receipt",
        "marker_body": "Comanda do balcão da Padaria Aurora. Sem valor fiscal.\n",
    },
    "fechada": {
        "trade": "Studio Norte",
        "bank": "Sessão de estúdio recebida no banco",
        "bank_line": "Receita do estúdio",
        "cash": "Ensaio avulso no caixa",
        "cash_line": "Receita do ensaio",
        "expense": "Aluguel da sala e equipamentos",
        "expense_line": "Locador da sala",
        "payment": "Pagamento do aluguel da sala",
        "payment_line": "Saída do banco do estúdio",
        "capital": "Capital inicial do estúdio",
        "capital_line": "Capital social do estúdio",
        "capital_amount": "3000.00",
        "marker_file": "proposta-estudio.txt",
        "marker_type": "contract",
        "marker_body": "Proposta de sessão fotográfica do Studio Norte. Sem vigência real.\n",
    },
    "banco": {
        "trade": "Comercial Vale Azul",
        "bank": "Venda de mercadoria recebida no banco",
        "bank_line": "Receita da loja",
        "cash": "Venda de balcão no caixa",
        "cash_line": "Receita do balcão da loja",
        "expense": "Compra de mercadoria para revenda",
        "expense_line": "Fornecedor da loja",
        "payment": "Pagamento ao fornecedor da loja",
        "payment_line": "Saída do banco da loja",
        "capital": "Capital inicial da loja",
        "capital_line": "Capital social da loja",
        "capital_amount": "12000.00",
        "marker_file": "pedido-mercadoria.txt",
        "marker_type": "invoice",
        "marker_body": "Pedido de mercadoria da Comercial Vale Azul. Sem efeito fiscal.\n",
    },
    "vazia": {
        "trade": "Ateliê Brisa",
        "bank": "Encomenda de vestido recebida no banco",
        "bank_line": "Receita da encomenda",
        "cash": "Ajuste de roupa no caixa",
        "cash_line": "Receita do ajuste",
        "expense": "Compra de tecido e aviamento",
        "expense_line": "Fornecedor de tecido",
        "payment": "Pagamento do tecido",
        "payment_line": "Saída do banco do ateliê",
        "capital": "Capital inicial do ateliê",
        "capital_line": "Capital social do ateliê",
        "capital_amount": "2000.00",
        "marker_file": "encomenda-vestido.txt",
        "marker_type": "contract",
        "marker_body": "Encomenda de vestido do Ateliê Brisa. Sem valor fiscal.\n",
    },
    "rascunhos": {
        "trade": "Transportes Rio Claro",
        "bank": "Frete recebido no banco",
        "bank_line": "Receita do frete",
        "cash": "Frete curto no caixa",
        "cash_line": "Receita do frete curto",
        "expense": "Diesel e pedágio do mês",
        "expense_line": "Posto",
        "payment": "Pagamento do posto",
        "payment_line": "Saída do banco da transportadora",
        "capital": "Capital inicial da transportadora",
        "capital_line": "Capital social da transportadora",
        "capital_amount": "4000.00",
        "marker_file": "conhecimento-frete.txt",
        "marker_type": "other",
        "marker_body": "Conhecimento de frete da Transportes Rio Claro. Sem valor fiscal.\n",
    },
}

COMPANIES = (
    ("900000000001", "Padaria Aurora Ltda. (teste)", "1500.00", "420.00", "80.00", True, "andamento"),
    ("900000000002", "Studio Norte Serviços Ltda. (teste)", "800.00", "250.00", "40.00", False, "fechada"),
    ("900000000003", "Comercial Vale Azul Ltda. (teste)", "2200.00", "640.00", "90.00", False, "banco"),
    ("900000000004", "Ateliê Brisa Ltda. (teste)", "0", "0", "0", False, "vazia"),
    ("900000000005", "Transportes Rio Claro Ltda. (teste)", "0", "0", "0", False, "rascunhos"),
)


def storage_configured() -> bool:
    return bool(os.environ.get("OBJECT_STORAGE_BUCKET", "").strip() and os.environ.get("OBJECT_STORAGE_ACCESS_KEY", "").strip())


def load_samples(tenant_id: str) -> dict:
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError(f"Escritório {tenant_id} não existe.")
        tenant_name = tenant.name
        session.commit()
        bootstrap(tenant_id, tenant_name, PREPARER_ID, "Preparador do piloto", ["preparer"])
        bootstrap(tenant_id, tenant_name, APPROVER_ID, "Aprovador do piloto", ["approver"])
        preparer = Principal(PREPARER_ID, tenant_id, frozenset({"preparer"}), "Preparador do piloto", tenant_name)
        approver = Principal(APPROVER_ID, tenant_id, frozenset({"approver"}), "Aprovador do piloto", tenant_name)
        year, month, entry_date = _previous_month()
        today = date.today()
        created: list[dict] = []
        skipped: list[str] = []
        notes: list[str] = []
        statements = "imported" if storage_configured() else "skipped"
        for index, (base, name, capital, revenue, expense, reverse, story) in enumerate(COMPANIES, start=1):
            apply_tenant(session, tenant_id)
            digits = cnpj_digits(base)
            existing = session.scalar(select(LegalEntity).where(LegalEntity.tenant_id == tenant_id, LegalEntity.cnpj == digits))
            published = 0
            if existing is None:
                if story in {"vazia", "rascunhos"}:
                    company = create_legal_entity(session, preparer, name=name, cnpj=digits, fiscal_year=year)
                    entity_id = company["legal_entity_id"]
                else:
                    loaded = _load_company(
                        session,
                        preparer,
                        approver,
                        name=name,
                        cnpj=digits,
                        year=year,
                        month=month,
                        entry_date=entry_date,
                        capital=capital,
                        revenue=revenue,
                        expense=expense,
                        reverse=reverse,
                        masked=f"{index:04d}",
                    )
                    entity_id = loaded["legal_entity_id"]
                    published = loaded["journals"]
                created.append({"legal_entity_id": entity_id, "name": name, "journals": published, "published": published, "story": story})
            else:
                entity_id = existing.id
                skipped.append(name)
            _enrich(
                session,
                preparer,
                approver,
                entity_id=entity_id,
                name=name,
                story=story,
                year=year,
                month=month,
                entry_date=entry_date,
                revenue=revenue,
                masked=f"{index:04d}",
                today=today,
                statements=statements == "imported",
                notes=notes,
            )
            session.commit()
        return {"created": created, "skipped": skipped, "statements": statements, "notes": notes}
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _load_company(
    session: Session,
    preparer: Principal,
    approver: Principal,
    *,
    name: str,
    cnpj: str,
    year: int,
    month: int,
    entry_date: date,
    capital: str,
    revenue: str,
    expense: str,
    reverse: bool,
    masked: str,
) -> dict:
    created = create_legal_entity(session, preparer, name=name, cnpj=cnpj, fiscal_year=year)
    entity_id = created["legal_entity_id"]
    period_id = f"{entity_id}-{year}-{month:02d}"
    bank = f"{entity_id}-1.1.02"
    journals = 0
    capital_id = _journal(session, preparer, approver, entity_id, period_id, entry_date, "Aporte de capital", bank, f"{entity_id}-3.1.01", capital, "Banco", "Capital social")
    journals += 1
    _journal(session, preparer, approver, entity_id, period_id, entry_date, "Receita de serviço recebida", bank, f"{entity_id}-4.1.01", revenue, "Recebimento", "Receita de serviços")
    journals += 1
    _journal(session, preparer, approver, entity_id, period_id, entry_date, "Despesa a pagar", f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", expense, "Despesa de serviço", "Fornecedor a pagar")
    journals += 1
    _journal(session, preparer, approver, entity_id, period_id, entry_date, "Pagamento a fornecedor", f"{entity_id}-2.1.01", bank, expense, "Baixa do fornecedor", "Pagamento")
    journals += 1
    if reverse:
        reversal = reverse_journal(session, preparer, capital_id)
        submit_journal(session, preparer, reversal["journal_id"])
        approve_journal(session, approver, reversal["journal_id"])
        publish_journal(session, approver, reversal["journal_id"])
        journals += 1
    _ensure_bank(session, preparer, entity_id, bank, name, masked)
    return {"legal_entity_id": entity_id, "name": name, "journals": journals, "period_id": period_id}


def _journal(session, preparer, approver, entity_id, period_id, entry_date, description, debit, credit, amount, debit_text, credit_text) -> str:
    return publish_balanced(
        session,
        preparer,
        approver,
        JournalCreate(
            legal_entity_id=entity_id,
            period_id=period_id,
            currency="BRL",
            entry_date=entry_date,
            description=description,
            lines=[
                LineIn(account_id=debit, side="debit", amount=amount, description=debit_text),
                LineIn(account_id=credit, side="credit", amount=amount, description=credit_text),
            ],
        ),
    )


def _statement(session, preparer: Principal, entity_id: str, bank_account_id: str, entry_date: date, revenue: str, name: str) -> None:
    posted = entry_date.strftime("%Y%m%d")
    ofx = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n"
        "COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n<OFX>\n"
        "<BANKTRANLIST>\n"
        f"<DTSTART>{posted}\n<DTEND>{posted}\n"
        f"<STMTTRN>\n<TRNTYPE>CREDIT\n<DTPOSTED>{posted}\n<TRNAMT>{revenue}\n<FITID>{entity_id}-receita\n<MEMO>{name}: recebimento de serviço\n</STMTTRN>\n"
        f"<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>{posted}\n<TRNAMT>-12.50\n<FITID>{entity_id}-tarifa\n<MEMO>{name}: TARIFA bancária\n</STMTTRN>\n"
        f"<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>{posted}\n<TRNAMT>-20.00\n<FITID>{entity_id}-devolvida\n<MEMO>{name}: DEVOLVIDA pelo cliente\n</STMTTRN>\n"
        "</BANKTRANLIST>\n</OFX>\n"
    ).encode("cp1252")
    stored, _status = store_document(
        session,
        preparer,
        file_name=f"extrato-{entity_id}.ofx",
        media_type="application/x-ofx",
        content=ofx,
        document_type="bank_statement",
        legal_entity_id=entity_id,
        competence=entry_date.strftime("%Y-%m"),
        source_ref=f"amostra-{name}",
        source_type="upload",
    )
    operation = create_statement(session, preparer, bank_account_id, stored["document_id"])
    import_statement(session, preparer.tenant_id, {"statement_id": operation["statement_id"], "operation_id": operation["operation_id"]})


def _previous_month() -> tuple[int, int, date]:
    today = date.today()
    year = today.year - 1 if today.month == 1 else today.year
    month = 12 if today.month == 1 else today.month - 1
    return year, month, date(year, month, 15)


def _enrich(
    session: Session,
    preparer: Principal,
    approver: Principal,
    *,
    entity_id: str,
    name: str,
    story: str,
    year: int,
    month: int,
    entry_date: date,
    revenue: str,
    masked: str,
    today: date,
    statements: bool,
    notes: list[str],
) -> None:
    period_id = f"{entity_id}-{year}-{month:02d}"
    bank = f"{entity_id}-1.1.02"
    current_period = f"{entity_id}-{today.year}-{today.month:02d}"
    current_date = date(today.year, today.month, min(15, today.day))
    if story == "andamento":
        center_id = _ensure_center(session, preparer.tenant_id, entity_id)
        _ensure_journal(
            session, preparer, approver, entity_id, period_id, entry_date, "rascunho", "draft",
            f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", "30.00", "Aluguel em rascunho", "Fornecedor",
            cost_center_id=center_id,
        )
        _ensure_journal(
            session, preparer, approver, entity_id, period_id, entry_date, "pendente", "pending",
            f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", "55.00", "Compra aguardando aprovação", "Fornecedor",
        )
        _ensure_journal(
            session, preparer, approver, entity_id, period_id, entry_date, "aprovado", "approved",
            f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", "70.00", "Honorários aguardando publicação", "Fornecedor",
        )
        if _period_exists(session, current_period):
            _ensure_journal(
                session, preparer, approver, entity_id, current_period, current_date, "corrente", "published",
                bank, f"{entity_id}-4.1.01", "100.00", "Venda do mês corrente", "Receita de serviços",
            )
        _ensure_bank(session, preparer, entity_id, bank, name, masked)
        if statements:
            _ensure_import(session, preparer, entity_id, name, notes)
            _ensure_receipt(session, preparer, entity_id, entry_date, name)
    elif story == "fechada":
        _ensure_bank(session, preparer, entity_id, bank, name, masked)
        _close_and_request_reopen(session, preparer, approver, period_id, notes, name)
    elif story == "banco":
        account_id = _ensure_bank(session, preparer, entity_id, bank, name, masked)
        if statements and account_id:
            _ensure_statement(session, preparer, approver, entity_id, account_id, entry_date, revenue, _ACTIVITY_TEXT[story]["trade"])
            _ensure_receipt(session, preparer, entity_id, entry_date, name)
    elif story == "rascunhos":
        _ensure_bank(session, preparer, entity_id, bank, name, masked)
        if _period_exists(session, current_period):
            _ensure_journal(
                session, preparer, approver, entity_id, current_period, current_date, "rascunho", "draft",
                f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", "25.00", "Frete em rascunho", "Fornecedor",
            )
            _ensure_journal(
                session, preparer, approver, entity_id, current_period, current_date, "pendente", "pending",
                f"{entity_id}-5.1.01", f"{entity_id}-2.1.01", "15.00", "Pedágio aguardando aprovação", "Fornecedor",
            )
    _ensure_activity(session, preparer, approver, entity_id, year, today, story, name, notes)
    if statements:
        _ensure_files(
            session, preparer, approver, entity_id=entity_id, name=name, story=story, masked=masked, today=today, notes=notes,
        )
    if story == "andamento":
        _ensure_sample_request(session, preparer, approver, entity_id, name, notes, confirm=True)
    elif story == "vazia":
        _ensure_sample_request(session, preparer, approver, entity_id, name, notes, confirm=False)


def _activity_months(year: int, today: date) -> list[int]:
    months = {2, 4, 6, 8, today.month}
    if year < today.year:
        return sorted(months)
    return sorted(month for month in months if month <= today.month)


def _money(amount: Decimal) -> str:
    return f"{amount.quantize(Decimal('0.01')):.2f}"


def activity_amount(story: str, kind: str, month: int) -> str:
    base, step = _ACTIVITY_SCALE[story][kind]
    return _money(base + Decimal(month) * step)


def _cloned_is_cleared(
    session: Session,
    preparer: Principal,
    approver: Principal,
    entity_id: str,
    key: str,
    name: str,
    notes: list[str],
) -> bool:
    source_id = _source_id(entity_id, key)
    journal = session.scalar(
        select(JournalEntry).where(
            JournalEntry.tenant_id == preparer.tenant_id,
            JournalEntry.legal_entity_id == entity_id,
            JournalEntry.source_id == source_id,
        )
    )
    if journal is None:
        return True
    if journal.status != "published":
        return False
    reversal = session.scalar(
        select(JournalEntry).where(
            JournalEntry.tenant_id == preparer.tenant_id,
            JournalEntry.reverses_journal_id == journal.id,
            JournalEntry.status != "rejected",
        )
    )
    if reversal is not None:
        return reversal.status == "published"
    period = session.get(AccountingPeriod, journal.period_id)
    if period is None or period.status not in {"open", "reopened"}:
        notes.append(f"{name}: lançamento repetido {key} ficou em período fechado")
        return False
    try:
        created = reverse_journal(session, preparer, journal.id)
        submit_journal(session, preparer, created["journal_id"])
        approve_journal(session, approver, created["journal_id"])
        publish_journal(session, approver, created["journal_id"])
    except DomainError as exc:
        notes.append(f"{name}: estorno de {key} não publicado ({exc.detail})")
        return False
    return True


def _ensure_activity(
    session: Session,
    preparer: Principal,
    approver: Principal,
    entity_id: str,
    year: int,
    today: date,
    story: str,
    name: str,
    notes: list[str],
) -> None:
    text = _ACTIVITY_TEXT[story]
    caixa = f"{entity_id}-1.1.01"
    banco = f"{entity_id}-1.1.02"
    fornecedor = f"{entity_id}-2.1.01"
    capital = f"{entity_id}-3.1.01"
    receita = f"{entity_id}-4.1.01"
    despesa = f"{entity_id}-5.1.01"
    for month in _activity_months(year, today):
        period_id = f"{entity_id}-{year}-{month:02d}"
        period = session.get(AccountingPeriod, period_id)
        if period is None or period.status not in {"open", "reopened"}:
            continue
        posted = date(year, month, min(12, today.day if month == today.month and year == today.year else 12))
        stamp = f"{year}-{month:02d}"
        bank_amount = activity_amount(story, "bank", month)
        cash_amount = activity_amount(story, "cash", month)
        expense_amount = activity_amount(story, "expense", month)
        if _cloned_is_cleared(session, preparer, approver, entity_id, f"venda-banco-{stamp}", name, notes):
            _ensure_journal(
                session, preparer, approver, entity_id, period_id, posted, f"ramo-venda-banco-{stamp}", "published",
                banco, receita, bank_amount, text["bank"], text["bank_line"],
            )
        if _cloned_is_cleared(session, preparer, approver, entity_id, f"venda-caixa-{stamp}", name, notes):
            _ensure_journal(
                session, preparer, approver, entity_id, period_id, posted, f"ramo-venda-caixa-{stamp}", "published",
                caixa, receita, cash_amount, text["cash"], text["cash_line"],
            )
        if _cloned_is_cleared(session, preparer, approver, entity_id, f"despesa-{stamp}", name, notes):
            _ensure_journal(
                session, preparer, approver, entity_id, period_id, posted, f"ramo-despesa-{stamp}", "published",
                despesa, fornecedor, expense_amount, text["expense"], text["expense_line"],
            )
        if _cloned_is_cleared(session, preparer, approver, entity_id, f"pagamento-{stamp}", name, notes):
            _ensure_journal(
                session, preparer, approver, entity_id, period_id, posted, f"ramo-pagamento-{stamp}", "published",
                fornecedor, banco, expense_amount, text["payment"], text["payment_line"],
            )
    opening = f"{entity_id}-{year}-02"
    opening_period = session.get(AccountingPeriod, opening)
    if opening_period is not None and opening_period.status in {"open", "reopened"}:
        if _cloned_is_cleared(session, preparer, approver, entity_id, "capital-inicial", name, notes):
            _ensure_journal(
                session, preparer, approver, entity_id, opening, date(year, 2, 2), "ramo-capital", "published",
                banco, capital, text["capital_amount"], text["capital"], text["capital_line"],
            )


def _period_exists(session: Session, period_id: str) -> bool:
    return session.get(AccountingPeriod, period_id) is not None


def _source_id(entity_id: str, key: str) -> str:
    return f"amostra-{entity_id}-{key}"


def _ensure_center(session: Session, tenant_id: str, entity_id: str) -> str:
    found = session.scalar(
        select(CostCenter).where(CostCenter.tenant_id == tenant_id, CostCenter.legal_entity_id == entity_id, CostCenter.code == "ADM")
    )
    if found is not None:
        return found.id
    center_id = f"{entity_id}-cc-adm"
    session.add(
        CostCenter(
            id=center_id,
            tenant_id=tenant_id,
            legal_entity_id=entity_id,
            code="ADM",
            name="Administrativo",
            active=True,
        )
    )
    session.flush()
    return center_id


def _ensure_bank(session: Session, preparer: Principal, entity_id: str, account_id: str, name: str, masked: str) -> str | None:
    found = session.scalar(
        select(BankAccount).where(
            BankAccount.tenant_id == preparer.tenant_id,
            BankAccount.legal_entity_id == entity_id,
            BankAccount.account_id == account_id,
        )
    )
    if found is not None:
        return found.id
    created = create_bank_account(
        session,
        preparer,
        BankAccountCreate(
            legal_entity_id=entity_id,
            account_id=account_id,
            name=f"Conta corrente {name}",
            bank_code="001",
            branch="0001",
            account_number_masked=masked,
        ),
    )
    return created["bank_account_id"]


def _ensure_journal(
    session: Session,
    preparer: Principal,
    approver: Principal,
    entity_id: str,
    period_id: str,
    entry_date: date,
    key: str,
    status: str,
    debit: str,
    credit: str,
    amount: str,
    debit_text: str,
    credit_text: str,
    cost_center_id: str | None = None,
) -> None:
    source_id = _source_id(entity_id, key)
    found = session.scalar(
        select(JournalEntry.id).where(
            JournalEntry.tenant_id == preparer.tenant_id,
            JournalEntry.legal_entity_id == entity_id,
            JournalEntry.source_id == source_id,
        )
    )
    if found is not None:
        return
    body = JournalCreate(
        legal_entity_id=entity_id,
        period_id=period_id,
        currency="BRL",
        entry_date=entry_date,
        description=debit_text,
        source_id=source_id,
        lines=[
            LineIn(account_id=debit, side="debit", amount=amount, description=debit_text, cost_center_id=cost_center_id),
            LineIn(account_id=credit, side="credit", amount=amount, description=credit_text),
        ],
    )
    if status == "published":
        publish_balanced(session, preparer, approver, body)
        return
    created = create_journal(session, preparer, body)
    if status == "draft":
        return
    submit_journal(session, preparer, created["journal_id"])
    if status == "approved":
        approve_journal(session, approver, created["journal_id"])


def _close_and_request_reopen(
    session: Session,
    preparer: Principal,
    approver: Principal,
    period_id: str,
    notes: list[str],
    name: str,
) -> None:
    from contabil.closing.service import close_run, decide_item, open_close_run
    from contabil.periods.service import request_reopen

    period = session.get(AccountingPeriod, period_id)
    if period is None:
        notes.append(f"{name}: período {period_id} não existe")
        return
    if period.status in {"open", "reopened"}:
        try:
            _opened, payload = open_close_run(session, approver, period_id)
            decide_item(session, approver, payload["close_run_id"], "trial_balance_review", status="completed", reason=None)
            close_run(session, approver, payload["close_run_id"])
        except DomainError as exc:
            notes.append(f"{name}: fechamento não concluído ({exc.detail})")
            return
        period = session.get(AccountingPeriod, period_id)
    if period is None or period.status != "closed":
        return
    pending = session.scalar(
        select(ReopenRequest.id).where(
            ReopenRequest.tenant_id == preparer.tenant_id,
            ReopenRequest.period_id == period_id,
            ReopenRequest.status == "pending",
        )
    )
    if pending is None:
        request_reopen(session, preparer, period_id, "Amostra para outra pessoa aprovar a reabertura.")


def _has_document(session: Session, tenant_id: str, source_ref: str) -> bool:
    found = session.scalar(
        select(SourceDocument.id).where(SourceDocument.tenant_id == tenant_id, SourceDocument.source_ref == source_ref)
    )
    return found is not None


def _store_sample_file(
    session: Session,
    preparer: Principal,
    *,
    entity_id: str,
    name: str,
    source_ref: str,
    file_name: str,
    media_type: str,
    document_type: str,
    competence: str | None,
    content: bytes,
    notes: list[str],
) -> None:
    if _has_document(session, preparer.tenant_id, source_ref):
        return
    try:
        store_document(
            session,
            preparer,
            file_name=file_name,
            media_type=media_type,
            content=content,
            document_type=document_type,
            legal_entity_id=entity_id,
            competence=competence,
            source_ref=source_ref,
            source_type="upload",
        )
    except DomainError as exc:
        notes.append(f"{name}: arquivo {file_name} não gravado ({exc.detail})")


def _ensure_files(
    session: Session,
    preparer: Principal,
    approver: Principal,
    *,
    entity_id: str,
    name: str,
    story: str,
    masked: str,
    today: date,
    notes: list[str],
) -> None:
    bank = f"{entity_id}-1.1.02"
    competence = f"{today.year}-{today.month:02d}"
    posted = date(today.year, today.month, min(12, today.day))
    amount = _money(Decimal("200.00") + Decimal(today.month) * Decimal("25.00"))
    account_id = _ensure_bank(session, preparer, entity_id, bank, name, masked)
    _ensure_receipt(session, preparer, entity_id, posted, name)
    _store_sample_file(
        session,
        preparer,
        entity_id=entity_id,
        name=name,
        source_ref=f"amostra-nota-{entity_id}",
        file_name=f"nota-{entity_id}.txt",
        media_type="text/plain",
        document_type="journal_support",
        competence=competence,
        content=f"Nota fictícia de {name} em {competence}. Valor de referência {amount}. Sem efeito fiscal.\n".encode(),
        notes=notes,
    )
    _store_sample_file(
        session,
        preparer,
        entity_id=entity_id,
        name=name,
        source_ref=f"amostra-contrato-{entity_id}",
        file_name=f"contrato-{entity_id}.txt",
        media_type="text/plain",
        document_type="contract",
        competence=None,
        content=f"Contrato fictício de prestação de serviço de {name}. Documento de teste, sem vigência real.\n".encode(),
        notes=notes,
    )
    _ensure_journal_import(session, preparer, entity_id, name, posted, notes)
    text = _ACTIVITY_TEXT[story]
    _store_sample_file(
        session,
        preparer,
        entity_id=entity_id,
        name=name,
        source_ref=f"amostra-marca-{entity_id}",
        file_name=text["marker_file"],
        media_type="text/plain",
        document_type=text["marker_type"],
        competence=competence,
        content=text["marker_body"].encode(),
        notes=notes,
    )
    if account_id:
        try:
            _ensure_statement(session, preparer, approver, entity_id, account_id, posted, amount, text["trade"])
        except DomainError as exc:
            notes.append(f"{name}: extrato não concluído ({exc.detail})")


def _ensure_journal_import(
    session: Session,
    preparer: Principal,
    entity_id: str,
    name: str,
    posted: date,
    notes: list[str],
) -> None:
    from contabil.imports.router import BatchCreate, FileIn
    from contabil.imports.service import create_batch, validate_batch

    source = f"amostra-diario-{entity_id}"
    period_id = f"{entity_id}-{posted.year}-{posted.month:02d}"
    if not _period_exists(session, period_id):
        notes.append(f"{name}: lote de diário sem período {posted.year}-{posted.month:02d}")
        return
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.tenant_id == preparer.tenant_id, ImportBatch.source_system == source)
    )
    if batch is not None and batch.status != "received":
        return
    if batch is not None:
        notes.append(f"{name}: lote de diário ficou recebido e não foi revalidado")
        return
    day = posted.isoformat()
    csv = (
        "external_journal_id;entry_date;description;account_code;side;amount;line_description;cost_center_code\n"
        f"amostra-j-{entity_id};{day};Amostra de diário;1.1.02;debit;15.00;Banco;\n"
        f"amostra-j-{entity_id};{day};Amostra de diário;4.1.01;credit;15.00;Receita de serviços;\n"
        f"amostra-j-{entity_id}-invalida;{day};Linha sem conta;;debit;1.00;Conta ausente;\n"
    ).encode()
    try:
        stored, _status = store_document(
            session,
            preparer,
            file_name=f"diario-{entity_id}.csv",
            media_type="text/csv",
            content=csv,
            document_type="other",
            legal_entity_id=entity_id,
            competence=posted.strftime("%Y-%m"),
            source_ref=source,
            source_type="import",
        )
        operation = create_batch(
            session,
            preparer,
            BatchCreate(
                legal_entity_id=entity_id,
                source_system=source,
                mode="dry_run",
                period_id=period_id,
                files=[FileIn(document_id=stored["document_id"], kind="journal")],
            ),
            source,
        )
        created = session.scalar(
            select(ImportBatch).where(ImportBatch.tenant_id == preparer.tenant_id, ImportBatch.idempotency_key == source)
        )
        if created is None:
            notes.append(f"{name}: lote de diário não foi criado")
            return
        validate_batch(session, preparer.tenant_id, {"batch_id": created.id, "operation_id": operation["operation_id"]})
    except DomainError as exc:
        notes.append(f"{name}: lote de diário não gravado ({exc.detail})")


def _ensure_receipt(session: Session, preparer: Principal, entity_id: str, entry_date: date, name: str) -> None:
    content = f"Recibo fictício de {name}. Sem valor fiscal.\n".encode()
    store_document(
        session,
        preparer,
        file_name=f"recibo-{entity_id}.txt",
        media_type="text/plain",
        content=content,
        document_type="receipt",
        legal_entity_id=entity_id,
        competence=entry_date.strftime("%Y-%m"),
        source_ref=f"amostra-recibo-{entity_id}",
        source_type="upload",
    )


def _ensure_sample_request(
    session: Session,
    preparer: Principal,
    approver: Principal,
    entity_id: str,
    name: str,
    notes: list[str],
    *,
    confirm: bool,
) -> None:
    from contabil.document_requests.service import confirm_request, create_request, receive_content
    from contabil.platform.constants import POSTING_PERIOD_STATUSES

    period_id = f"{entity_id}-2026-10"
    period = session.get(AccountingPeriod, period_id)
    title = "Amostra: recibo de outubro" if confirm else "Amostra: contrato de outubro"
    if period is None or period.status not in POSTING_PERIOD_STATUSES:
        notes.append(f"{name}: pedido de outubro não gravado (período indisponível)")
        return
    existing = session.scalar(
        select(DocumentRequest).where(
            DocumentRequest.tenant_id == preparer.tenant_id,
            DocumentRequest.legal_entity_id == entity_id,
            DocumentRequest.period_id == period_id,
            DocumentRequest.title == title,
        )
    )
    if confirm and not storage_configured() and (existing is None or existing.status == "open"):
        notes.append(f"{name}: pedido confirmado não gravado (sem armazenamento)")
        return
    try:
        if existing is None:
            created = create_request(
                session,
                preparer,
                legal_entity_id=entity_id,
                period_id=period_id,
                document_type="receipt" if confirm else "contract",
                title=title,
                due_on=date(2026, 10, 31),
            )
            request_id = created["document_request_id"]
            status = created["status"]
        else:
            request_id = existing.id
            status = existing.status
        if not confirm or status in {"confirmed", "cancelled"}:
            return
        if status == "open":
            received = receive_content(
                session,
                preparer,
                request_id,
                file_name=f"pedido-recibo-{entity_id}.txt",
                media_type="text/plain",
                content=f"Recibo de amostra de {name}. Sem valor fiscal.\n".encode(),
            )
            status = received["status"]
        if status == "received":
            confirm_request(session, approver, request_id)
    except DomainError as exc:
        notes.append(f"{name}: pedido de outubro não gravado ({exc.detail})")


def _ensure_import(session: Session, preparer: Principal, entity_id: str, name: str, notes: list[str]) -> None:
    from contabil.imports.router import BatchCreate, FileIn
    from contabil.imports.service import create_batch, validate_batch

    source = f"amostra-plano-{entity_id}"
    batch = session.scalar(
        select(ImportBatch).where(ImportBatch.tenant_id == preparer.tenant_id, ImportBatch.source_system == source)
    )
    if batch is not None and batch.status != "received":
        return
    if batch is None:
        csv = (
            "external_id;code;name;account_type;postable;parent_code\n"
            f"amostra-{entity_id}-5.1.02;5.1.02;Despesas diversas;expense;true;5\n"
            f"amostra-{entity_id}-invalida;;Conta sem código;expense;true;5\n"
        ).encode()
        stored, _status = store_document(
            session,
            preparer,
            file_name=f"plano-{entity_id}.csv",
            media_type="text/csv",
            content=csv,
            document_type="other",
            legal_entity_id=entity_id,
            competence=None,
            source_ref=source,
            source_type="import",
        )
        operation = create_batch(
            session,
            preparer,
            BatchCreate(
                legal_entity_id=entity_id,
                source_system=source,
                mode="dry_run",
                files=[FileIn(document_id=stored["document_id"], kind="chart_of_accounts")],
            ),
            source,
        )
        batch = session.scalar(
            select(ImportBatch).where(ImportBatch.tenant_id == preparer.tenant_id, ImportBatch.idempotency_key == source)
        )
        if batch is None:
            notes.append(f"{name}: lote de importação não foi criado")
            return
        validate_batch(session, preparer.tenant_id, {"batch_id": batch.id, "operation_id": operation["operation_id"]})
        return
    notes.append(f"{name}: lote {batch.id} ficou recebido e não foi revalidado")


def _ensure_statement(
    session: Session,
    preparer: Principal,
    approver: Principal,
    entity_id: str,
    bank_account_id: str,
    entry_date: date,
    revenue: str,
    name: str,
) -> None:
    found = session.scalar(
        select(BankStatement.id).where(
            BankStatement.tenant_id == preparer.tenant_id,
            BankStatement.bank_account_id == bank_account_id,
        )
    )
    if found is not None:
        return
    _statement(session, preparer, entity_id, bank_account_id, entry_date, revenue, name)
    cases = list(
        session.scalars(
            select(ReconciliationCase).where(
                ReconciliationCase.tenant_id == preparer.tenant_id,
                ReconciliationCase.bank_account_id == bank_account_id,
            )
        ).all()
    )
    approved = False
    for case in cases:
        transaction = session.get(BankTransaction, case.transaction_id)
        memo = transaction.description if transaction is not None else ""
        if case.status == "suggested" and case.candidates and not approved:
            approve_case(session, approver, case.id, case.candidates[0]["candidate_id"])
            approved = True
        elif case.status == "open" and "DEVOLVIDA" in memo:
            ignore_case(session, approver, case.id, "Amostra: devolução que não entra no razão.")


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cria empresas fictícias de teste no escritório informado.")
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = load_samples(args.tenant_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for item in result["created"]:
        print(f"criada {item['name']} cenario={item['story']} lancamentos={item['journals']}")
    for name in result["skipped"]:
        print(f"ja existia {name}")
    for note in result["notes"]:
        print(f"nota {note}")
    print(f"extrato={result['statements']}")


if __name__ == "__main__":
    main(sys.argv[1:])
