from __future__ import annotations

import re
from decimal import Decimal

from contabil.platform.errors import DomainError

_AMOUNT = re.compile(r"^[0-9]+(\.[0-9]{1,6})?$")


def parse_amount(value: str) -> Decimal:
    if not isinstance(value, str) or _AMOUNT.fullmatch(value) is None:
        raise DomainError(400, "Valor inválido", "Informe o valor como string decimal com até 6 casas, sem float.")
    amount = Decimal(value)
    if amount <= 0:
        raise DomainError(400, "Valor inválido", "O valor da linha deve ser positivo.")
    return amount


def format_amount(value: Decimal) -> str:
    quantized = Decimal(value).quantize(Decimal("0.000001"))
    text = format(quantized, "f")
    if "." in text:
        text = text.rstrip("0").rstrip(".")
    return text or "0"


def format_signed(value: Decimal) -> str:
    if value < 0:
        return "-" + format_amount(abs(value))
    return format_amount(value)
