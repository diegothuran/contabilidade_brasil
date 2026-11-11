"""Conferência de um pagamento com retenção na fonte (ADR 032).

O sistema não calcula imposto e não conhece alíquota: confere documento, natureza, valores e data, e guarda
o que o usuário informou. As mesmas regras valem na gravação e, de novo, na prévia da EFD-Reinf, que não
confia em dado gravado por outro caminho (seed, migração ou SQL).
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from contabil.platform.errors import DomainError
from contabil.regulatory.registry import IncomeNatureTable, reinf_natures
from contabil.signatories.validators import valid_cpf
from contabil.tenancy.service import normalize_cnpj, valid_cnpj

BENEFICIARY_KINDS = ("pj", "pf")
NAME_MAX = 150
DESCRIPTION_MAX = 200
CENT = Decimal("0.01")
# Valor do XSD: até 12 dígitos inteiros e 2 casas. Na API vem com ponto, como os outros valores.
_AMOUNT = re.compile(r"^[0-9]{1,12}(\.[0-9]{1,2})?$")
_NATURE = re.compile(r"^[0-9]{5}$")
_CPF_TEXT = re.compile(r"^[0-9.\-\s]+$")
# O tributo da Tabela 01 que autoriza a CSRF informada de forma agregada (vlrBaseAgreg/vlrAgreg).
AGGREGATED_TAX = "AGREGADO"


@dataclass(frozen=True)
class PaymentInput:
    beneficiary_kind: str | None = None
    beneficiary_document: str | None = None
    beneficiary_name: str | None = None
    nature_code: str | None = None
    payment_date: date | str | None = None
    gross_amount: str | None = None
    ir_base: str | None = None
    ir_amount: str | None = None
    csrf_base: str | None = None
    csrf_amount: str | None = None
    description: str | None = None


@dataclass(frozen=True)
class CleanPayment:
    beneficiary_kind: str
    beneficiary_document: str
    beneficiary_name: str
    nature_code: str
    payment_date: date
    gross_amount: Decimal
    ir_base: Decimal | None
    ir_amount: Decimal | None
    csrf_base: Decimal | None
    csrf_amount: Decimal | None
    description: str | None


def _text(value) -> str:
    return "" if value is None else str(value).strip()


def _amount(value, field: str, errors: list[dict], *, required: bool) -> Decimal | None:
    raw = _text(value)
    if not raw:
        if required:
            errors.append({"loc": [field], "msg": "Informe o valor."})
        return None
    if _AMOUNT.fullmatch(raw) is None:
        errors.append({"loc": [field], "msg": "Use um valor decimal com ponto e até 2 casas, como 1500.00."})
        return None
    amount = Decimal(raw).quantize(CENT)
    if amount <= 0:
        errors.append({"loc": [field], "msg": "O valor precisa ser maior que zero."})
        return None
    return amount


def _document(kind: str, value, errors: list[dict]) -> str:
    raw = _text(value)
    if not raw:
        errors.append({"loc": ["beneficiary_document"], "msg": "Informe o CNPJ ou o CPF do beneficiário."})
        return ""
    if kind == "pj":
        digits = normalize_cnpj(raw)
        if not valid_cnpj(digits):
            errors.append({"loc": ["beneficiary_document"], "msg": "CNPJ inválido: confira os dígitos verificadores."})
        return digits
    if kind == "pf":
        digits = re.sub(r"\D", "", raw)
        if _CPF_TEXT.fullmatch(raw) is None or not valid_cpf(digits):
            errors.append({"loc": ["beneficiary_document"], "msg": "CPF inválido: confira os 11 dígitos e os verificadores."})
        return digits
    return raw


def _date(value, errors: list[dict]) -> date | None:
    if isinstance(value, date):
        return value
    raw = _text(value)
    if not raw:
        errors.append({"loc": ["payment_date"], "msg": "Informe a data do pagamento."})
        return None
    try:
        return date.fromisoformat(raw)
    except ValueError:
        errors.append({"loc": ["payment_date"], "msg": "Use a data no formato AAAA-MM-DD."})
        return None


def payment_problems(
    data: PaymentInput,
    *,
    period_start: date,
    period_end: date,
    table: IncomeNatureTable | None = None,
) -> tuple[CleanPayment | None, list[dict]]:
    """Normaliza e confere um pagamento. Devolve o pagamento limpo e a lista de erros por campo."""
    table = table or reinf_natures()
    errors: list[dict] = []
    kind = _text(data.beneficiary_kind).lower()
    if kind not in BENEFICIARY_KINDS:
        errors.append({"loc": ["beneficiary_kind"], "msg": "Use pj (pessoa jurídica) ou pf (pessoa física)."})
    document = _document(kind, data.beneficiary_document, errors)
    name = " ".join(_text(data.beneficiary_name).split())
    if not name:
        errors.append({"loc": ["beneficiary_name"], "msg": "Informe o nome do beneficiário."})
    elif len(name) > NAME_MAX:
        errors.append({"loc": ["beneficiary_name"], "msg": f"O nome tem até {NAME_MAX} caracteres."})
    code = _text(data.nature_code)
    nature = table.natures.get(code)
    if _NATURE.fullmatch(code) is None:
        errors.append({"loc": ["nature_code"], "msg": "A natureza do rendimento tem 5 dígitos."})
    elif nature is None:
        errors.append({"loc": ["nature_code"], "msg": f"O código {code} está fora da tabela da prévia (Tabela 01, versão {table.version})."})
    elif kind in BENEFICIARY_KINDS and nature.beneficiary_kind != kind:
        label = "pessoa jurídica" if nature.beneficiary_kind == "pj" else "pessoa física"
        errors.append({"loc": ["nature_code"], "msg": f"A natureza {code} é de pagamento a {label}."})
    paid_on = _date(data.payment_date, errors)
    if paid_on is not None and not period_start <= paid_on <= period_end:
        errors.append({"loc": ["payment_date"], "msg": "A data do pagamento precisa cair dentro da competência."})
    gross = _amount(data.gross_amount, "gross_amount", errors, required=True)
    ir_base = _amount(data.ir_base, "ir_base", errors, required=False)
    ir_amount = _amount(data.ir_amount, "ir_amount", errors, required=False)
    if ir_amount is not None and ir_base is None and _text(data.ir_base) == "":
        errors.append({"loc": ["ir_base"], "msg": "Informe a base do IR junto com o valor retido."})
    if ir_base is not None and ir_amount is not None and ir_amount > ir_base:
        errors.append({"loc": ["ir_amount"], "msg": "O IR retido não pode passar da base."})
    if nature is not None and "IR" not in nature.taxes and (ir_base is not None or ir_amount is not None):
        errors.append({"loc": ["ir_base"], "msg": f"A natureza {code} não tem IR na Tabela 01."})
    if kind == "pf" and gross is not None and ir_base is not None and ir_base > gross:
        # Leiaute 2.1.2b, R-4010: vlrRendBruto, se informado, deve ser maior ou igual a vlrRendTrib.
        errors.append({"loc": ["ir_base"], "msg": "No pagamento a pessoa física a base do IR não pode passar do valor bruto."})
    csrf_base = _amount(data.csrf_base, "csrf_base", errors, required=False)
    csrf_amount = _amount(data.csrf_amount, "csrf_amount", errors, required=False)
    if kind == "pf" and (_text(data.csrf_base) or _text(data.csrf_amount)):
        errors.append({"loc": ["csrf_base"], "msg": "Pagamento a pessoa física não tem CSRF. Deixe a base e o valor vazios."})
    elif kind == "pj":
        if csrf_amount is not None and csrf_base is None and _text(data.csrf_base) == "":
            errors.append({"loc": ["csrf_base"], "msg": "Informe a base da CSRF junto com o valor retido."})
        if csrf_base is not None and csrf_amount is not None and csrf_amount > csrf_base:
            errors.append({"loc": ["csrf_amount"], "msg": "A CSRF retida não pode passar da base."})
        if nature is not None and AGGREGATED_TAX not in nature.taxes and (csrf_base is not None or csrf_amount is not None):
            errors.append({"loc": ["csrf_base"], "msg": f"A natureza {code} não admite CSRF agregada na Tabela 01."})
    description = _text(data.description) or None
    if description is not None and len(description) > DESCRIPTION_MAX:
        errors.append({"loc": ["description"], "msg": f"A descrição tem até {DESCRIPTION_MAX} caracteres."})
    if errors:
        return None, errors
    assert paid_on is not None and gross is not None
    return (
        CleanPayment(
            beneficiary_kind=kind,
            beneficiary_document=document,
            beneficiary_name=name,
            nature_code=code,
            payment_date=paid_on,
            gross_amount=gross,
            ir_base=ir_base,
            ir_amount=ir_amount,
            csrf_base=csrf_base if kind == "pj" else None,
            csrf_amount=csrf_amount if kind == "pj" else None,
            description=description,
        ),
        [],
    )


def validate_payment(data: PaymentInput, *, period_start: date, period_end: date) -> CleanPayment:
    clean, errors = payment_problems(data, period_start=period_start, period_end=period_end)
    if errors or clean is None:
        raise DomainError(400, "Pagamento inválido", "Confira os campos destacados.", errors=errors)
    return clean
