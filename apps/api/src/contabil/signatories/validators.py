"""Validações de CPF e CRC dos signatários (ADR 030). Não consultam o CRC nem a Receita."""

from __future__ import annotations

import re

UFS = (
    "AC", "AL", "AM", "AP", "BA", "CE", "DF", "ES", "GO", "MA", "MG", "MS", "MT", "PA",
    "PB", "PE", "PI", "PR", "RJ", "RN", "RO", "RR", "RS", "SC", "SE", "SP", "TO",
)
CRC_CATEGORIES = ("contador", "tecnico")
LEGAL_REP_ROLES = ("socio_administrador", "administrador", "diretor", "titular")
LEGAL_REP_LABELS = {
    "socio_administrador": "Sócio-administrador",
    "administrador": "Administrador",
    "diretor": "Diretor",
    "titular": "Titular",
}
CATEGORY_LABELS = {"contador": "Contador", "tecnico": "Técnico em contabilidade"}

# Número do registro como o CRC imprime: dígitos, com o sufixo de tipo (/O, /S, /T, /P) e dígito opcionais.
_CRC_NUMBER = re.compile(r"^\d{1,8}(/[OSTP](-\d)?)?$")


def cpf_digits(value: str) -> str:
    return re.sub(r"\D", "", value or "")


def valid_cpf(value: str) -> bool:
    digits = cpf_digits(value)
    if len(digits) != 11 or digits == digits[0] * 11:
        return False
    for size in (9, 10):
        total = sum(int(digits[i]) * (size + 1 - i) for i in range(size))
        check = (total * 10) % 11 % 10
        if check != int(digits[size]):
            return False
    return True


def masked_cpf(digits: str) -> str:
    return f"***.{digits[3:6]}.{digits[6:9]}-**" if len(digits) == 11 else ""


def formatted_cpf(digits: str) -> str:
    return f"{digits[:3]}.{digits[3:6]}.{digits[6:9]}-{digits[9:]}" if len(digits) == 11 else digits


def normalize_crc_number(value: str) -> str:
    return (value or "").strip().upper().replace(" ", "")


def valid_crc_number(value: str) -> bool:
    return bool(_CRC_NUMBER.match(normalize_crc_number(value)))


def crc_label(uf: str, number: str) -> str:
    return f"CRC-{uf} {number}"
