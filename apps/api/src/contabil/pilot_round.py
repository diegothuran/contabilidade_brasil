"""Prepara a rodada da Fase D com clientes fictícios.

Para cada cliente de teste que as amostras criaram (`cliente-<cenário>`), o comando cria o login no Cognito
com um e-mail fictício e uma senha temporária, sem enviar e-mail, e abre os pedidos de documento da
competência corrente. Pode ser repetido: login e pedido que já existem são preservados.
"""

from __future__ import annotations

import argparse
import secrets
import string
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select

from contabil.bootstrap import bootstrap
from contabil.identity.directory import CognitoDirectory, get_user_directory
from contabil.pilot_samples import PREPARER_ID, _behavior
from contabil.platform.auth import apply_tenant
from contabil.platform.constants import POSTING_PERIOD_STATUSES
from contabil.platform.db import session_factory
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal
from contabil.tables import AccountingPeriod, DocumentRequest, LegalEntity, Membership, Tenant

MONTHS = (
    "janeiro", "fevereiro", "março", "abril", "maio", "junho",
    "julho", "agosto", "setembro", "outubro", "novembro", "dezembro",
)

# Prazo dos pedidos da rodada, contado a partir do dia em que o comando roda.
DUE_IN_DAYS = 7

_SYMBOLS = "!#$%&*+-=?@"


def temporary_password(length: int = 16) -> str:
    """Senha temporária com maiúscula, minúscula, dígito e símbolo, como a política padrão do Cognito pede."""
    pools = (string.ascii_uppercase, string.ascii_lowercase, string.digits, _SYMBOLS)
    chars = [secrets.choice(pool) for pool in pools]
    everything = "".join(pools)
    chars += [secrets.choice(everything) for _ in range(length - len(chars))]
    secrets.SystemRandom().shuffle(chars)
    return "".join(chars)


def fictitious_email(user_id: str, tenant_id: str) -> str:
    """E-mail no domínio reservado example.com (RFC 2606): não pertence a ninguém e não recebe nada."""
    return f"{user_id}.{tenant_id}@example.com".lower()


def round_requests(story: str, month: int) -> list[tuple[str, str]]:
    """Pedidos da rodada por cenário: tipo de documento e título."""
    name = MONTHS[month - 1]
    extra = {
        "andamento": ("invoice", f"Rodada: notas fiscais de compra de {name}"),
        "fechada": ("invoice", f"Rodada: notas fiscais de serviço emitidas em {name}"),
        "banco": ("receipt", f"Rodada: comprovantes de pagamento a fornecedores de {name}"),
        "vazia": ("contract", "Rodada: contrato social e última alteração"),
        "rascunhos": ("receipt", f"Rodada: recibos de frete e pedágio de {name}"),
    }
    items = [("bank_statement", f"Rodada: extrato bancário de {name}")]
    behavior = _behavior(story)
    if behavior in extra:
        items.append(extra[behavior])
    return items


@dataclass
class ClientLogin:
    user_id: str
    company: str
    email: str
    password: str | None
    requests_opened: int


@dataclass
class RoundResult:
    logins: list[ClientLogin] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def prepare_round(tenant_id: str, directory: CognitoDirectory, today: date | None = None) -> RoundResult:
    today = today or date.today()
    result = RoundResult()
    session = session_factory(admin=True)()
    try:
        apply_tenant(session, tenant_id)
        tenant = session.get(Tenant, tenant_id)
        if tenant is None:
            raise ValueError(f"Escritório {tenant_id} não existe.")
        tenant_name = tenant.name
        session.commit()
        bootstrap(tenant_id, tenant_name, PREPARER_ID, "Preparador do piloto", ["preparer"])
        preparer = Principal(PREPARER_ID, tenant_id, frozenset({"preparer"}), "Preparador do piloto", tenant_name)
        apply_tenant(session, tenant_id)
        rows = session.execute(
            select(Membership.user_id, Membership.legal_entity_id, LegalEntity.name)
            .join(LegalEntity, LegalEntity.id == Membership.legal_entity_id)
            .where(Membership.tenant_id == tenant_id, Membership.user_id.like("cliente-%"))
            .order_by(LegalEntity.name)
        ).all()
        if not rows:
            raise ValueError("Nenhum cliente de teste. Rode antes o comando das empresas de teste.")
        for user_id, entity_id, company in rows:
            opened = _open_requests(session, preparer, entity_id, company, user_id.removeprefix("cliente-"), today, result.notes)
            session.commit()
            email = fictitious_email(user_id, tenant_id)
            password = temporary_password()
            try:
                created = directory.create_test_login(user_id, email, tenant_id, password)
            except DomainError as exc:
                result.notes.append(f"{company}: login não criado ({exc.detail})")
                created = False
            result.logins.append(ClientLogin(user_id, company, email, password if created else None, opened))
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _open_requests(
    session, preparer: Principal, entity_id: str, company: str, story: str, today: date, notes: list[str]
) -> int:
    from contabil.document_requests.service import create_request

    apply_tenant(session, preparer.tenant_id)
    period_id = f"{entity_id}-{today.year}-{today.month:02d}"
    period = session.get(AccountingPeriod, period_id)
    if period is None or period.status not in POSTING_PERIOD_STATUSES:
        notes.append(f"{company}: competência {today.month:02d}/{today.year} indisponível, nenhum pedido aberto")
        return 0
    opened = 0
    for document_type, title in round_requests(story, today.month):
        existing = session.scalar(
            select(DocumentRequest.id).where(
                DocumentRequest.tenant_id == preparer.tenant_id,
                DocumentRequest.legal_entity_id == entity_id,
                DocumentRequest.period_id == period_id,
                DocumentRequest.title == title,
            )
        )
        if existing is not None:
            continue
        try:
            create_request(
                session,
                preparer,
                legal_entity_id=entity_id,
                period_id=period_id,
                document_type=document_type,
                title=title,
                due_on=today + timedelta(days=DUE_IN_DAYS),
            )
            opened += 1
        except DomainError as exc:
            notes.append(f"{company}: pedido \"{title}\" não aberto ({exc.detail})")
    return opened


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Cria o login fictício dos clientes de teste e abre os pedidos da competência.")
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args(argv)
    directory = get_user_directory()
    if not isinstance(directory, CognitoDirectory):
        raise SystemExit("Diretório de usuários não configurado: faltam as chaves do Cognito na API.")
    try:
        result = prepare_round(args.tenant_id, directory)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for login in result.logins:
        secret = f"senha_temporaria={login.password}" if login.password else "login ja existia (senha mantida)"
        print(f"{login.company} usuario={login.user_id} email={login.email} {secret} pedidos_novos={login.requests_opened}")
    for note in result.notes:
        print(f"nota {note}")


if __name__ == "__main__":
    main(sys.argv[1:])
