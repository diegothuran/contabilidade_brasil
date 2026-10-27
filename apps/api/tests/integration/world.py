from __future__ import annotations

import calendar
from datetime import date

from sqlalchemy import text
from sqlalchemy.orm import Session

from contabil.platform.db import session_factory
from contabil.seed.cnpj import cnpj_digits
from contabil.tables import Account, AccountingPeriod, AppUser, ChartOfAccounts, LegalEntity, Membership, Tenant

TABLES = (
    "reconciliation_matches",
    "reconciliation_cases",
    "bank_transactions",
    "bank_statements",
    "bank_accounts",
    "import_rows",
    "import_reports",
    "import_batch_journals",
    "import_batch_files",
    "external_refs",
    "operations",
    "import_batches",
    "document_requests",
    "source_documents",
    "outbox_events",
    "idempotency_keys",
    "audit_events",
    "journal_lines",
    "journal_entries",
    "close_snapshots",
    "close_run_decisions",
    "close_runs",
    "reopen_requests",
    "accounting_periods",
    "cost_centers",
    "accounts",
    "charts_of_accounts",
    "establishments",
    "legal_entities",
    "memberships",
    "app_users",
    "tenants",
)


def reset_world() -> None:
    session = session_factory(admin=True)()
    try:
        session.execute(text(f"TRUNCATE {', '.join(TABLES)} RESTART IDENTITY CASCADE"))
        session.add_all([Tenant(id="tenant_demo", name="Escritório Demo"), Tenant(id="tenant_other", name="Escritório Outro")])
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
        _entity(session, "le_test", "tenant_demo", "Empresa Teste", "100000000001")
        _entity(session, "le_other", "tenant_other", "Empresa Outra", "200000000001")
        session.commit()
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _entity(session: Session, entity_id: str, tenant_id: str, name: str, base: str) -> None:
    session.add(LegalEntity(id=entity_id, tenant_id=tenant_id, name=name, cnpj=cnpj_digits(base), currency="BRL"))
    session.flush()
    session.add(ChartOfAccounts(id=f"chart_{entity_id}", tenant_id=tenant_id, legal_entity_id=entity_id, name="Plano"))
    session.flush()
    session.add(
        Account(
            id=f"{entity_id}-5",
            tenant_id=tenant_id,
            legal_entity_id=entity_id,
            chart_id=f"chart_{entity_id}",
            code="5",
            name="Despesas",
            account_type="expense",
            postable=False,
            active=True,
        )
    )
    session.flush()
    session.add_all(
        [
            Account(
                id=f"{entity_id}-5.1.01",
                tenant_id=tenant_id,
                legal_entity_id=entity_id,
                chart_id=f"chart_{entity_id}",
                parent_id=f"{entity_id}-5",
                code="5.1.01",
                name="Despesas de serviços",
                account_type="expense",
                postable=True,
                active=True,
            ),
            Account(
                id=f"{entity_id}-2.1.01",
                tenant_id=tenant_id,
                legal_entity_id=entity_id,
                chart_id=f"chart_{entity_id}",
                code="2.1.01",
                name="Fornecedores",
                account_type="liability",
                postable=True,
                active=True,
            ),
            Account(
                id=f"{entity_id}-1.1.02",
                tenant_id=tenant_id,
                legal_entity_id=entity_id,
                chart_id=f"chart_{entity_id}",
                code="1.1.02",
                name="Bancos",
                account_type="asset",
                postable=True,
                active=True,
            ),
            Account(
                id=f"{entity_id}-3.1.01",
                tenant_id=tenant_id,
                legal_entity_id=entity_id,
                chart_id=f"chart_{entity_id}",
                code="3.1.01",
                name="Capital social",
                account_type="equity",
                postable=True,
                active=True,
            ),
        ]
    )
    for month in (8, 9):
        last_day = calendar.monthrange(2026, month)[1]
        session.add(
            AccountingPeriod(
                id=f"{entity_id}-2026-{month:02d}",
                tenant_id=tenant_id,
                legal_entity_id=entity_id,
                fiscal_year=2026,
                month=month,
                start_date=date(2026, month, 1),
                end_date=date(2026, month, last_day),
                status="open",
            )
        )

