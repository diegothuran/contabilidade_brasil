from datetime import date
from decimal import Decimal

from contabil.reconciliation.matching import score_candidate
from contabil.reconciliation.statement_parser import StatementParseError, fingerprint, parse_statement


def test_csv_accepts_semicolon_or_comma_and_signed_amount() -> None:
    semicolon = "date;description;amount;external_id\n2026-09-15;Recebimento;300.00;fit-1\n16/09/2026;Tarifa;-45.90;\n"
    comma = "date,description,amount,external_id\n2026-09-15,Recebimento,300.00,fit-1\n"
    parsed = parse_statement(semicolon.encode())
    assert parsed.format == "csv"
    assert parsed.transactions[0].direction == "inflow"
    assert parsed.transactions[0].external_id == "fit-1"
    assert parsed.transactions[1].direction == "outflow"
    assert parsed.transactions[1].amount == Decimal("45.90")
    assert parsed.transactions[1].date == date(2026, 9, 16)
    assert parsed.transactions[1].external_id is None
    assert parse_statement(comma.encode()).transactions[0].amount == Decimal("300.00")


def test_csv_rejects_missing_column_and_bad_values() -> None:
    try:
        parse_statement(b"date;description;amount\n2026-09-15;X;1.00\n")
    except StatementParseError as exc:
        assert exc.code == "MISSING_COLUMN"
    else:
        raise AssertionError("coluna ausente deveria falhar")
    try:
        parse_statement("date;description;amount;external_id\n2026-09-15;X;10,00;\n".encode())
    except StatementParseError as exc:
        assert exc.code == "INVALID_AMOUNT"
    else:
        raise AssertionError("vírgula decimal deveria falhar")
    try:
        parse_statement("date;description;amount;external_id\n31-09-2026;X;10.00;\n".encode())
    except StatementParseError as exc:
        assert exc.code == "INVALID_DATE"
    else:
        raise AssertionError("data inválida deveria falhar")


def test_ofx_sgml_cp1252_and_xml() -> None:
    sgml = (
        "OFXHEADER:100\nCHARSET:1252\n\n<OFX>\n<STMTTRN>\n<DTPOSTED>20260915120000[-3:BRT]\n"
        "<TRNAMT>300.00\n<FITID>abc\n<MEMO>manutenção\n</STMTTRN>\n"
        "<LEDGERBAL>\n<BALAMT>-10.50\n</LEDGERBAL>\n"
    ).encode("cp1252")
    parsed = parse_statement(sgml)
    assert parsed.format == "ofx"
    assert parsed.transactions[0].date == date(2026, 9, 15)
    assert parsed.transactions[0].direction == "inflow"
    assert parsed.transactions[0].external_id == "abc"
    assert "ç" in parsed.transactions[0].description
    assert parsed.closing_balance == Decimal("-10.50")
    xml = """<?xml version="1.0" encoding="UTF-8"?>
<OFX><BANKTRANLIST><DTSTART>20260901</DTSTART><DTEND>20260930</DTEND>
<STMTTRN><DTPOSTED>20260916</DTPOSTED><TRNAMT>-45.90</TRNAMT><FITID>fee</FITID><NAME>TARIFA</NAME></STMTTRN>
</BANKTRANLIST></OFX>"""
    xml_parsed = parse_statement(xml.encode())
    assert xml_parsed.transactions[0].direction == "outflow"
    assert xml_parsed.transactions[0].description == "TARIFA"
    assert xml_parsed.start_date == date(2026, 9, 1)
    assert xml_parsed.end_date == date(2026, 9, 30)


def test_fingerprint_uses_fitid_or_the_movement() -> None:
    posted = date(2026, 9, 15)
    with_fitid = fingerprint("bank", posted_on=posted, amount=Decimal("10.00"), direction="inflow", description="A", external_id="fit")
    same_fitid = fingerprint("bank", posted_on=posted, amount=Decimal("99.00"), direction="outflow", description="B", external_id="fit")
    other_account = fingerprint("other", posted_on=posted, amount=Decimal("10.00"), direction="inflow", description="A", external_id="fit")
    without = fingerprint("bank", posted_on=posted, amount=Decimal("10.00"), direction="inflow", description="Tarifa", external_id=None)
    changed = fingerprint("bank", posted_on=posted, amount=Decimal("10.00"), direction="inflow", description="Outra", external_id=None)
    assert with_fitid == same_fitid
    assert with_fitid != other_account
    assert without != changed
    assert len(without) == 64


def test_score_explains_amount_date_and_history() -> None:
    perfect, explanation, fields = score_candidate(date(2026, 9, 15), "Recebimento cliente", date(2026, 9, 15), "Recebimento cliente")
    assert perfect == 1.0
    assert explanation == ["Valor idêntico", "Data igual", "Histórico compatível: cliente"]
    assert fields == ["amount", "date", "description"]
    near, near_explanation, _fields = score_candidate(date(2026, 9, 15), "Tarifa", date(2026, 9, 17), "Outro")
    assert near == 0.8
    assert near_explanation[1] == "Data a 2 dias"


def test_unsupported_format_is_a_batch_error() -> None:
    try:
        parse_statement(b"isto nao e extrato")
    except StatementParseError as exc:
        assert exc.code == "UNSUPPORTED_FORMAT"
    else:
        raise AssertionError("formato desconhecido deveria falhar")
