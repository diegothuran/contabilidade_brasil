"""Prévia da ECD de um ano-calendário (ADR 031, POC).

Monta o arquivo do leiaute a partir do razão, sem transmitir, assinar ou ler certificado. O arquivo
sai marcado como prévia no nome e na natureza do livro, e vem com a lista do que falta (`issues`) e
com as conferências internas (`checks`). Os campos e a forma de cada registro vêm do registry.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import asdict, dataclass, field
from datetime import date
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.orm import Session

from contabil.ledger.service import account_sums, trial_balance
from contabil.ledger.statements import balance_sheet, income_statement
from contabil.platform.constants import CLOSING_SOURCE, EFFECTIVE_JOURNAL_STATUSES
from contabil.platform.errors import DomainError
from contabil.platform.principal import Principal
from contabil.regulatory.registration import registration_row
from contabil.regulatory.registry import Layout, LayoutNotFound, layout_for, uf_codes
from contabil.regulatory.writer import RecordWriter
from contabil.signatories.service import signatories_for
from contabil.tables import Account, AccountingPeriod, JournalEntry, JournalLine
from contabil.tenancy.service import require_entity

OBLIGATION = "ecd"
NOTICE = "Prévia para conferência no PVA. Não transmitir."
ZERO = Decimal("0")
PENDING_STATUSES = ("draft", "pending_approval", "approved")


@dataclass(frozen=True)
class Issue:
    code: str
    severity: str
    message: str
    register: str | None = None
    fix: str | None = None

    def as_dict(self) -> dict:
        return {key: value for key, value in asdict(self).items()}


@dataclass
class EcdPreview:
    content: str
    issues: list[Issue]
    counts: dict[str, int]
    checks: dict[str, bool]
    file_name: str
    layout_version: str
    encoding: str
    notice: str = NOTICE
    result: str = "0"
    extra: dict = field(default_factory=dict)

    def encoded(self) -> bytes:
        return self.content.encode(self.encoding)


# Pequenos auxiliares de valor


def _dec(value: str | Decimal | None) -> Decimal:
    return Decimal(str(value or "0"))


def _side(amount: Decimal, debit_nature: bool) -> str:
    """Indicador D ou C de um saldo com sinal (débito positivo). Saldo zero segue a natureza da conta."""
    if amount > 0:
        return "D"
    if amount < 0:
        return "C"
    return "D" if debit_nature else "C"


def _presented_side(amount: Decimal, nature: str) -> str:
    """Indicador de um valor apresentado na natureza (positivo = natureza, negativo = contrário)."""
    other = "C" if nature == "D" else "D"
    return nature if amount >= 0 else other


# Montagem


def build_ecd_preview(session: Session, tenant_id: str, legal_entity_id: str, fiscal_year: int, *, actor: str = "system") -> EcdPreview:
    entity = require_entity(session, tenant_id, legal_entity_id)
    try:
        layout = layout_for(OBLIGATION, fiscal_year)
    except LayoutNotFound as exc:
        raise DomainError(422, "Leiaute não encontrado", f"O registry não tem leiaute da ECD para {fiscal_year}.") from exc
    periods = list(
        session.scalars(
            select(AccountingPeriod)
            .where(
                AccountingPeriod.tenant_id == tenant_id,
                AccountingPeriod.legal_entity_id == entity.id,
                AccountingPeriod.fiscal_year == fiscal_year,
            )
            .order_by(AccountingPeriod.month)
        ).all()
    )
    if not periods:
        raise DomainError(409, "Ano sem competências", f"A empresa não tem competências em {fiscal_year}.")
    reader = Principal(actor, tenant_id, frozenset({"viewer"}), actor, "")
    mappings = layout.product_mappings
    issues: list[Issue] = []
    start, end = date(fiscal_year, 1, 1), date(fiscal_year, 12, 31)

    registration = registration_row(session, tenant_id, entity.id)
    if registration is None:
        issues.append(Issue("registration_missing", "blocker", "Preencha os dados da escrituração: UF, município, registro e número do livro.", "0000", "ecd_registration"))
    else:
        issues.extend(registration_issues(registration))
    signatories = signatories_for(session, tenant_id, entity.id)
    accountant = signatories.accountant if signatories else None
    representative = signatories.legal_representative if signatories else None
    if accountant is None:
        issues.append(Issue("accountant_missing", "blocker", "A empresa não tem contador responsável com CRC cadastrado (J930 código 900).", "J930", "signatories"))
    elif accountant.crc_category != "contador":
        issues.append(Issue("accountant_not_contador", "blocker", "O responsável técnico cadastrado é técnico em contabilidade; o J930 900 pede contador.", "J930", "signatories"))
    if representative is None:
        issues.append(Issue("legal_rep_missing", "blocker", "A empresa não tem representante legal cadastrado (J930 com IND_RESP_LEGAL = S).", "J930", "signatories"))
    months = {period.month for period in periods}
    if months != set(range(1, 13)):
        missing = ", ".join(f"{month:02d}" for month in sorted(set(range(1, 13)) - months))
        issues.append(Issue("months_missing", "warning", f"O ano não tem as competências {missing}; o I150 sai só com os meses existentes.", "I150"))

    pending = session.scalar(
        select(JournalEntry.id)
        .join(AccountingPeriod, AccountingPeriod.id == JournalEntry.period_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == entity.id,
            AccountingPeriod.fiscal_year == fiscal_year,
            JournalEntry.status.in_(PENDING_STATUSES),
        )
        .limit(1)
    )
    if pending is not None:
        issues.append(Issue("pending_journals", "blocker", "Há lançamento do ano em rascunho, pendente ou aprovado sem publicar.", "I200", "journals"))
    closings = list(
        session.scalars(
            select(JournalEntry)
            .join(AccountingPeriod, AccountingPeriod.id == JournalEntry.period_id)
            .where(
                JournalEntry.tenant_id == tenant_id,
                JournalEntry.legal_entity_id == entity.id,
                AccountingPeriod.fiscal_year == fiscal_year,
                JournalEntry.source_type == CLOSING_SOURCE,
                JournalEntry.status == "published",
            )
            .order_by(JournalEntry.entry_date)
        ).all()
    )
    if not closings:
        issues.append(Issue("closing_missing", "blocker", f"O exercício {fiscal_year} não tem encerramento publicado; sem ele não há I350/I355 nem lançamento tipo E.", "I350", "year_end_closing"))

    accounts = list(
        session.scalars(
            select(Account).where(Account.tenant_id == tenant_id, Account.legal_entity_id == entity.id).order_by(Account.code)
        ).all()
    )
    by_id = {account.id: account for account in accounts}
    natures = mappings["account_type_to_cod_nat"]
    debit_types = set(mappings["debit_nature_types"])
    for account in accounts:
        if account.account_type not in natures:
            issues.append(Issue("account_without_nature", "blocker", f"A conta {account.code} {account.name} não tem natureza para o I050.", "I050", "accounts"))

    writer = RecordWriter(layout)
    _block_zero(writer, layout, entity, registration, start, end)
    _plan(writer, accounts, by_id, natures, start)
    _balances(writer, session, reader, entity.id, periods, by_id, debit_types)
    _journals(writer, session, tenant_id, entity.id, fiscal_year, by_id)
    if closings:
        _result_before_closing(writer, session, tenant_id, entity.id, fiscal_year, by_id, closings[-1].entry_date)
    december = periods[-1]
    previous = session.scalar(
        select(AccountingPeriod)
        .where(
            AccountingPeriod.tenant_id == tenant_id,
            AccountingPeriod.legal_entity_id == entity.id,
            AccountingPeriod.end_date < start,
        )
        .order_by(AccountingPeriod.end_date.desc())
        .limit(1)
    )
    statement = income_statement(session, reader, entity.id, december.id)
    final_sheet = balance_sheet(session, reader, entity.id, december.id)
    initial_sheet = balance_sheet(session, reader, entity.id, previous.id) if previous is not None else None
    writer.add("J005", {"DT_INI": start, "DT_FIN": end, **layout.preview_defaults.get("J005", {})})
    _balance_sheet_lines(writer, final_sheet, initial_sheet)
    _income_lines(writer, statement)
    writer.add(
        "J900",
        {
            "NUM_ORD": registration.book_number if registration else None,
            "NAT_LIVRO": mappings["book_nature"],
            "NOME": entity.name,
            "DT_INI_ESCR": start,
            "DT_FIN_ESCR": end,
        },
    )
    _signers(writer, layout, accountant, representative)
    content = writer.finish()

    result = _dec(statement["result"]["year_to_date"])
    seen: set[tuple[str, str, str]] = set()
    for violation in writer.violations:
        key = (violation.register, violation.field, violation.rule)
        if key in seen:
            continue
        seen.add(key)
        severity = "blocker" if violation.severity == "error" else "warning"
        issues.append(Issue(f"layout_{violation.rule}", severity, violation.message, violation.register, _fix_for(violation.register)))
    issues.extend(_fixed_notes(layout))
    checks = check_file(content, layout, expected_result=result if closings else None)
    for name, passed in checks.items():
        if not passed:
            issues.append(Issue(f"check_{name}", "blocker", f"A conferência interna {name} não fechou. O arquivo não deve ir ao PVA.", None, None))
    return EcdPreview(
        content=content,
        issues=issues,
        counts=writer.counts,
        checks=checks,
        file_name=preview_file_name(entity.cnpj, fiscal_year),
        layout_version=layout.version,
        encoding=layout.file["encoding"],
        result=format(result, "f"),
    )


def preview_file_name(cnpj: str, fiscal_year: int) -> str:
    """Nome do arquivo da prévia. O CNPJ entra como está guardado: 14 dígitos ou alfanumérico."""
    return f"ECD-PREVIA-{cnpj}-{fiscal_year}.txt"


def registration_issues(registration) -> list[Issue]:
    """Confere de novo, sobre o cadastro gravado, as regras do NIRE do Manual do Leiaute 9.

    O IND_NIRE do 0000 sai da presença do NIRE, então o par IND_NIRE/NIRE do I030 é sempre
    coerente no arquivo; o que pode divergir é o registro escolhido (Junta ou cartório) e a UF.
    O cadastro já recusa isso na gravação; aqui a prévia não confia num dado gravado por outro
    caminho (seed, migração ou SQL).
    """
    found: list[Issue] = []
    nire = (registration.nire or "").strip()
    if registration.registry_kind == "junta" and not nire:
        found.append(Issue("registration_nire_missing", "blocker", "Empresa registrada na Junta Comercial sem NIRE: o I030 sairia com IND_NIRE = 1 e NIRE vazio (REGRA_CAMPO_OBRIGATORIO_NIRE).", "I030", "ecd_registration"))
    if registration.registry_kind == "cartorio" and nire:
        found.append(Issue("registration_nire_unexpected", "blocker", "Sociedade registrada em cartório não tem NIRE: com NIRE preenchido o PVA exige IND_NIRE = 1.", "I030", "ecd_registration"))
    prefix = uf_codes().get((registration.uf or "").upper())
    if nire and prefix and not nire.startswith(prefix):
        found.append(Issue("registration_nire_uf", "blocker", f"O NIRE {nire} não começa com {prefix}, o código da UF {registration.uf} do 0000 (REGRA_NIRE_UF).", "I030", "ecd_registration"))
    return found


def _fix_for(register: str) -> str | None:
    if register in {"0000", "I030", "J900"}:
        return "ecd_registration"
    if register == "J930":
        return "signatories"
    if register == "I050":
        return "accounts"
    return None


def _fixed_notes(layout: Layout) -> list[Issue]:
    notes = [
        Issue("out_of_scope_i051", "out_of_scope", "O I051 (plano referencial) fica fora: o 0000.COD_PLAN_REF sai vazio e o PVA valida sem ele.", "I051"),
        Issue("out_of_scope_i012", "out_of_scope", "O I012/I015 não se aplica ao Diário completo (G); livros auxiliares ficam fora da POC.", "I012"),
        Issue("out_of_scope_k", "out_of_scope", "O bloco K (conglomerado econômico) fica fora: o 0000.IND_ESC_CONS sai N.", "K001"),
        Issue("out_of_scope_j210", "out_of_scope", "DLPA e DMPL (J210/J215) ficam fora da POC.", "J210"),
        Issue("out_of_scope_c", "out_of_scope", "O bloco C não é importado: o PVA recupera da ECD anterior.", "C001"),
        Issue("assumption_0007", "assumption", "O 0007 sai como 00 (nenhuma inscrição em outras entidades). Se a empresa tem IE ou outra inscrição, a prévia ainda não informa.", "0007"),
    ]
    for register, values in layout.preview_defaults.items():
        if not isinstance(values, dict):
            continue
        assumed = ", ".join(f"{name} = {value or 'vazio'}" for name, value in values.items())
        notes.append(Issue(f"assumption_{register}", "assumption", f"Valores assumidos no {register}: {assumed}.", register))
    notes.append(Issue("assumption_signers", "assumption", "Cargo do representante e formato do IND_CRC seguem a correspondência provisória do registry; EMAIL e FONE do contador não estão no cadastro.", "J930", "signatories"))
    return notes


def _block_zero(writer: RecordWriter, layout: Layout, entity, registration, start: date, end: date) -> None:
    values = {
        "DT_INI": start,
        "DT_FIN": end,
        "NOME": entity.name,
        "CNPJ": entity.cnpj,
        "UF": registration.uf if registration else None,
        "COD_MUN": registration.municipality_ibge if registration else None,
        "IND_SIT_ESP": registration.special_situation if registration else None,
        "IND_NIRE": ("1" if registration.nire else "0") if registration else None,
        **layout.preview_defaults.get("0000", {}),
    }
    writer.add("0000", values)
    writer.add("0007", {"COD_ENT_REF": "00"})
    writer.add("I010", {"IND_ESC": layout.product_mappings["bookkeeping_form"]})
    writer.add(
        "I030",
        {
            "NUM_ORD": registration.book_number if registration else None,
            "NAT_LIVR": layout.product_mappings["book_nature"],
            "NOME": entity.name,
            "NIRE": registration.nire if registration else None,
            "CNPJ": entity.cnpj,
            "DT_ARQ": registration.registry_date if registration else None,
            "DT_ARQ_CONV": registration.conversion_date if registration else None,
            "DT_EX_SOCIAL": end,
        },
    )


def _depth(account: Account, by_id: dict[str, Account]) -> int:
    level, current, seen = 1, account, {account.id}
    while current.parent_id and current.parent_id in by_id and current.parent_id not in seen:
        current = by_id[current.parent_id]
        seen.add(current.id)
        level += 1
    return level


def _plan(writer: RecordWriter, accounts: list[Account], by_id: dict[str, Account], natures: dict, start: date) -> None:
    for account in accounts:
        parent = by_id.get(account.parent_id) if account.parent_id else None
        writer.add(
            "I050",
            {
                "DT_ALT": start,
                "COD_NAT": natures.get(account.account_type),
                "IND_CTA": "A" if account.postable else "S",
                "NIVEL": _depth(account, by_id),
                "COD_CTA": account.code,
                "COD_CTA_SUP": parent.code if parent else None,
                "CTA": account.name,
            },
        )
        if account.postable:
            writer.add("I052", {"COD_AGL": account.code})


def _balances(writer, session, reader, entity_id, periods, by_id, debit_types) -> None:
    for period in periods:
        writer.add("I150", {"DT_INI": period.start_date, "DT_FIN": period.end_date})
        balance = trial_balance(session, reader, entity_id, period.id)
        for row in balance["rows"]:
            opening, debit, credit = _dec(row["opening_balance"]), _dec(row["debit"]), _dec(row["credit"])
            closing = _dec(row["closing_balance"])
            if opening == 0 and debit == 0 and credit == 0:
                continue
            debit_nature = by_id[row["account_id"]].account_type in debit_types
            writer.add(
                "I155",
                {
                    "COD_CTA": row["code"],
                    "VL_SLD_INI": abs(opening),
                    "IND_DC_INI": _side(opening, debit_nature),
                    "VL_DEB": debit,
                    "VL_CRED": credit,
                    "VL_SLD_FIN": abs(closing),
                    "IND_DC_FIN": _side(closing, debit_nature),
                },
            )


def _journals(writer, session, tenant_id, entity_id, fiscal_year, by_id) -> None:
    journals = session.scalars(
        select(JournalEntry)
        .join(AccountingPeriod, AccountingPeriod.id == JournalEntry.period_id)
        .where(
            JournalEntry.tenant_id == tenant_id,
            JournalEntry.legal_entity_id == entity_id,
            AccountingPeriod.fiscal_year == fiscal_year,
            JournalEntry.status.in_(EFFECTIVE_JOURNAL_STATUSES),
        )
        .order_by(JournalEntry.entry_date, JournalEntry.published_at, JournalEntry.id)
    ).all()
    if not journals:
        return
    lines_by_journal: dict[str, list[JournalLine]] = defaultdict(list)
    for line in session.scalars(
        select(JournalLine)
        .where(JournalLine.tenant_id == tenant_id, JournalLine.journal_id.in_([journal.id for journal in journals]))
        .order_by(JournalLine.journal_id, JournalLine.line_no)
    ).all():
        lines_by_journal[line.journal_id].append(line)
    for journal in journals:
        lines = lines_by_journal[journal.id]
        total = sum((line.amount for line in lines if line.side == "debit"), ZERO)
        writer.add(
            "I200",
            {
                "NUM_LCTO": journal.id,
                "DT_LCTO": journal.entry_date,
                "VL_LCTO": total,
                "IND_LCTO": "E" if journal.source_type == CLOSING_SOURCE else "N",
            },
        )
        for line in lines:
            writer.add(
                "I250",
                {
                    "COD_CTA": by_id[line.account_id].code,
                    "VL_DC": line.amount,
                    "IND_DC": "D" if line.side == "debit" else "C",
                    "HIST": line.description or journal.description,
                },
            )


def _result_before_closing(writer, session, tenant_id, entity_id, fiscal_year, by_id, closing_date: date) -> None:
    sums = account_sums(session, tenant_id, entity_id, AccountingPeriod.fiscal_year == fiscal_year, exclude_closing=True)
    writer.add("I350", {"DT_RES": closing_date})
    for account in sorted(by_id.values(), key=lambda item: item.code):
        if not account.postable or account.account_type not in ("revenue", "expense"):
            continue
        amount = sums.get(account.id, ZERO)
        if amount == 0:
            continue
        writer.add("I355", {"COD_CTA": account.code, "VL_CTA": abs(amount), "IND_DC": "D" if amount > 0 else "C"})


# Demonstrações (J100 e J150), montadas a partir das demonstrações gerenciais (ADR 029)


@dataclass
class _Node:
    code: str
    name: str
    detail: bool
    children: list["_Node"] = field(default_factory=list)
    initial: Decimal = ZERO
    final: Decimal = ZERO

    def total(self) -> None:
        for child in self.children:
            child.total()
        if self.children:
            self.initial = sum((child.initial for child in self.children), ZERO)
            self.final = sum((child.final for child in self.children), ZERO)


def _sheet_groups(sheet: dict | None) -> dict[str, dict[str, dict]]:
    """Por tipo de seção: grupo (conta raiz) -> {name, rows: code -> (name, valor)}."""
    found: dict[str, dict[str, dict]] = {}
    if sheet is None:
        return found
    for section in sheet["sections"]:
        groups = found.setdefault(section["account_type"], {})
        for group in section["groups"]:
            entry = groups.setdefault(group["code"], {"name": group["name"], "rows": {}})
            for row in group["rows"]:
                entry["rows"][row["code"]] = (row["name"], _dec(row["balance"]))
    return found


def _group_nodes(final: dict, initial: dict, account_types: tuple[str, ...]) -> list[_Node]:
    nodes: list[_Node] = []
    for account_type in account_types:
        final_groups, initial_groups = final.get(account_type, {}), initial.get(account_type, {})
        for code in sorted(set(final_groups) | set(initial_groups)):
            source = final_groups.get(code) or initial_groups[code]
            row_codes = sorted(set(final_groups.get(code, {}).get("rows", {})) | set(initial_groups.get(code, {}).get("rows", {})))
            if not row_codes:
                continue
            rows = []
            for row_code in row_codes:
                name, final_value = final_groups.get(code, {}).get("rows", {}).get(row_code, (None, ZERO))
                initial_name, initial_value = initial_groups.get(code, {}).get("rows", {}).get(row_code, (None, ZERO))
                rows.append(_Node(row_code, name or initial_name or row_code, True, initial=initial_value, final=final_value))
            group_code = f"G{code}" if code in row_codes else code
            nodes.append(_Node(group_code, source["name"], False, rows))
    return nodes


def _emit_balance(writer: RecordWriter, node: _Node, level: int, parent: str | None, group: str) -> None:
    nature = "D" if group == "A" else "C"
    writer.add(
        "J100",
        {
            "COD_AGL": node.code,
            "IND_COD_AGL": "D" if node.detail else "T",
            "NIVEL_AGL": level,
            "COD_AGL_SUP": parent,
            "IND_GRP_BAL": group,
            "DESCR_COD_AGL": node.name,
            "VL_CTA_INI": abs(node.initial),
            "IND_DC_CTA_INI": _presented_side(node.initial, nature),
            "VL_CTA_FIN": abs(node.final),
            "IND_DC_CTA_FIN": _presented_side(node.final, nature),
        },
    )
    for child in node.children:
        _emit_balance(writer, child, level + 1, node.code, group)


def _balance_sheet_lines(writer: RecordWriter, final_sheet: dict, initial_sheet: dict | None) -> None:
    final, initial = _sheet_groups(final_sheet), _sheet_groups(initial_sheet)
    assets = _Node("A", "ATIVO", False, _group_nodes(final, initial, ("asset",)))
    liabilities = _Node("P", "PASSIVO E PATRIMONIO LIQUIDO", False, _group_nodes(final, initial, ("liability", "equity")))
    unclosed_final = _dec(final_sheet["sections"][2].get("unclosed_result"))
    unclosed_initial = _dec(initial_sheet["sections"][2].get("unclosed_result")) if initial_sheet else ZERO
    if unclosed_final != 0 or unclosed_initial != 0:
        liabilities.children.append(_Node("RES.NAO.ENC", "RESULTADO DO EXERCICIO NAO ENCERRADO", True, initial=unclosed_initial, final=unclosed_final))
    for root, group in ((assets, "A"), (liabilities, "P")):
        root.total()
        _emit_balance(writer, root, 1, None, group)


def _income_lines(writer: RecordWriter, statement: dict) -> None:
    order = 0

    def emit(node: _Node, level: int, parent: str | None, effect: str) -> None:
        nonlocal order
        order += 1
        nature = "C" if effect == "R" else "D"
        writer.add(
            "J150",
            {
                "NU_ORDEM": order,
                "COD_AGL": node.code,
                "IND_COD_AGL": "D" if node.detail else "T",
                "NIVEL_AGL": level,
                "COD_AGL_SUP": parent,
                "DESCR_COD_AGL": node.name,
                "VL_CTA_FIN": abs(node.final),
                "IND_DC_CTA_FIN": _presented_side(node.final, nature),
                "IND_GRP_DRE": effect if node.final >= 0 else ("D" if effect == "R" else "R"),
            },
        )
        for child in node.children:
            emit(child, level + 1, node.code, effect)

    groups: list[tuple[_Node, str]] = []
    for section in statement["sections"]:
        effect = "R" if section["account_type"] == "revenue" else "D"
        for group in section["groups"]:
            rows = [_Node(row["code"], row["name"], True, final=_dec(row["year_to_date"])) for row in group["rows"]]
            if not rows:
                continue
            codes = {row.code for row in rows}
            node = _Node(f"G{group['code']}" if group["code"] in codes else group["code"], group["name"], False, rows)
            node.total()
            groups.append((node, effect))
    result = _dec(statement["result"]["year_to_date"])
    order += 1
    writer.add(
        "J150",
        {
            "NU_ORDEM": order,
            "COD_AGL": "RES",
            "IND_COD_AGL": "T",
            "NIVEL_AGL": 1,
            "DESCR_COD_AGL": "RESULTADO DO EXERCICIO",
            "VL_CTA_FIN": abs(result),
            "IND_DC_CTA_FIN": "C" if result >= 0 else "D",
            "IND_GRP_DRE": "R" if result >= 0 else "D",
        },
    )
    for node, effect in groups:
        emit(node, 2, "RES", effect)


def _signers(writer: RecordWriter, layout: Layout, accountant, representative) -> None:
    codes = layout.codes["COD_ASSIN"]
    accountant_code = layout.codes["accountant_cod_assin"]
    if accountant is not None:
        writer.add(
            "J930",
            {
                "IDENT_NOM": accountant.name,
                "IDENT_CPF_CNPJ": accountant.cpf,
                "IDENT_QUALIF": codes[accountant_code],
                "COD_ASSIN": accountant_code,
                "IND_CRC": f"{accountant.crc_uf}{accountant.crc_number}",
                "UF_CRC": accountant.crc_uf,
                "NUM_SEQ_CRC": accountant.regularity_number,
                "DT_CRC": accountant.regularity_valid_until,
                "IND_RESP_LEGAL": "N",
            },
        )
    if representative is not None:
        code = layout.product_mappings["legal_rep_role_to_cod_assin"].get(representative.role or "")
        writer.add(
            "J930",
            {
                "IDENT_NOM": representative.name,
                "IDENT_CPF_CNPJ": representative.cpf,
                "IDENT_QUALIF": codes.get(code or ""),
                "COD_ASSIN": code,
                "IND_RESP_LEGAL": "S",
            },
        )


# Conferências sobre o texto pronto


def _parse(content: str, layout: Layout) -> list[list[str]]:
    delimiter = layout.file["delimiter"]
    rows = []
    for line in content.split(layout.file["line_ending"]):
        if not line:
            continue
        rows.append(line[1:-1].split(delimiter) if line.startswith(delimiter) and line.endswith(delimiter) else [line])
    return rows


def _number(text: str) -> Decimal:
    return Decimal(text.replace(",", ".")) if text else ZERO


def check_file(content: str, layout: Layout, *, expected_result: Decimal | None = None) -> dict[str, bool]:
    rows = _parse(content, layout)
    names = {register: [item.name for item in layout.fields(register)] for register in layout.registers}

    def record(row: list[str]) -> dict[str, str]:
        return dict(zip(names.get(row[0], []), row))

    records = [record(row) for row in rows]
    checks: dict[str, bool] = {}

    # I200 = soma dos débitos = soma dos créditos do I250.
    entries: list[tuple[Decimal, Decimal, Decimal]] = []
    for item in records:
        if item["REG"] == "I200":
            entries.append((_number(item["VL_LCTO"]), ZERO, ZERO))
        elif item["REG"] == "I250" and entries:
            total, debit, credit = entries[-1]
            amount = _number(item["VL_DC"])
            entries[-1] = (total, debit + amount, credit) if item["IND_DC"] == "D" else (total, debit, credit + amount)
    checks["i200_matches_i250"] = all(debit == total and credit == total for total, debit, credit in entries)

    # I155: inicial + débitos - créditos = final, com o sinal de cada indicador.
    def signed(value: str, side: str) -> Decimal:
        return _number(value) if side == "D" else -_number(value)

    checks["i155_rolls_forward"] = all(
        signed(item["VL_SLD_INI"], item["IND_DC_INI"]) + _number(item["VL_DEB"]) - _number(item["VL_CRED"])
        == signed(item["VL_SLD_FIN"], item["IND_DC_FIN"])
        for item in records
        if item["REG"] == "I155"
    )

    # I355 soma o resultado da DRE (crédito positivo).
    if expected_result is not None:
        total = sum((-signed(item["VL_CTA"], item["IND_DC"]) for item in records if item["REG"] == "I355"), ZERO)
        checks["i355_matches_income_statement"] = total == expected_result.quantize(Decimal("0.01"))

    # J100: ativo = passivo + PL, no início e no fim.
    level_one = [item for item in records if item["REG"] == "J100" and item["NIVEL_AGL"] == "1"]
    assets = [item for item in level_one if item["IND_GRP_BAL"] == "A"]
    liabilities = [item for item in level_one if item["IND_GRP_BAL"] == "P"]
    if assets and liabilities:
        checks["j100_balances"] = all(
            signed(assets[0][value], assets[0][side]) == -signed(liabilities[0][value], liabilities[0][side])
            for value, side in (("VL_CTA_INI", "IND_DC_CTA_INI"), ("VL_CTA_FIN", "IND_DC_CTA_FIN"))
        )
    else:
        checks["j100_balances"] = False

    # Bloco 9 e encerramentos de bloco batem com as linhas.
    actual: dict[str, int] = defaultdict(int)
    for item in records:
        actual[item["REG"]] += 1
    declared = {item["REG_BLC"]: int(item["QTD_REG_BLC"]) for item in records if item["REG"] == "9900"}
    totals_ok = declared == dict(actual)
    structure = layout.structure
    file_close = structure["file_close"]
    closing = next((item for item in records if item["REG"] == file_close["register"]), None)
    totals_ok = totals_ok and closing is not None and int(closing[file_close["count_field"]]) == len(records)
    for block, spec in structure["blocks"].items():
        close = next((item for item in records if item["REG"] == spec["close"]), None)
        in_block = sum(1 for item in records if item["REG"][0] == block)
        totals_ok = totals_ok and close is not None and int(close[spec["count_field"]]) == in_block
    checks["block_counts"] = totals_ok
    return checks
