from decimal import Decimal

from contabil.imports.csv_layout import CsvParseError, group_journals, parse_csv
from contabil.imports.service import Classified, _money, summarize


def test_parser_accepts_semicolon_and_comma() -> None:
    semicolon = "external_id;code;name;account_type;postable;parent_code\ndemo;1.1;Caixa;asset;true;\n"
    comma = "external_id,code,name,account_type,postable,parent_code\ndemo,1.1,Caixa,asset,true,\n"
    assert parse_csv(semicolon.encode(), "chart_of_accounts")[0].values["code"] == "1.1"
    assert parse_csv(comma.encode(), "chart_of_accounts")[0].values["name"] == "Caixa"


def test_parser_rejects_missing_header() -> None:
    try:
        parse_csv(b"code;name\n1;Caixa\n", "chart_of_accounts")
    except CsvParseError as exc:
        assert exc.code == "MISSING_COLUMN"
    else:
        raise AssertionError("cabeçalho incompleto deveria falhar")


def test_amounts_use_decimal_point() -> None:
    assert _money("10.50") == Decimal("10.50")
    assert _money("0") == Decimal("0")
    assert _money("10,50") is None
    assert _money("-1") is None


def test_journals_group_by_external_id() -> None:
    header = "external_journal_id,entry_date,description,account_code,side,amount,line_description,cost_center_code\n"
    body = "j1,2026-09-15,Compra,5.1.01,debit,10.00,Despesa,\nj2,2026-09-15,Outra,1.1.02,debit,3.00,Banco,\nj1,2026-09-15,Compra,2.1.01,credit,10.00,Fornecedor,\n"
    grouped = group_journals(parse_csv((header + body).encode(), "journal"))
    assert list(grouped) == ["j1", "j2"]
    assert len(grouped["j1"]) == 2


def test_summary_ignores_invalid_rows() -> None:
    rows = [
        Classified("file", "journal", 2, "j1", {}, debit=Decimal("10"), credit=Decimal("0")),
        Classified("file", "journal", 3, "j1", {}, status="invalid", debit=Decimal("4"), credit=Decimal("0")),
        Classified("file", "journal", 4, "j1", {}, status="already_imported", debit=Decimal("9"), credit=Decimal("9")),
    ]
    received, valid, invalid, already, debit, credit = summarize(rows)
    assert (received, valid, invalid, already) == (3, 1, 1, 1)
    assert debit == Decimal("10")
    assert credit == Decimal("0")
