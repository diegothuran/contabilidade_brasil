"""CNPJ numérico e alfanumérico (IN RFB nº 2.229/2024), módulo 11 com valor = ASCII − 48."""

from __future__ import annotations

import pytest

from contabil.seed.cnpj import cnpj_digits
from contabil.tenancy.service import normalize_cnpj, valid_cnpj


def test_numeric_cnpj_keeps_the_usual_check_digits():
    assert cnpj_digits("112223330001") == "11222333000181"
    assert cnpj_digits("042520110001") == "04252011000110"


def test_alphanumeric_base_uses_ascii_minus_48():
    # Exemplo da Receita: 12.ABC.345/01DE-35. A = 17, B = 18, C = 19, D = 20, E = 21.
    assert cnpj_digits("12ABC34501DE") == "12ABC34501DE35"


def test_valid_cnpj_accepts_the_alphanumeric_format_with_mask_and_lowercase():
    assert valid_cnpj("12ABC34501DE35")
    assert valid_cnpj("12.ABC.345/01DE-35")
    assert valid_cnpj("12.abc.345/01de-35")
    assert normalize_cnpj("12.abc.345/01de-35") == "12ABC34501DE35"
    assert valid_cnpj("11.222.333/0001-81")


@pytest.mark.parametrize(
    "value",
    [
        "12ABC34501DE36",  # dígito verificador errado
        "12ABC34501DEA5",  # dígito verificador com letra
        "12ABC34501D35",  # 13 caracteres
        "12ABC34501DÉ35",  # letra fora de A-Z
        "AAAAAAAAAAAAAA",
        "00000000000000",
    ],
)
def test_valid_cnpj_refuses_what_breaks_the_rule(value):
    assert not valid_cnpj(value)


def test_base_outside_the_alphabet_is_refused():
    with pytest.raises(ValueError):
        cnpj_digits("12abc34501de")
    with pytest.raises(ValueError):
        cnpj_digits("12ABC3450")
