from __future__ import annotations

from datetime import date

from contabil.ledger.posting import publish_balanced
from contabil.ledger.schemas import JournalCreate, LineIn
from contabil.ledger.service import approve_journal, publish_journal, reverse_journal, submit_journal
from contabil.master_data.starter_chart import add_open_year, add_starter_chart
from contabil.platform.db import session_factory
from contabil.platform.principal import Principal
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import (
    AppUser,
    CostCenter,
    Establishment,
    LegalEntity,
    Membership,
    Tenant,
)


def _add_chart(session, tenant_id: str, entity_id: str) -> None:
    add_starter_chart(
        session,
        tenant_id=tenant_id,
        legal_entity_id=entity_id,
        chart_id=f"chart_{entity_id}",
        chart_name="Plano sintético",
        account_id=lambda code: f"{entity_id}-{code}",
    )
    add_open_year(
        session,
        tenant_id=tenant_id,
        legal_entity_id=entity_id,
        year=2026,
        period_id=lambda year, month: f"{entity_id}-{year}-{month:02d}",
    )


def _publish(session, preparer: Principal, approver: Principal, body: JournalCreate) -> str:
    return publish_balanced(session, preparer, approver, body)


def seed() -> None:
    session = session_factory(admin=True)()
    try:
        if session.get(Tenant, "tenant_demo") is None:
            _seed_foundation(session)
        _seed_phase_b(session)
        _seed_phase_c(session)
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _seed_foundation(session) -> None:
        session.add_all(
            [
                Tenant(id="tenant_demo", name="Escritório Demo"),
                Tenant(id="tenant_other", name="Escritório Outro"),
            ]
        )
        users = [
            ("preparer", "Preparador", "tenant_demo", ["preparer"]),
            ("approver", "Aprovador", "tenant_demo", ["approver"]),
            ("admin", "Administrador", "tenant_demo", ["preparer", "approver", "admin", "viewer"]),
            ("viewer", "Consulta", "tenant_demo", ["viewer"]),
            ("outsider", "Outro escritório", "tenant_other", ["preparer"]),
        ]
        for user_id, display_name, _tenant, _roles in users:
            session.add(AppUser(id=user_id, display_name=display_name))
        session.flush()
        for user_id, _display_name, tenant_id, roles in users:
            session.add(Membership(id=f"mem_{tenant_id}_{user_id}", tenant_id=tenant_id, user_id=user_id, roles=roles))
        entities = [
            ("le_alfa", "tenant_demo", "Empresa Alfa", cnpj_digits("100000000001")),
            ("le_beta", "tenant_demo", "Empresa Beta", cnpj_digits("100000000002")),
            ("le_outra", "tenant_other", "Empresa Outra", cnpj_digits("200000000001")),
        ]
        for entity_id, tenant_id, name, cnpj in entities:
            session.add(LegalEntity(id=entity_id, tenant_id=tenant_id, name=name, cnpj=cnpj, currency="BRL"))
        session.flush()
        for entity_id, tenant_id, _name, _cnpj in entities:
            session.add(Establishment(id=f"est_{entity_id}", tenant_id=tenant_id, legal_entity_id=entity_id, name="Matriz"))
        session.flush()
        for entity_id, tenant_id, _name, _cnpj in entities:
            _add_chart(session, tenant_id, entity_id)
        session.add(CostCenter(id="cc_alfa", tenant_id="tenant_demo", legal_entity_id="le_alfa", code="ADM", name="Administrativo", active=True))
        session.flush()
        preparer = Principal("preparer", "tenant_demo", frozenset({"preparer"}), "Preparador", "Escritório Demo")
        approver = Principal("approver", "tenant_demo", frozenset({"approver"}), "Aprovador", "Escritório Demo")
        _publish(
            session,
            preparer,
            approver,
            JournalCreate(
                legal_entity_id="le_alfa",
                period_id="le_alfa-2026-09",
                currency="BRL",
                entry_date=date(2026, 9, 15),
                description="Reconhecimento de despesa de serviço",
                lines=[
                    LineIn(account_id="le_alfa-5.1.01", side="debit", amount="1000.00", description="Despesa de serviço", cost_center_id="cc_alfa"),
                    LineIn(account_id="le_alfa-2.1.01", side="credit", amount="1000.00", description="Fornecedor a pagar"),
                ],
            ),
        )
        aporte_id = _publish(
            session,
            preparer,
            approver,
            JournalCreate(
                legal_entity_id="le_alfa",
                period_id="le_alfa-2026-09",
                currency="BRL",
                entry_date=date(2026, 9, 20),
                description="Aporte de capital",
                lines=[
                    LineIn(account_id="le_alfa-1.1.02", side="debit", amount="500.00", description="Banco"),
                    LineIn(account_id="le_alfa-3.1.01", side="credit", amount="500.00", description="Capital social"),
                ],
            ),
        )
        reversal = reverse_journal(session, preparer, aporte_id)
        submit_journal(session, preparer, reversal["journal_id"])
        approve_journal(session, approver, reversal["journal_id"])
        publish_journal(session, approver, reversal["journal_id"])


def _seed_phase_b(session) -> None:
    from sqlalchemy import select

    from contabil.documents.service import store_document
    from contabil.imports.router import BatchCreate, FileIn
    from contabil.imports.service import create_batch
    from contabil.tables import ImportBatch

    existing = session.scalar(
        select(ImportBatch).where(ImportBatch.tenant_id == "tenant_demo", ImportBatch.source_system == "demo-legacy")
    )
    if existing is not None:
        return
    csv = (
        "external_id;code;name;account_type;postable;parent_code\n"
        "demo-7;7;Outras contas;expense;false;\n"
        "demo-7.1;7.1.01;Despesas diversas;expense;true;7\n"
    ).encode()
    preparer = Principal("preparer", "tenant_demo", frozenset({"preparer"}), "Preparador", "Escritório Demo")
    stored, _status = store_document(
        session,
        preparer,
        file_name="plano-demo.csv",
        media_type="text/csv",
        content=csv,
        document_type="other",
        legal_entity_id="le_alfa",
        competence="2026-09",
        source_ref="demo-legacy",
        source_type="import",
    )
    create_batch(
        session,
        preparer,
        BatchCreate(
            legal_entity_id="le_alfa",
            source_system="demo-legacy",
            mode="dry_run",
            files=[FileIn(document_id=stored["document_id"], kind="chart_of_accounts")],
        ),
        "seed-demo-chart",
    )


def _seed_phase_c(session) -> None:
    from sqlalchemy import select

    from contabil.documents.service import store_document
    from contabil.reconciliation.service import create_bank_account, create_statement, import_statement
    from contabil.reconciliation.router import BankAccountCreate
    from contabil.tables import BankAccount

    existing = session.scalar(
        select(BankAccount).where(BankAccount.tenant_id == "tenant_demo", BankAccount.legal_entity_id == "le_alfa", BankAccount.account_id == "le_alfa-1.1.02")
    )
    if existing is not None:
        return
    preparer = Principal("preparer", "tenant_demo", frozenset({"preparer"}), "Preparador", "Escritório Demo")
    approver = Principal("approver", "tenant_demo", frozenset({"approver"}), "Aprovador", "Escritório Demo")
    _publish(
        session,
        preparer,
        approver,
        JournalCreate(
            legal_entity_id="le_alfa",
            period_id="le_alfa-2026-09",
            currency="BRL",
            entry_date=date(2026, 9, 15),
            description="Recebimento cliente",
            lines=[
                LineIn(account_id="le_alfa-1.1.02", side="debit", amount="300.00", description="Recebimento cliente"),
                LineIn(account_id="le_alfa-4.1.01", side="credit", amount="300.00", description="Receita de serviços"),
            ],
        ),
    )
    account = create_bank_account(
        session,
        preparer,
        BankAccountCreate(
            legal_entity_id="le_alfa",
            account_id="le_alfa-1.1.02",
            name="Conta corrente Alfa",
            bank_code="001",
            branch="1234",
            account_number_masked="6789",
        ),
    )
    ofx = (
        "OFXHEADER:100\nDATA:OFXSGML\nVERSION:102\nSECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\n"
        "COMPRESSION:NONE\nOLDFILEUID:NONE\nNEWFILEUID:NONE\n\n<OFX>\n"
        "<BANKTRANLIST>\n<DTSTART>20260901\n<DTEND>20260930\n"
        "<STMTTRN>\n<TRNTYPE>CREDIT\n<DTPOSTED>20260915\n<TRNAMT>300.00\n<FITID>demo-300\n<MEMO>Recebimento cliente\n</STMTTRN>\n"
        "<STMTTRN>\n<TRNTYPE>DEBIT\n<DTPOSTED>20260916\n<TRNAMT>-45.90\n<FITID>demo-tarifa\n<MEMO>TARIFA\n</STMTTRN>\n"
        "</BANKTRANLIST>\n<LEDGERBAL>\n<BALAMT>254.10\n<DTASOF>20260930\n</LEDGERBAL>\n</OFX>\n"
    ).encode("cp1252")
    stored, _status = store_document(
        session,
        preparer,
        file_name="extrato-alfa.ofx",
        media_type="application/x-ofx",
        content=ofx,
        document_type="bank_statement",
        legal_entity_id="le_alfa",
        competence="2026-09",
        source_ref="demo-bank",
        source_type="upload",
    )
    operation = create_statement(session, preparer, account["bank_account_id"], stored["document_id"])
    import_statement(session, "tenant_demo", {"statement_id": operation["statement_id"], "operation_id": operation["operation_id"]})


if __name__ == "__main__":
    seed()
