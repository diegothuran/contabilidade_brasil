from __future__ import annotations

import csv
import hashlib
import re
from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from xml.etree import ElementTree

from contabil.platform.money import format_amount

_AMOUNT = re.compile(r"^-?[0-9]+(\.[0-9]{1,6})?$")
_SGML_VALUE = re.compile(r"<([A-Za-z0-9]+)>([^<\r\n]*)")
_CSV_COLUMNS = ("date", "description", "amount", "external_id")


class StatementParseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class ParsedTransaction:
    date: date
    amount: Decimal
    direction: str
    description: str
    external_id: str | None


@dataclass(frozen=True)
class ParsedStatement:
    format: str
    start_date: date | None
    end_date: date | None
    closing_balance: Decimal | None
    transactions: list[ParsedTransaction]


def normalize_description(value: str) -> str:
    return re.sub(r"\s+", " ", value.casefold()).strip()


def fingerprint(
    bank_account_id: str,
    *,
    posted_on: date,
    amount: Decimal,
    direction: str,
    description: str,
    external_id: str | None,
) -> str:
    external = external_id.strip() if external_id else ""
    if external:
        material = f"{bank_account_id}|{external}"
    else:
        material = "|".join(
            [
                bank_account_id,
                posted_on.isoformat(),
                format_amount(amount),
                direction,
                normalize_description(description),
            ]
        )
    return hashlib.sha256(material.encode("utf-8")).hexdigest()


def parse_statement(content: bytes) -> ParsedStatement:
    if not content or not content.strip():
        raise StatementParseError("UNSUPPORTED_FORMAT", "Arquivo de extrato vazio.")
    sample = content.lstrip()[:800].upper()
    if sample.startswith(b"OFXHEADER") or sample.startswith(b"<?XML") or sample.startswith(b"<?OFX") or b"<OFX" in sample:
        return _parse_ofx(content)
    if b"DATE" in sample and b"AMOUNT" in sample:
        return _parse_csv(content)
    raise StatementParseError("UNSUPPORTED_FORMAT", "Formato de extrato não suportado. Use CSV ou OFX.")


def _parse_csv(content: bytes) -> ParsedStatement:
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise StatementParseError("INVALID_ENCODING", "O extrato CSV precisa estar em UTF-8.") from exc
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise StatementParseError("MISSING_COLUMN", "O arquivo não tem cabeçalho.")
    delimiter = ";" if ";" in lines[0] else ","
    header = [cell.strip().lower() for cell in next(csv.reader([lines[0]], delimiter=delimiter))]
    missing = [name for name in _CSV_COLUMNS if name not in header]
    if missing:
        raise StatementParseError("MISSING_COLUMN", "Colunas ausentes: " + ", ".join(missing))
    transactions: list[ParsedTransaction] = []
    for line in lines[1:]:
        if not line.strip():
            continue
        cells = next(csv.reader([line], delimiter=delimiter))
        values = {name: "" for name in header}
        for index, name in enumerate(header):
            if index < len(cells):
                values[name] = cells[index].strip()
        amount, direction = _signed_amount(values["amount"])
        external = values["external_id"] or None
        transactions.append(
            ParsedTransaction(
                date=_csv_date(values["date"]),
                amount=amount,
                direction=direction,
                description=values["description"][:2000],
                external_id=external,
            )
        )
    return ParsedStatement("csv", _min_date(transactions), _max_date(transactions), None, transactions)


def _parse_ofx(content: bytes) -> ParsedStatement:
    text = _decode_ofx(content)
    start = text.find("<")
    if start < 0:
        raise StatementParseError("UNSUPPORTED_FORMAT", "O OFX não contém transações legíveis.")
    body = text[start:]
    if body.lstrip()[:5].lower().startswith("<?xml") or "<?OFX" in body[:200].upper():
        try:
            return _parse_xml(re.sub(r"<\?[^?]*\?>", "", body, count=1))
        except StatementParseError:
            raise
        except ElementTree.ParseError:
            return _parse_sgml(body)
    return _parse_sgml(body)


def _decode_ofx(content: bytes) -> str:
    header_end = content.upper().find(b"<OFX")
    header = content[: header_end if header_end > 0 else min(len(content), 500)]
    header_text = header.decode("ascii", errors="ignore")
    match = re.search(r"CHARSET:([^\r\n]+)", header_text, re.IGNORECASE)
    charset = match.group(1).strip().upper() if match else ""
    if charset in {"1252", "CP1252", "WINDOWS-1252"}:
        try:
            return content.decode("cp1252")
        except UnicodeError as exc:
            raise StatementParseError("INVALID_ENCODING", "Não foi possível ler o extrato em cp1252.") from exc
    try:
        return content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise StatementParseError("INVALID_ENCODING", "Não foi possível ler o extrato.") from exc


def _parse_sgml(text: str) -> ParsedStatement:
    transactions = [_tx_from_map(_sgml_map(chunk)) for chunk in re.split(r"(?i)<STMTTRN>", text)[1:]]
    closing = _optional_amount(_tag_value(text[text.upper().find("<LEDGERBAL>") :], "BALAMT") if "<LEDGERBAL>" in text.upper() else None)
    return ParsedStatement(
        "ofx",
        _ofx_date(_tag_value(text, "DTSTART"), required=False),
        _ofx_date(_tag_value(text, "DTEND"), required=False),
        closing,
        transactions,
    )


def _parse_xml(text: str) -> ParsedStatement:
    root = ElementTree.fromstring(text)
    transactions = [_tx_from_map(_xml_map(element)) for element in root.iter() if _local(element.tag) == "STMTTRN"]
    closing: Decimal | None = None
    for element in root.iter():
        if _local(element.tag) == "LEDGERBAL":
            closing = _optional_amount(_child_text(element, "BALAMT") or None)
    start = _first_text(root, "DTSTART")
    end = _first_text(root, "DTEND")
    return ParsedStatement(
        "ofx",
        _ofx_date(start, required=False),
        _ofx_date(end, required=False),
        closing,
        transactions,
    )


def _sgml_map(block: str) -> dict[str, str]:
    return {match.group(1).upper(): match.group(2).strip() for match in _SGML_VALUE.finditer(block)}


def _tag_value(text: str, tag: str) -> str | None:
    match = re.search(rf"(?i)<{tag}>\s*([^<\r\n]*)", text)
    if match is None:
        return None
    value = match.group(1).strip()
    return value or None


def _xml_map(element: ElementTree.Element) -> dict[str, str]:
    return {_local(child.tag): (child.text or "").strip() for child in list(element)}


def _child_text(element: ElementTree.Element, name: str) -> str:
    for child in list(element):
        if _local(child.tag) == name and child.text:
            return child.text.strip()
    return ""


def _first_text(root: ElementTree.Element, name: str) -> str | None:
    for element in root.iter():
        if _local(element.tag) == name and element.text and element.text.strip():
            return element.text.strip()
    return None


def _local(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].upper()


def _tx_from_map(values: dict[str, str]) -> ParsedTransaction:
    amount, direction = _signed_amount(values.get("TRNAMT", ""))
    description = (values.get("MEMO") or values.get("NAME") or "").strip()[:2000]
    external = (values.get("FITID") or "").strip() or None
    posted = _ofx_date(values.get("DTPOSTED"), required=True)
    if posted is None:
        raise StatementParseError("INVALID_DATE", "Data do extrato inválida.")
    return ParsedTransaction(
        date=posted,
        amount=amount,
        direction=direction,
        description=description,
        external_id=external,
    )


def _signed_amount(value: str) -> tuple[Decimal, str]:
    text = value.strip()
    if _AMOUNT.fullmatch(text) is None:
        raise StatementParseError("INVALID_AMOUNT", "Valor do extrato inválido.")
    amount = Decimal(text)
    if amount == 0:
        raise StatementParseError("INVALID_AMOUNT", "Valor do extrato inválido.")
    if amount < 0:
        return abs(amount), "outflow"
    return amount, "inflow"


def _optional_amount(value: str | None) -> Decimal | None:
    if value is None or not value.strip():
        return None
    text = value.strip()
    if _AMOUNT.fullmatch(text) is None:
        raise StatementParseError("INVALID_AMOUNT", "Saldo do extrato inválido.")
    return Decimal(text)


def _csv_date(value: str) -> date:
    text = value.strip()
    for fmt in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    raise StatementParseError("INVALID_DATE", "Data do extrato inválida.")


def _ofx_date(value: str | None, *, required: bool) -> date | None:
    if value is None or not str(value).strip():
        if required:
            raise StatementParseError("INVALID_DATE", "Data do extrato inválida.")
        return None
    match = re.match(r"(\d{8})", str(value).strip())
    if match is None:
        raise StatementParseError("INVALID_DATE", "Data do extrato inválida.")
    try:
        return datetime.strptime(match.group(1), "%Y%m%d").date()
    except ValueError as exc:
        raise StatementParseError("INVALID_DATE", "Data do extrato inválida.") from exc


def _min_date(transactions: list[ParsedTransaction]) -> date | None:
    if not transactions:
        return None
    return min(item.date for item in transactions)


def _max_date(transactions: list[ParsedTransaction]) -> date | None:
    if not transactions:
        return None
    return max(item.date for item in transactions)
