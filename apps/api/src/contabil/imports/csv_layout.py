from __future__ import annotations

import csv
from dataclasses import dataclass

LAYOUTS: dict[str, tuple[str, ...]] = {
    "chart_of_accounts": ("external_id", "code", "name", "account_type", "postable", "parent_code"),
    "opening_balance": ("external_account_id", "account_code", "debit", "credit"),
    "journal": (
        "external_journal_id",
        "entry_date",
        "description",
        "account_code",
        "side",
        "amount",
        "line_description",
        "cost_center_code",
    ),
}

TEMPLATES = {kind: ";".join(columns) for kind, columns in LAYOUTS.items()}


class CsvParseError(Exception):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message
        super().__init__(message)


@dataclass(frozen=True)
class CsvRow:
    row_no: int
    values: dict[str, str]


def parse_csv(content: bytes, kind: str) -> list[CsvRow]:
    columns = LAYOUTS.get(kind)
    if columns is None:
        raise CsvParseError("MISSING_COLUMN", "Tipo de arquivo não suportado nesta fase.")
    try:
        text = content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise CsvParseError("INVALID_ENCODING", "O arquivo precisa estar em UTF-8.") from exc
    lines = text.splitlines()
    if not lines or not lines[0].strip():
        raise CsvParseError("MISSING_COLUMN", "O arquivo não tem cabeçalho.")
    delimiter = ";" if ";" in lines[0] else ","
    header = [cell.strip() for cell in next(csv.reader([lines[0]], delimiter=delimiter))]
    missing = [name for name in columns if name not in header]
    if missing:
        raise CsvParseError("MISSING_COLUMN", "Colunas ausentes: " + ", ".join(missing))
    rows: list[CsvRow] = []
    for line_no, line in enumerate(lines[1:], start=2):
        if not line.strip():
            continue
        cells = next(csv.reader([line], delimiter=delimiter))
        values = {name: "" for name in header}
        for index, name in enumerate(header):
            if index < len(cells):
                values[name] = cells[index].strip()
        rows.append(CsvRow(row_no=line_no, values=values))
    return rows


def group_journals(rows: list[CsvRow]) -> dict[str, list[CsvRow]]:
    grouped: dict[str, list[CsvRow]] = {}
    for row in rows:
        key = row.values.get("external_journal_id", "")
        grouped.setdefault(key, []).append(row)
    return grouped
