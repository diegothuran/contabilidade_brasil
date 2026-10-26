from __future__ import annotations

import argparse
import os
import sys
from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.bootstrap import bootstrap
from contabil.documents.service import store_document
from contabil.ledger.posting import publish_balanced
from contabil.ledger.schemas import JournalCreate, LineIn
from contabil.ledger.service import approve_journal, publish_journal, reverse_journal, submit_journal
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.platform.principal import Principal
from contabil.reconciliation.router import BankAccountCreate
from contabil.reconciliation.service import create_bank_account, create_statement, import_statement
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import LegalEntity, Tenant
from contabil.tenancy.service import create_legal_entity

PREPARER_ID = "pilot-sample-preparer"
APPROVER_ID = "pilot-sample-approver"

COMPANIES = (
    ("900000000001", "Padaria Aurora Ltda. (teste)", "1500.00", "420.00", "80.00", True),
    ("900000000002", "Studio Norte Serviços Ltda. (teste)", "800.00", "250.00", "40.00", False),
    ("900000000003", "Comercial Vale Azul Ltda. (teste)", "2200.00", "640.00", "90.00", False),
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
        created: list[dict] = []
        skipped: list[str] = []
        statements = "imported" if storage_configured() else "skipped"
        for index, (base, name, capital, revenue, expense, reverse) in enumerate(COMPANIES, start=1):
            apply_tenant(session, tenant_id)
            digits = cnpj_digits(base)
            existing = session.scalar(select(LegalEntity).where(LegalEntity.tenant_id == tenant_id, LegalEntity.cnpj == digits))
            if existing is not None:
                skipped.append(name)
                session.rollback()
                continue
            company = _load_company(
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
                statements=statements == "imported",
            )
            session.commit()
            created.append(company)
        return {"created": created, "skipped": skipped, "statements": statements}
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
    statements: bool,
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
    account = create_bank_account(
        session,
        preparer,
        BankAccountCreate(
            legal_entity_id=entity_id,
            account_id=bank,
            name=f"Conta corrente {name}",
            bank_code="001",
            branch="0001",
            account_number_masked=masked,
        ),
    )
    if statements:
        _statement(session, preparer, entity_id, account["bank_account_id"], entry_date, revenue, name)
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
        f"<STMTTRN>\n<TRNTYPE>CREDIT\n<DTPOSTED>{posted}\n<TRNAMT>{revenue}\n<FITID>{entity_id}-receita\n<MEMO>Receita de serviço\n</STMTTRN>\n"
        f"<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>{posted}\n<TRNAMT>-12.50\n<FITID>{entity_id}-tarifa\n<MEMO>TARIFA\n</STMTTRN>\n"
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


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cria empresas fictícias de teste no escritório informado.")
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = load_samples(args.tenant_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for item in result["created"]:
        print(f"criada {item['name']} lancamentos={item['journals']}")
    for name in result["skipped"]:
        print(f"ja existia {name}")
    print(f"extrato={result['statements']}")


if __name__ == "__main__":
    main(sys.argv[1:])
