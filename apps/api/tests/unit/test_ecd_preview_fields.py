"""Campos da prévia da ECD conferidos contra o Manual do Leiaute 9 (ADE Cofis nº 01/2026)."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from types import SimpleNamespace

from contabil.regulatory.ecd_preview import (
    _block_zero,
    _number,
    _presented_side,
    _side,
    preview_file_name,
    registration_issues,
)
from contabil.regulatory.registry import layout_for
from contabil.regulatory.writer import RecordWriter
from contabil.tenancy.service import valid_cnpj

ALPHANUMERIC_CNPJ = "12ABC34501DE35"


def _layout():
    return layout_for("ecd", 2026)


def _registration(**overrides):
    base = {
        "uf": "PE",
        "municipality_ibge": "2611606",
        "registry_kind": "junta",
        "nire": "26200000011",
        "registry_date": date(2020, 5, 4),
        "special_situation": None,
        "book_number": 3,
    }
    base.update(overrides)
    return SimpleNamespace(**base)


def _records(registration, cnpj: str = "11222333000181") -> tuple[dict[str, dict[str, str]], RecordWriter]:
    layout = _layout()
    writer = RecordWriter(layout)
    entity = SimpleNamespace(name="Clinica Exemplo", cnpj=cnpj)
    _block_zero(writer, layout, entity, registration, date(2026, 1, 1), date(2026, 12, 31))
    content = writer.finish()
    found: dict[str, dict[str, str]] = {}
    for line in content.split(layout.file["line_ending"]):
        if not line:
            continue
        cells = line[1:-1].split(layout.file["delimiter"])
        names = [item.name for item in layout.fields(cells[0])]
        found.setdefault(cells[0], dict(zip(names, cells)))
    return found, writer


def test_cartorio_without_nire_sends_ind_nire_zero_and_the_opening_date_in_dt_arq():
    opening = date(2018, 3, 15)
    records, writer = _records(_registration(registry_kind="cartorio", nire=None, registry_date=opening))
    assert records["0000"]["IND_NIRE"] == "0"
    assert records["I030"]["NIRE"] == ""
    assert records["I030"]["DT_ARQ"] == "15032018"
    assert records["I030"]["DT_ARQ_CONV"] == ""
    assert not [item for item in writer.violations if item.field in {"NIRE", "IND_NIRE", "DT_ARQ"}]


def test_junta_sends_ind_nire_one_with_the_nire_and_the_filing_date():
    records, writer = _records(_registration())
    assert records["0000"]["IND_NIRE"] == "1"
    assert records["0000"]["UF"] == "PE"
    assert records["I030"]["NIRE"] == "26200000011"
    assert records["I030"]["NIRE"][:2] == "26"
    assert records["I030"]["DT_ARQ"] == "04052020"
    assert not [item for item in writer.violations if item.field in {"NIRE", "IND_NIRE", "DT_ARQ"}]


def test_preview_flags_a_nire_that_does_not_match_the_uf_or_the_registry_kind():
    assert registration_issues(_registration()) == []
    assert registration_issues(_registration(registry_kind="cartorio", nire=None)) == []
    wrong_uf = registration_issues(_registration(nire="35200000011"))
    assert [item.code for item in wrong_uf] == ["registration_nire_uf"]
    assert wrong_uf[0].severity == "blocker"
    assert wrong_uf[0].register == "I030"
    assert wrong_uf[0].fix == "ecd_registration"
    assert [item.code for item in registration_issues(_registration(nire=None))] == ["registration_nire_missing"]
    assert [item.code for item in registration_issues(_registration(registry_kind="cartorio"))] == ["registration_nire_unexpected"]


def test_values_use_decimal_comma_two_places_and_no_thousands_separator():
    layout = _layout()
    writer = RecordWriter(layout)
    line = writer.line(
        "I155",
        {
            "COD_CTA": "2.1.01",
            "VL_SLD_INI": Decimal("1234567.8"),
            "IND_DC_INI": "C",
            "VL_DEB": Decimal("1000"),
            "VL_CRED": Decimal("0.5"),
            "VL_SLD_FIN": Decimal("1233568.3"),
            "IND_DC_FIN": "C",
        },
    )
    assert line == "|I155|2.1.01||1234567,80|C|1000,00|0,50|1233568,30|C|"
    assert "." not in line.split("|", 3)[3]
    assert writer.violations == []
    assert _number("1234567,80") == Decimal("1234567.80")


def test_credit_balance_goes_out_without_sign_and_with_the_c_indicator():
    balance = Decimal("-1500.25")
    assert _side(balance, debit_nature=True) == "C"
    assert _side(Decimal("1500.25"), debit_nature=False) == "D"
    assert _side(Decimal("0"), debit_nature=False) == "C"
    assert _presented_side(Decimal("-10"), "D") == "C"
    writer = RecordWriter(_layout())
    line = writer.line("I250", {"COD_CTA": "1.1.01", "VL_DC": abs(balance), "IND_DC": _side(balance, True), "HIST": "Ajuste"})
    assert line == "|I250|1.1.01||1500,25|C|||Ajuste||"
    assert writer.violations == []
    signed = RecordWriter(_layout())
    assert signed.line("I250", {"COD_CTA": "1", "VL_DC": balance, "IND_DC": "C"}) == "|I250|1||1500,25|C|||||"
    assert [(item.field, item.rule) for item in signed.violations] == [("VL_DC", "sign")]

def test_alphanumeric_cnpj_flows_into_the_preview_file_and_its_name():
    assert valid_cnpj(ALPHANUMERIC_CNPJ)
    records, writer = _records(_registration(), cnpj=ALPHANUMERIC_CNPJ)
    assert records["0000"]["CNPJ"] == ALPHANUMERIC_CNPJ
    assert records["I030"]["CNPJ"] == ALPHANUMERIC_CNPJ
    assert not [item for item in writer.violations if item.field == "CNPJ"]
    assert preview_file_name(ALPHANUMERIC_CNPJ, 2026) == "ECD-PREVIA-12ABC34501DE35-2026.txt"
