"""Simula a rodada da Fase D com os cinco clientes fictícios.

Cada cliente de teste segue um roteiro fixo, escrito aqui, sobre os pedidos que `contabil.pilot_round` abriu:
o pontual, o que troca o arquivo, o que pergunta antes, o que não responde e o que manda pelo envio avulso.
O escritório responde com o preparador e o aprovador fictícios das amostras. Tudo passa pelas mesmas
funções de serviço da API, então a trilha de auditoria e o `pilot_report` enxergam a simulação como uma
rodada. Os horários são os da execução: a simulação não inventa prazo nem data passada.

A simulação exercita o fluxo e gera dado para o relatório. Ela não substitui cliente real: o critério da
Fase D (o fluxo dispensa a planilha paralela) continua sendo decisão do contador.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass, field
from datetime import date, timedelta

from sqlalchemy import select

from contabil.bootstrap import bootstrap
from contabil.pilot_round import round_requests
from contabil.pilot_samples import APPROVER_ID, PREPARER_ID, _behavior, storage_configured
from contabil.platform.auth import apply_tenant
from contabil.platform.db import session_factory
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal
from contabil.tables import DocumentRequest, DocumentRequestComment, DocumentRequestFile, LegalEntity, Membership, Tenant

MARK = "[simulação]"

# Roteiro por cenário. "extrato" é o pedido do extrato bancário; "ramo" é o segundo pedido da rodada.
# Passos: (ator, ação, pedido, texto ou nome do arquivo, conteúdo).
PERSONAS: dict[str, tuple[str, list[tuple]]] = {
    "andamento": (
        "Pontual",
        [
            ("client", "upload", "extrato", "extrato-novembro.txt", "Extrato fictício da conta corrente, novembro."),
            ("client", "upload", "ramo", "notas-compra-novembro.txt", "Notas fictícias de compra de farinha e embalagens."),
            ("office", "confirm", "extrato"),
            ("office", "confirm", "ramo"),
        ],
    ),
    "fechada": (
        "Troca o arquivo",
        [
            ("client", "upload", "extrato", "extrato-outubro.txt", "Extrato fictício de OUTUBRO (mês errado)."),
            ("office", "return", "extrato", "O extrato enviado é de outubro. Precisamos do extrato de novembro."),
            ("client", "comment", "extrato", "Peguei o mês errado. Segue o de novembro."),
            ("client", "upload", "extrato", "extrato-novembro.txt", "Extrato fictício da conta corrente, novembro."),
            ("office", "confirm", "extrato"),
            ("client", "upload", "ramo", "notas-servico-novembro.txt", "Notas fictícias de serviço emitidas em novembro."),
            ("office", "confirm", "ramo"),
        ],
    ),
    "banco": (
        "Pergunta antes de enviar",
        [
            ("client", "comment", "extrato", "Mando também o extrato da aplicação ou só o da conta corrente?"),
            ("office", "comment", "extrato", "Só o da conta corrente PJ. A aplicação pedimos no fim do trimestre."),
            ("client", "upload", "extrato", "extrato-conta-corrente-novembro.txt", "Extrato fictício da conta corrente PJ."),
        ],
    ),
    "vazia": ("Não responde", []),
    "rascunhos": (
        "Manda pelo envio avulso",
        [
            ("client", "submission", None, "recibos-pedagio-novembro.txt", "Recibos fictícios de pedágio e frete."),
            ("client", "comment", "ramo", "Mandei os recibos pelo envio avulso, não achei onde anexar aqui."),
            ("office", "classify", None, "Rodada: recibos de frete e pedágio (envio avulso)"),
            ("office", "cancel", "ramo", "Os recibos chegaram pelo envio avulso e foram classificados em outro pedido."),
            ("office", "confirm", "classified"),
            ("client", "upload", "extrato", "extrato-novembro.txt", "Extrato fictício da conta corrente, novembro."),
            ("office", "confirm", "extrato"),
        ],
    ),
}


@dataclass
class SimulatedClient:
    company: str
    persona: str
    steps_done: int
    skipped: bool = False


@dataclass
class SimulationResult:
    clients: list[SimulatedClient] = field(default_factory=list)
    notes: list[str] = field(default_factory=list)


def persona_for(story: str) -> tuple[str, list[tuple]]:
    return PERSONAS.get(_behavior(story), ("Sem roteiro", []))


def simulate_round(tenant_id: str, today: date | None = None) -> SimulationResult:
    today = today or date.today()
    if not storage_configured():
        raise ValueError("A simulação envia arquivos: configure o bucket do storage antes.")
    result = SimulationResult()
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
        office = {
            "preparer": Principal(PREPARER_ID, tenant_id, frozenset({"preparer"}), "Preparador do piloto", tenant_name),
            "approver": Principal(APPROVER_ID, tenant_id, frozenset({"approver"}), "Aprovador do piloto", tenant_name),
        }
        apply_tenant(session, tenant_id)
        rows = session.execute(
            select(Membership.user_id, Membership.legal_entity_id, LegalEntity.name)
            .join(LegalEntity, LegalEntity.id == Membership.legal_entity_id)
            .where(Membership.tenant_id == tenant_id, Membership.user_id.like("cliente-%"))
            .order_by(LegalEntity.name)
        ).all()
        if not rows:
            raise ValueError("Nenhum cliente de teste. Rode antes as amostras e o contabil.pilot_round.")
        for user_id, entity_id, company in rows:
            story = user_id.removeprefix("cliente-")
            persona, steps = persona_for(story)
            client = Principal(user_id, tenant_id, frozenset({"client"}), f"Cliente de teste {company}"[:200], tenant_name, legal_entity_id=entity_id)
            outcome = _simulate_client(session, office, client, entity_id, company, story, steps, today, result.notes)
            outcome.persona = persona
            result.clients.append(outcome)
        return result
    except Exception:
        session.rollback()
        raise
    finally:
        session.close()


def _round_rows(session, tenant_id: str, entity_id: str, story: str, today: date) -> dict[str, DocumentRequest]:
    period_id = f"{entity_id}-{today.year}-{today.month:02d}"
    titles = round_requests(story, today.month)
    keys = ["extrato", "ramo"]
    found: dict[str, DocumentRequest] = {}
    for key, (_type, title) in zip(keys, titles):
        row = session.scalar(
            select(DocumentRequest).where(
                DocumentRequest.tenant_id == tenant_id,
                DocumentRequest.legal_entity_id == entity_id,
                DocumentRequest.period_id == period_id,
                DocumentRequest.title == title,
            )
        )
        if row is not None:
            found[key] = row
    return found


def _already_touched(session, tenant_id: str, rows: dict[str, DocumentRequest]) -> bool:
    ids = [row.id for row in rows.values()]
    if not ids:
        return False
    if any(row.status != "open" for row in rows.values()):
        return True
    has_file = session.scalar(
        select(DocumentRequestFile.id).where(DocumentRequestFile.tenant_id == tenant_id, DocumentRequestFile.request_id.in_(ids)).limit(1)
    )
    has_comment = session.scalar(
        select(DocumentRequestComment.id).where(DocumentRequestComment.tenant_id == tenant_id, DocumentRequestComment.request_id.in_(ids)).limit(1)
    )
    return bool(has_file or has_comment)


def _simulate_client(
    session,
    office: dict[str, Principal],
    client: Principal,
    entity_id: str,
    company: str,
    story: str,
    steps: list[tuple],
    today: date,
    notes: list[str],
) -> SimulatedClient:
    from contabil.document_requests.service import add_comment, cancel_request, confirm_request, receive_content, return_request
    from contabil.submissions.service import classify_submission, create_submission

    tenant_id = client.tenant_id
    apply_tenant(session, tenant_id)
    rows = _round_rows(session, tenant_id, entity_id, story, today)
    outcome = SimulatedClient(company, "", 0)
    if steps and len(rows) < 2:
        notes.append(f"{company}: pedidos da rodada não encontrados; rode antes o contabil.pilot_round")
        outcome.skipped = True
        return outcome
    if _already_touched(session, tenant_id, rows):
        outcome.skipped = True
        return outcome
    ids = {key: row.id for key, row in rows.items()}
    submission_id: str | None = None
    for step in steps:
        actor, action = step[0], step[1]
        apply_tenant(session, tenant_id)
        try:
            if action == "upload":
                _key, file_name, body = step[2], step[3], step[4]
                receive_content(
                    session, client, ids[_key], file_name=file_name, media_type="text/plain",
                    content=f"{MARK} {body}\nDocumento fictício, sem valor fiscal.\n".encode(),
                )
            elif action == "comment":
                author = client if actor == "client" else office["preparer"]
                add_comment(session, author, ids[step[2]], f"{MARK} {step[3]}")
            elif action == "return":
                return_request(session, office["approver"], ids[step[2]], f"{MARK} {step[3]}")
            elif action == "confirm":
                confirm_request(session, office["approver"], ids[step[2]])
            elif action == "cancel":
                cancel_request(session, office["preparer"], ids[step[2]], f"{MARK} {step[3]}")
            elif action == "submission":
                created = create_submission(
                    session, client, file_name=step[3], media_type="text/plain",
                    content=f"{MARK} {step[4]}\nDocumento fictício, sem valor fiscal.\n".encode(),
                    note=f"{MARK} Não achei onde anexar no pedido, mando por aqui.",
                )
                submission_id = created["submission_id"]
            elif action == "classify":
                if submission_id is None:
                    raise DomainError(409, "Sem envio", "O roteiro classifica um envio que não foi criado.")
                classified = classify_submission(
                    session, office["preparer"], submission_id,
                    period_id=f"{entity_id}-{today.year}-{today.month:02d}", document_type="receipt",
                    title=step[3], due_on=today + timedelta(days=7),
                )
                ids["classified"] = classified["document_request_id"]
            session.commit()
            outcome.steps_done += 1
        except DomainError as exc:
            session.rollback()
            notes.append(f"{company}: passo {action} parou ({exc.detail})")
            break
    return outcome


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Simula a rodada da Fase D com os cinco clientes fictícios.")
    parser.add_argument("--tenant-id", required=True)
    args = parser.parse_args(argv)
    try:
        result = simulate_round(args.tenant_id)
    except ValueError as exc:
        raise SystemExit(str(exc)) from exc
    for item in result.clients:
        state = "ja simulado" if item.skipped else f"passos={item.steps_done}"
        print(f"{item.company} perfil=\"{item.persona}\" {state}")
    for note in result.notes:
        print(f"nota {note}")


if __name__ == "__main__":
    main(sys.argv[1:])
