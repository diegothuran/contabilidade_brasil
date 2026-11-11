"""Prévia da EFD-Reinf série R-4000 de uma competência (ADR 032, POC).

Monta um R-4020 por beneficiário pessoa jurídica, um R-4010 por beneficiário pessoa física e um R-4099 de
fechamento, a partir dos pagamentos com retenção informados pelo escritório. Valida cada evento contra o
XSD oficial guardado sem modificação no registry e entrega um zip com os XMLs **sem assinatura**, mais um
LEIA-ME. Não assina, não lê certificado, não monta lote e não transmite.

O XSD oficial exige `ds:Signature`. A validação usa uma cópia em memória do evento com um `<Signature/>`
vazio como marcador e troca o import `./xmldsig-core-schema.xsd` por um schema auxiliar próprio e mínimo
(`data/reinf/xmldsig-marcador-previa.xsd`). O XML do zip sai sem o marcador.
"""

from __future__ import annotations

import hashlib
import io
import threading
import zipfile
from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from decimal import Decimal
from functools import lru_cache

from lxml import etree
from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.platform.clock import BRASILIA
from contabil.platform.errors import DomainError
from contabil.regulatory.registry import DATA, IncomeNatureTable, reinf_natures
from contabil.signatories.service import signatories_for
from contabil.tables import AccountingPeriod, WithholdingPayment
from contabil.tenancy.service import normalize_cnpj, require_entity, valid_cnpj
from contabil.withholdings.validators import CleanPayment, PaymentInput, payment_problems

LAYOUT_VERSION = "2.1.2"
NOTICE = "Prévia para conferência. Não assinar nem transmitir."
REINF_DATA = DATA / "reinf"
XSD_DIR = REINF_DATA / "v2_01_02"
SIGNATURE_STUB = REINF_DATA / "xmldsig-marcador-previa.xsd"
DSIG = "http://www.w3.org/2000/09/xmldsig#"
_NS_BASE = "http://www.reinf.esocial.gov.br/schemas"
EVENTS = {
    "R-4010": {"xsd": "R-4010-evt4010PagtoBeneficiarioPF-v2_01_02.xsd", "ns": f"{_NS_BASE}/evt4010PagtoBeneficiarioPF/v2_01_02", "root": "evtRetPF"},
    "R-4020": {"xsd": "R-4020-evt4020PagtoBeneficiarioPJ-v2_01_02.xsd", "ns": f"{_NS_BASE}/evt4020PagtoBeneficiarioPJ/v2_01_02", "root": "evtRetPJ"},
    "R-4099": {"xsd": "R-4099-evt4099FechamentoDirf-v2_01_02.xsd", "ns": f"{_NS_BASE}/evt4099FechamentoDirf/v2_01_02", "root": "evtFech"},
}
EVENT_KINDS = tuple(EVENTS)
# Ambiente 2 (produção restrita): a prévia nunca se parece com um arquivo de produção.
TP_AMB = "2"
# 1 = aplicativo do contribuinte.
PROC_EMI = "1"
# 1 = CNPJ.
TP_INSC = "1"
# 0 = fechamento.
FECH_RET = "0"
CENT = Decimal("0.01")
README_NAME = "LEIA-ME.txt"


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str
    event: str | None = None
    fix: str | None = None

    def as_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class Responsible:
    """Quem responde pelas informações no R-4099 (ideRespInf): o representante legal da ADR 030."""

    name: str
    cpf: str
    phone: str | None = None
    email: str | None = None


@dataclass(frozen=True)
class ReinfEvent:
    kind: str
    file_name: str
    event_id: str
    xml: bytes


@dataclass
class ReinfPreview:
    content: bytes
    issues: list[Issue]
    counts: dict[str, int]
    checks: dict[str, bool | None]
    file_name: str
    competence: str
    events: list[ReinfEvent] = field(default_factory=list)
    layout_version: str = LAYOUT_VERSION
    notice: str = NOTICE

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.content).hexdigest()


# Valores, identificadores e nomes


def format_value(value: Decimal) -> str:
    """Valor do XSD: vírgula decimal, duas casas, sem separador de milhar (`[0-9]{1,12}[,][0-9]{2}`)."""
    return format(Decimal(value).quantize(CENT), "f").replace(".", ",")


def contributor_number(cnpj: str) -> str:
    """`ideContri/nrInsc`: a raiz de 8 posições do CNPJ (tpInsc 1), em caixa alta."""
    return normalize_cnpj(cnpj)[:8]


def event_id(cnpj: str, generated_at: datetime, sequence: int) -> str:
    """`ID` + tpInsc + nrInsc completado com zeros à direita até 14 + AAAAMMDDHHMMSS + sequência de 5 dígitos.

    Anexo II do leiaute 2.1.2b (REGRA_VALIDA_ID_EVENTO): a inscrição do id é a mesma do `ideContri/nrInsc`,
    a raiz de 8 posições, completada com zeros à direita. O XSD de 23/09/2026 aceita zeros à esquerda ou à
    direita (`ID[0-9][0-9A-Z]{14}[0-9]{19}`); à direita sempre foi aceito.
    """
    if not 1 <= sequence <= 99999:
        raise ValueError("a sequência do id vai de 1 a 99999")
    number = contributor_number(cnpj).ljust(14, "0")
    return f"ID{TP_INSC}{number}{generated_at.strftime('%Y%m%d%H%M%S')}{sequence:05d}"


def preview_file_name(cnpj: str, year: int, month: int) -> str:
    return f"REINF-R4000-PREVIA-{cnpj}-{year:04d}{month:02d}.zip"


def app_version() -> str:
    try:
        from importlib.metadata import version

        return version("contabil")
    except Exception:  # pragma: no cover - pacote sem metadados
        return "0.1.0"


def ver_proc() -> str:
    return f"contabil-{app_version()}"[:20]


# Agrupamento


@dataclass(frozen=True)
class BeneficiaryGroup:
    kind: str
    document: str
    natures: tuple[tuple[str, tuple[CleanPayment, ...]], ...]


def group_payments(payments: list[CleanPayment]) -> tuple[list[BeneficiaryGroup], list[BeneficiaryGroup]]:
    """Um evento por beneficiário (MOU 2.1.2.1, p. 106), com um `idePgto` por natureza e um `infoPgto` por pagamento.

    Devolve (pessoas físicas, pessoas jurídicas), cada lista em ordem de documento.
    """
    grouped: dict[tuple[str, str], dict[str, list[CleanPayment]]] = defaultdict(lambda: defaultdict(list))
    for payment in payments:
        grouped[(payment.beneficiary_kind, payment.beneficiary_document)][payment.nature_code].append(payment)
    groups = [
        BeneficiaryGroup(
            kind=kind,
            document=document,
            natures=tuple(
                (code, tuple(sorted(items, key=lambda item: item.payment_date)))
                for code, items in sorted(by_nature.items())
            ),
        )
        for (kind, document), by_nature in sorted(grouped.items())
    ]
    return [group for group in groups if group.kind == "pf"], [group for group in groups if group.kind == "pj"]


# Montagem do XML


def _sub(parent, tag: str, text: str | None = None):
    element = etree.SubElement(parent, tag)
    if text is not None:
        element.text = text
    return element


def _event_root(kind: str, identifier: str):
    spec = EVENTS[kind]
    root = etree.Element(f"{{{spec['ns']}}}Reinf", nsmap={None: spec["ns"]})
    event = etree.SubElement(root, f"{{{spec['ns']}}}{spec['root']}")
    event.set("id", identifier)
    return root, event, spec["ns"]


def _q(ns: str, name: str) -> str:
    return f"{{{ns}}}{name}"


def _ide_evento(event, ns: str, competence: str, *, with_retif: bool) -> None:
    ide = etree.SubElement(event, _q(ns, "ideEvento"))
    if with_retif:
        _sub(ide, _q(ns, "indRetif"), "1")
    _sub(ide, _q(ns, "perApur"), competence)
    _sub(ide, _q(ns, "tpAmb"), TP_AMB)
    _sub(ide, _q(ns, "procEmi"), PROC_EMI)
    _sub(ide, _q(ns, "verProc"), ver_proc())


def _ide_contri(event, ns: str, cnpj: str) -> None:
    ide = etree.SubElement(event, _q(ns, "ideContri"))
    _sub(ide, _q(ns, "tpInsc"), TP_INSC)
    _sub(ide, _q(ns, "nrInsc"), contributor_number(cnpj))


def _serialize(root) -> bytes:
    return etree.tostring(root, xml_declaration=True, encoding="UTF-8", pretty_print=True)


def payment_event(kind: str, cnpj: str, competence: str, group: BeneficiaryGroup, identifier: str) -> bytes:
    """R-4020 (pessoa jurídica) ou R-4010 (pessoa física) de um beneficiário."""
    root, event, ns = _event_root(kind, identifier)
    _ide_evento(event, ns, competence, with_retif=True)
    _ide_contri(event, ns, cnpj)
    estab = etree.SubElement(event, _q(ns, "ideEstab"))
    _sub(estab, _q(ns, "tpInscEstab"), TP_INSC)
    _sub(estab, _q(ns, "nrInscEstab"), normalize_cnpj(cnpj))
    benef = etree.SubElement(estab, _q(ns, "ideBenef"))
    # O nome só vai no XML quando não há CNPJ/CPF (beneficiário no exterior), o que a prévia não cobre.
    _sub(benef, _q(ns, "cnpjBenef" if kind == "R-4020" else "cpfBenef"), group.document)
    for code, payments in group.natures:
        pgto = etree.SubElement(benef, _q(ns, "idePgto"))
        _sub(pgto, _q(ns, "natRend"), code)
        for payment in payments:
            info = etree.SubElement(pgto, _q(ns, "infoPgto"))
            _sub(info, _q(ns, "dtFG"), payment.payment_date.isoformat())
            if kind == "R-4020":
                _sub(info, _q(ns, "vlrBruto"), format_value(payment.gross_amount))
                values = [
                    ("vlrBaseIR", payment.ir_base),
                    ("vlrIR", payment.ir_amount),
                    ("vlrBaseAgreg", payment.csrf_base),
                    ("vlrAgreg", payment.csrf_amount),
                ]
                if any(value is not None for _, value in values):
                    retencoes = etree.SubElement(info, _q(ns, "retencoes"))
                    for name, value in values:
                        if value is not None:
                            _sub(retencoes, _q(ns, name), format_value(value))
            else:
                _sub(info, _q(ns, "vlrRendBruto"), format_value(payment.gross_amount))
                if payment.ir_base is not None:
                    _sub(info, _q(ns, "vlrRendTrib"), format_value(payment.ir_base))
                if payment.ir_amount is not None:
                    _sub(info, _q(ns, "vlrIR"), format_value(payment.ir_amount))
    return _serialize(root)


def closing_event(cnpj: str, competence: str, responsible: Responsible | None, identifier: str) -> bytes:
    """R-4099 com fechRet = 0 (fechamento)."""
    root, event, ns = _event_root("R-4099", identifier)
    _ide_evento(event, ns, competence, with_retif=False)
    _ide_contri(event, ns, cnpj)
    if responsible is not None:
        resp = etree.SubElement(event, _q(ns, "ideRespInf"))
        _sub(resp, _q(ns, "nmResp"), responsible.name)
        _sub(resp, _q(ns, "cpfResp"), responsible.cpf)
        if responsible.phone:
            _sub(resp, _q(ns, "telefone"), responsible.phone)
        if responsible.email:
            _sub(resp, _q(ns, "email"), responsible.email)
    info = etree.SubElement(event, _q(ns, "infoFech"))
    _sub(info, _q(ns, "fechRet"), FECH_RET)
    return _serialize(root)


def build_events(
    *,
    cnpj: str,
    year: int,
    month: int,
    payments: list[CleanPayment],
    responsible: Responsible | None,
    generated_at: datetime,
) -> list[ReinfEvent]:
    """R-4010, depois R-4020, depois o R-4099. Sem pagamento, nenhum evento (o R-4099 pede um R-4000 no período)."""
    if not payments:
        return []
    competence = f"{year:04d}-{month:02d}"
    people, companies = group_payments(payments)
    events: list[ReinfEvent] = []
    sequence = 0
    for kind, groups in (("R-4010", people), ("R-4020", companies)):
        for index, group in enumerate(groups, start=1):
            sequence += 1
            identifier = event_id(cnpj, generated_at, sequence)
            events.append(ReinfEvent(kind, f"{kind}-{index:03d}.xml", identifier, payment_event(kind, cnpj, competence, group, identifier)))
    sequence += 1
    identifier = event_id(cnpj, generated_at, sequence)
    events.append(ReinfEvent("R-4099", "R-4099-001.xml", identifier, closing_event(cnpj, competence, responsible, identifier)))
    return events


# Validação contra o XSD oficial


class _SignatureStubResolver(etree.Resolver):
    """Troca o import `./xmldsig-core-schema.xsd` dos XSDs oficiais pelo schema auxiliar próprio."""

    def resolve(self, url, pubid, context):
        if url and url.replace("\\", "/").rsplit("/", 1)[-1] == "xmldsig-core-schema.xsd":
            return self.resolve_filename(str(SIGNATURE_STUB), context)
        return None


_VALIDATION_LOCK = threading.Lock()


def _safe_parser() -> etree.XMLParser:
    return etree.XMLParser(no_network=True, resolve_entities=False, load_dtd=False, huge_tree=False)


@lru_cache(maxsize=len(EVENTS))
def _schema(kind: str) -> etree.XMLSchema:
    parser = _safe_parser()
    parser.resolvers.add(_SignatureStubResolver())
    document = etree.parse(str(XSD_DIR / EVENTS[kind]["xsd"]), parser)
    return etree.XMLSchema(document)


def xsd_errors(kind: str, xml: bytes) -> list[str]:
    """Erros do XSD oficial para um evento sem assinatura. Lista vazia quando o evento valida."""
    try:
        root = etree.fromstring(xml, parser=_safe_parser())
    except etree.XMLSyntaxError as exc:
        return [f"XML malformado: {exc}"]
    etree.SubElement(root, f"{{{DSIG}}}Signature", nsmap={None: DSIG})
    schema = _schema(kind)
    with _VALIDATION_LOCK:
        if schema.validate(root):
            return []
        return [f"linha {error.line}: {error.message}" for error in schema.error_log]


# Pacote


def readme_text(competence: str, cnpj: str, events: list[ReinfEvent]) -> str:
    lines = [
        "PRÉVIA DA EFD-REINF SÉRIE R-4000 - NÃO ASSINAR NEM TRANSMITIR",
        "",
        f"Empresa (CNPJ): {cnpj}",
        f"Competência (perApur): {competence}",
        f"Leiaute: {LAYOUT_VERSION} (XSD v2_01_02, pacote oficial de 23/09/2026)",
        "",
        "Este pacote é uma prévia para conferência. Os XMLs saem SEM assinatura digital.",
        "O XSD oficial exige o elemento ds:Signature; por isso nenhum destes arquivos passa no XSD como está,",
        "e nenhum deve ser enviado à Receita. A plataforma validou cada evento contra o XSD oficial numa cópia",
        "com um marcador de assinatura vazio.",
        "",
        "tpAmb = 2 (produção restrita). O envio, mesmo à produção restrita, exige o certificado ICP-Brasil",
        "do próprio CNPJ e fica fora desta prévia.",
        "",
        "Eventos:",
    ]
    lines.extend(f"- {event.file_name}: {event.kind}, id {event.event_id}" for event in events)
    if not events:
        lines.append("- nenhum: a competência não tem pagamento com retenção.")
    return "\r\n".join(lines) + "\r\n"


def package(events: list[ReinfEvent], readme: str, generated_at: datetime) -> bytes:
    """Zip com um XML por evento e o LEIA-ME. A data dos arquivos é a da geração, para o hash ser reproduzível."""
    stamp = generated_at.timetuple()[:6]
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr(zipfile.ZipInfo(README_NAME, date_time=stamp), readme.encode("utf-8"), compress_type=zipfile.ZIP_DEFLATED)
        for event in events:
            archive.writestr(zipfile.ZipInfo(event.file_name, date_time=stamp), event.xml, compress_type=zipfile.ZIP_DEFLATED)
    return buffer.getvalue()


# Pendências fixas


def fixed_notes() -> list[Issue]:
    return [
        Issue("out_of_scope_ir_ledger", "out_of_scope", "A conferência do IR retido com o razão fica fora: o plano de contas mínimo não tem conta de IRRF a recolher.", None, None),
        Issue("out_of_scope_signature", "out_of_scope", "Os eventos saem sem assinatura e sem lote. O envio, mesmo à produção restrita, exige o certificado ICP-Brasil da própria empresa.", None, None),
        Issue("assumption_dtfg", "assumption", "A data do fato gerador (dtFG) é a data do pagamento. Para o IR de pessoa jurídica o fato gerador é o pagamento ou o crédito, o que vier primeiro.", None, "withholding_payments"),
        Issue("assumption_r1000", "assumption", "A prévia supõe que o R-1000 da empresa já foi enviado; ela não gera o R-1000.", None, None),
        Issue("assumption_csrf_aggregated", "assumption", "A CSRF vai agregada (vlrBaseAgreg e vlrAgreg), sem separar CSLL, Cofins e PIS/Pasep.", "R-4020", "withholding_payments"),
        Issue("assumption_simples", "assumption", "A prévia não confere se o beneficiário é optante do Simples Nacional, que dispensa a retenção da CSRF (Lei 10.833/2003, art. 32).", "R-4020", "withholding_payments"),
        Issue("assumption_matriz", "assumption", "Os pagamentos saem centralizados no estabelecimento matriz (ideEstab com o CNPJ da empresa).", None, "legal_entity"),
    ]


# Montagem a partir do banco


def _clean_from_row(row: WithholdingPayment, period: AccountingPeriod, table: IncomeNatureTable) -> tuple[CleanPayment | None, list[dict]]:
    def text(value: Decimal | None) -> str | None:
        return None if value is None else format(Decimal(value), "f")

    return payment_problems(
        PaymentInput(
            beneficiary_kind=row.beneficiary_kind,
            beneficiary_document=row.beneficiary_document,
            beneficiary_name=row.beneficiary_name,
            nature_code=row.nature_code,
            payment_date=row.payment_date,
            gross_amount=text(row.gross_amount),
            ir_base=text(row.ir_base),
            ir_amount=text(row.ir_amount),
            csrf_base=text(row.csrf_base),
            csrf_amount=text(row.csrf_amount),
            description=row.description,
        ),
        period_start=period.start_date,
        period_end=period.end_date,
        table=table,
    )


def payment_issues(rows: list[WithholdingPayment], period: AccountingPeriod, cnpj: str, table: IncomeNatureTable) -> tuple[list[CleanPayment], list[Issue]]:
    """Confere de novo cada pagamento gravado. O que não passa fica fora dos eventos e vira pendência."""
    clean: list[CleanPayment] = []
    issues: list[Issue] = []
    declarant = normalize_cnpj(cnpj)
    for row in rows:
        payment, errors = _clean_from_row(row, period, table)
        label = f"Pagamento de {row.payment_date.strftime('%d/%m/%Y')} ({format_value(row.gross_amount)})"
        if payment is None:
            for error in errors:
                field_name = error["loc"][0]
                code = "nature_outside_table" if field_name == "nature_code" else "payment_invalid"
                issues.append(Issue(code, "blocker", f"{label}: {error['msg']} Ele ficou fora dos eventos.", "R-4020" if row.beneficiary_kind == "pj" else "R-4010", "withholding_payments"))
            continue
        clean.append(payment)
        if payment.beneficiary_kind == "pj" and payment.beneficiary_document == declarant:
            issues.append(Issue("beneficiary_is_declarant", "warning", f"{label}: o beneficiário é a própria empresa. O leiaute só aceita isso em casos de exceção.", "R-4020", "withholding_payments"))
    not_withheld_ir = sum(1 for payment in clean if payment.ir_base is not None and payment.ir_amount is None)
    if not_withheld_ir:
        issues.append(Issue("ir_not_withheld", "warning", f"{not_withheld_ir} pagamento(s) com base do IR e sem valor retido. A prévia supõe retenção dispensada (até R$ 10,00) e deixa vlrIR vazio.", None, "withholding_payments"))
    not_withheld_csrf = sum(1 for payment in clean if payment.csrf_base is not None and payment.csrf_amount is None)
    if not_withheld_csrf:
        issues.append(Issue("csrf_not_withheld", "warning", f"{not_withheld_csrf} pagamento(s) com base da CSRF e sem valor retido. A prévia deixa vlrAgreg vazio.", "R-4020", "withholding_payments"))
    return clean, issues


def build_reinf_preview(
    session: Session,
    tenant_id: str,
    legal_entity_id: str,
    period_id: str,
    *,
    now: datetime | None = None,
) -> ReinfPreview:
    entity = require_entity(session, tenant_id, legal_entity_id)
    period = session.scalar(
        select(AccountingPeriod).where(
            AccountingPeriod.id == period_id,
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.legal_entity_id == entity.id,
        )
    )
    if period is None:
        raise DomainError(404, "Não encontrado", "Período não encontrado.")
    generated_at = (now or datetime.now(timezone.utc)).astimezone(BRASILIA).replace(microsecond=0)
    competence = f"{period.fiscal_year:04d}-{period.month:02d}"
    cnpj = normalize_cnpj(entity.cnpj)
    table = reinf_natures()
    issues: list[Issue] = []

    rows = list(
        session.scalars(
            select(WithholdingPayment)
            .where(
                WithholdingPayment.tenant_id == tenant_id,
                WithholdingPayment.legal_entity_id == entity.id,
                WithholdingPayment.period_id == period.id,
            )
            .order_by(WithholdingPayment.payment_date, WithholdingPayment.created_at, WithholdingPayment.id)
        ).all()
    )
    payments, found = payment_issues(rows, period, cnpj, table)
    issues.extend(found)
    if not rows:
        issues.append(Issue("no_payments", "blocker", "A competência não tem pagamento com retenção. Nenhum evento foi gerado.", None, "withholding_payments"))

    responsible: Responsible | None = None
    signatories = signatories_for(session, tenant_id, entity.id)
    representative = signatories.legal_representative if signatories else None
    if representative is None:
        issues.append(Issue("legal_rep_missing", "blocker", "A empresa não tem representante legal cadastrado. O R-4099 sai sem ideRespInf, que o leiaute exige quando o contribuinte é pessoa jurídica.", "R-4099", "signatories"))
    elif not representative.cpf:
        issues.append(Issue("legal_rep_cpf_missing", "blocker", "O representante legal não tem CPF cadastrado. O R-4099 sai sem ideRespInf.", "R-4099", "signatories"))
    else:
        responsible = Responsible(name=representative.name, cpf=representative.cpf)
        issues.append(Issue("responsible_contact_missing", "warning", "Telefone e e-mail do responsável não estão no cadastro; o R-4099 sai sem eles.", "R-4099", "signatories"))

    events: list[ReinfEvent] = []
    if not valid_cnpj(cnpj):
        issues.append(Issue("entity_cnpj_invalid", "blocker", "O CNPJ da empresa não é válido. Nenhum evento foi gerado.", None, "legal_entity"))
    else:
        events = build_events(
            cnpj=cnpj,
            year=period.fiscal_year,
            month=period.month,
            payments=payments,
            responsible=responsible,
            generated_at=generated_at,
        )
    xsd_valid, found = validate_events(events)
    issues.extend(found)
    issues.extend(fixed_notes())
    counts = {kind: sum(1 for event in events if event.kind == kind) for kind in EVENT_KINDS}
    content = package(events, readme_text(competence, cnpj, events), generated_at)
    return ReinfPreview(
        content=content,
        issues=issues,
        counts=counts,
        checks={"xsd_valid": xsd_valid, "ir_matches_ledger": None},
        file_name=preview_file_name(cnpj, period.fiscal_year, period.month),
        competence=competence,
        events=events,
    )


def _fix_for(kind: str) -> str:
    return "signatories" if kind == "R-4099" else "withholding_payments"


def validate_events(events: list[ReinfEvent], *, per_event: int = 5) -> tuple[bool, list[Issue]]:
    """Valida cada evento no XSD oficial. Erro do XSD vira pendência `blocker` com a mensagem do lxml.

    Sem evento, `xsd_valid` é falso: nada foi validado, e a pendência "sem pagamentos" explica o porquê.
    """
    valid = bool(events)
    issues: list[Issue] = []
    for event in events:
        errors = xsd_errors(event.kind, event.xml)
        if errors:
            valid = False
        for message in errors[:per_event]:
            issues.append(Issue("xsd_invalid", "blocker", f"{event.file_name} não valida no XSD oficial: {message}", event.kind, _fix_for(event.kind)))
    return valid, issues
