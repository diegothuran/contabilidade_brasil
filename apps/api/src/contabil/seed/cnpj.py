"""Dígitos verificadores do CNPJ, numérico ou alfanumérico.

O CNPJ alfanumérico (IN RFB nº 2.229/2024) tem 12 caracteres em [0-9A-Z] e 2 dígitos verificadores
numéricos. O cálculo é o mesmo módulo 11 do CNPJ numérico, com o valor de cada caractere igual ao
código ASCII menos 48: "0" a "9" valem 0 a 9, "A" vale 17, "Z" vale 42. Para um CNPJ só de dígitos,
o resultado é o de sempre.
"""

from __future__ import annotations

import re

_BASE = re.compile(r"^[0-9A-Z]{12}$")
_WEIGHTS_FIRST = (5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)
_WEIGHTS_SECOND = (6, 5, 4, 3, 2, 9, 8, 7, 6, 5, 4, 3, 2)


def _value(char: str) -> int:
    return ord(char) - 48


def _check_digit(chars: str, weights: tuple[int, ...]) -> str:
    total = sum(_value(char) * weight for char, weight in zip(chars, weights, strict=True))
    remainder = total % 11
    return "0" if remainder < 2 else str(11 - remainder)


def cnpj_digits(base12: str) -> str:
    """Devolve a base de 12 caracteres seguida dos dois dígitos verificadores."""
    if not _BASE.match(base12):
        raise ValueError("base do CNPJ deve ter 12 caracteres entre 0-9 e A-Z")
    first = _check_digit(base12, _WEIGHTS_FIRST)
    second = _check_digit(base12 + first, _WEIGHTS_SECOND)
    return base12 + first + second
