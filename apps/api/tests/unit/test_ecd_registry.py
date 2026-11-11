from __future__ import annotations

from dataclasses import replace
from datetime import date
from decimal import Decimal

import pytest

from contabil.platform.errors import DomainError
from contabil.regulatory.ecd_preview import check_file
from contabil.regulatory.registration import RegistrationInput, validate_registration
from contabil.regulatory.registry import LayoutNotFound, layout_for, layouts, select_layout, uf_codes
from contabil.regulatory.writer import RecordWriter

RECORTE = (
    "0000 0001 0007 0990 I001 I010 I030 I050 I052 I150 I155 I200 I250 I350 I355 I990 "
    "J001 J005 J100 J150 J900 J930 J990 9001 9900 9990 9999"
).split()


def _layout():
    return layout_for("ecd", 2026)


def test_leiaute_9_comes_from_the_official_manual_with_the_confirmed_constants():
    layout = _layout()
    assert layout.version == "9"
    assert layout.verified is True
    assert layout.source["pdf"].startswith("http://sped.rfb.gov.br/")
    assert layout.source["accessed_on"] == "2026-11-08"
    assert layout.constants["COD_VER_LC"] == "9.00"
    assert layout.file == {
        **layout.file,
        "encoding": "ISO-8859-1",
        "delimiter": "|",
        "line_ending": "\r\n",
        "decimal_separator": ",",
    }
    assert set(RECORTE) <= set(layout.registers)
    names = [item.name for item in layout.fields("J930")]
    assert names == [
        "REG", "IDENT_NOM", "IDENT_CPF_CNPJ", "IDENT_QUALIF", "COD_ASSIN", "IND_CRC",
        "EMAIL", "FONE", "UF_CRC", "NUM_SEQ_CRC", "DT_CRC", "IND_RESP_LEGAL",
    ]
    assert [item.name for item in layout.fields("0000")][-1] == "COD_PLAN_REF"
    assert layout.codes["COD_ASSIN"]["900"] == "Contador/Contabilista"


def test_version_is_chosen_by_the_calendar_year():
    nine = _layout()
    older = replace(nine, version="8", valid_from_year=2018, valid_to_year=2019)
    future = replace(nine, version="10", valid_from_year=2030, valid_to_year=None)
    nine_bounded = replace(nine, valid_to_year=2029)
    candidates = (older, nine_bounded, future)
    assert select_layout(candidates, 2019).version == "8"
    assert select_layout(candidates, 2026).version == "9"
    assert select_layout(candidates, 2031).version == "10"
    with pytest.raises(LayoutNotFound):
        select_layout(candidates, 2010)
    assert len(layouts("ecd")) >= 1
    with pytest.raises(LayoutNotFound):
        layout_for("ecd", 2019)


def test_writer_follows_the_layout_fields_separators_and_line_ending():
    writer = RecordWriter(_layout())
    writer.add("I155", {
        "COD_CTA": "1.1.02",
        "VL_SLD_INI": Decimal("0"),
        "IND_DC_INI": "D",
        "VL_DEB": Decimal("1500.5"),
        "VL_CRED": Decimal("200"),
        "VL_SLD_FIN": Decimal("1300.50"),
        "IND_DC_FIN": "D",
    })
    line = writer.line("I155", writer._records[0][1])
    assert line == "|I155|1.1.02||0,00|D|1500,50|200,00|1300,50|D|"
    assert writer.line("I010", {"IND_ESC": "G"}) == "|I010|G|9.00|"
    assert writer.line("I150", {"DT_INI": date(2026, 1, 1), "DT_FIN": date(2026, 1, 31)}) == "|I150|01012026|31012026|"
    assert writer.violations == []


def test_writer_flags_what_the_layout_does_not_accept():
    writer = RecordWriter(_layout())
    writer.line("I250", {"COD_CTA": "1", "VL_DC": Decimal("10.005"), "IND_DC": "D", "HIST": "a|b"})
    writer.line("0000", {"UF": "PER"})
    writer.line("J930", {"IDENT_NOM": "Fulana", "IDENT_CPF_CNPJ": "52998224725", "IDENT_QUALIF": "Contador/Contabilista", "COD_ASSIN": "900", "IND_RESP_LEGAL": "N"})
    rules = {(item.register, item.field, item.rule) for item in writer.violations}
    assert ("I250", "VL_DC", "precision") in rules
    assert ("I250", "HIST", "characters") in rules
    assert ("0000", "UF", "size") in rules
    assert ("0000", "CNPJ", "required") in rules
    assert ("J930", "EMAIL", "REGRA_OBRIGATORIO_CONTADOR") in rules
    assert ("J930", "DT_CRC", "REGRA_ADVERTENCIA_CONTADOR") in rules
    severities = {item.field: item.severity for item in writer.violations if item.register == "J930"}
    assert severities["EMAIL"] == "error"
    assert severities["DT_CRC"] == "warning"
    with pytest.raises(ValueError):
        writer.add("I010", {"CAMPO_INVENTADO": "x"})


def test_writer_closes_blocks_and_counts_registers_in_9900():
    layout = _layout()
    writer = RecordWriter(layout)
    writer.add("0000", {"DT_INI": date(2026, 1, 1), "DT_FIN": date(2026, 12, 31), "NOME": "Empresa", "CNPJ": "11222333000181", "UF": "PE", "IND_SIT_INI_PER": "0", "IND_NIRE": "0", "IND_FIN_ESC": "0", "IND_GRANDE_PORTE": "0", "TIP_ECD": "0", "IDENT_MF": "N", "IND_ESC_CONS": "N", "IND_CENTRALIZADA": "0", "IND_MUDANC_PC": "0"})
    writer.add("I010", {"IND_ESC": "G"})
    writer.add("I030", {"NUM_ORD": 1, "NAT_LIVR": "DIARIO", "NOME": "Empresa", "CNPJ": "11222333000181", "DT_EX_SOCIAL": date(2026, 12, 31)})
    writer.add("I200", {"NUM_LCTO": "1", "DT_LCTO": date(2026, 3, 1), "VL_LCTO": Decimal("10"), "IND_LCTO": "N"})
    writer.add("I250", {"COD_CTA": "1", "VL_DC": Decimal("10"), "IND_DC": "D"})
    writer.add("I250", {"COD_CTA": "2", "VL_DC": Decimal("10"), "IND_DC": "C"})
    content = writer.finish()
    lines = content.split("\r\n")
    assert content.endswith("\r\n")
    lines = lines[:-1]
    assert lines[0].startswith("|0000|LECD|01012026|31122026|")
    assert lines[1] == "|0001|0|"
    assert lines[2] == "|0990|3|"
    assert lines[3] == "|I001|0|"
    assert "|J001|1|" in lines
    assert "|J990|2|" in lines
    assert lines[-1] == f"|9999|{len(lines)}|"
    assert f"|I030|TERMO DE ABERTURA|1|DIARIO|{len(lines)}|Empresa||11222333000181||||31122026|" in lines
    assert "|9900|I250|2|" in lines
    assert "|9900|9900|" + str(sum(1 for line in lines if line.startswith("|9900|"))) + "|" in lines
    assert "|9900|9999|1|" in lines
    assert writer.counts["I250"] == 2
    checks = check_file(content, layout)
    assert checks["i200_matches_i250"] is True
    assert checks["block_counts"] is True
    broken = content.replace("|9900|I250|2|", "|9900|I250|3|")
    assert check_file(broken, layout)["block_counts"] is False
    unbalanced = content.replace("|I250|2||10,00|C|", "|I250|2||9,00|C|")
    assert check_file(unbalanced, layout)["i200_matches_i250"] is False


def _registration(**overrides) -> RegistrationInput:
    base = {
        "uf": "pe",
        "municipality_ibge": "2611606",
        "registry_kind": "junta",
        "nire": "26.2.0000001-1",
        "registry_date": date(2020, 5, 4),
        "special_situation": None,
        "book_number": 3,
    }
    base.update(overrides)
    return RegistrationInput(**base)


def test_registration_accepts_recife_with_a_jucepe_nire_and_a_cartorio_without_nire():
    clean = validate_registration(_registration(nire="26200000011"), today=date(2026, 11, 8))
    assert clean.uf == "PE"
    assert clean.nire == "26200000011"
    cartorio = validate_registration(_registration(registry_kind="cartorio", nire=None), today=date(2026, 11, 8))
    assert cartorio.nire is None
    assert uf_codes()["PE"] == "26"
    assert len(uf_codes()) == 27


@pytest.mark.parametrize(
    "overrides, field",
    [
        ({"uf": "XX"}, "uf"),
        ({"municipality_ibge": "3550308"}, "municipality_ibge"),
        ({"municipality_ibge": "26116"}, "municipality_ibge"),
        ({"nire": "35200000011"}, "nire"),
        ({"nire": None}, "nire"),
        ({"nire": "2620000"}, "nire"),
        ({"registry_kind": "cartorio"}, "nire"),
        ({"registry_kind": "outro"}, "registry_kind"),
        ({"special_situation": "9"}, "special_situation"),
        ({"registry_date": date(2027, 1, 1)}, "registry_date"),
        ({"conversion_date": date(2027, 1, 1)}, "conversion_date"),
        ({"registry_kind": "cartorio", "nire": None, "conversion_date": date(2023, 9, 1)}, "conversion_date"),
        ({"book_number": 0}, "book_number"),
    ],
)
def test_registration_refuses_what_does_not_match_the_uf(overrides, field):
    with pytest.raises(DomainError) as error:
        validate_registration(_registration(**({"nire": "26200000011"} | overrides)), today=date(2026, 11, 8))
    assert error.value.status_code == 400
    assert field in {item["loc"][0] for item in error.value.errors}


def test_registration_keeps_the_conversion_date_only_at_the_junta():
    clean = validate_registration(_registration(nire="26200000011", conversion_date=date(2023, 9, 1)), today=date(2026, 11, 8))
    assert clean.conversion_date == date(2023, 9, 1)
    cartorio = validate_registration(_registration(registry_kind="cartorio", nire=None), today=date(2026, 11, 8))
    assert cartorio.conversion_date is None
