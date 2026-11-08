"""Serializa registros de um leiaute SPED a partir do dado do registry (ADR 031).

O escritor não conhece campo fiscal. Ele lê, do leiaute, a ordem, o tipo, o tamanho, os decimais,
a obrigatoriedade, as constantes, a estrutura dos blocos e as obrigatoriedades condicionais.
O que não cabe no leiaute vira `Violation`, e a prévia mostra como pendência.
"""

from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import date
from decimal import ROUND_HALF_UP, Decimal

from contabil.regulatory.registry import Layout, LayoutField

_CONTROL = re.compile(r"[\x00-\x1f]")


@dataclass(frozen=True)
class Violation:
    register: str
    field: str
    rule: str
    severity: str
    message: str


class RecordWriter:
    def __init__(self, layout: Layout) -> None:
        self.layout = layout
        self._records: list[tuple[str, dict]] = []
        self.violations: list[Violation] = []
        self.counts: dict[str, int] = {}

    def add(self, register: str, values: dict | None = None) -> None:
        values = dict(values or {})
        known = {item.name for item in self.layout.fields(register)}
        unknown = set(values) - known
        if unknown:
            raise ValueError(f"Campos fora do leiaute em {register}: {', '.join(sorted(unknown))}.")
        self._records.append((register, values))

    # Montagem do arquivo

    def finish(self) -> str:
        structure = self.layout.structure
        blocks = structure["blocks"]
        file_open = structure.get("file_open", "0000")
        by_block: dict[str, list[tuple[str, dict]]] = {block: [] for block in structure["block_order"]}
        head: list[tuple[str, dict]] = []
        for register, values in self._records:
            if register == file_open:
                head.append((register, values))
                continue
            block = self.layout_block(register)
            if block not in by_block:
                raise ValueError(f"O bloco {block} do registro {register} não está na ordem do leiaute.")
            by_block[block].append((register, values))

        ordered: list[tuple[str, dict]] = []
        count_register = structure["register_count"]
        file_close = structure["file_close"]
        for block in structure["block_order"]:
            spec = blocks[block]
            body = by_block[block]
            if block == count_register["register"][0]:
                # O bloco 9 sempre tem dados: as linhas 9900 entram abaixo.
                ordered.append((spec["open"], {"IND_DAD": "0"}))
                continue
            opening = head if block == file_open[0] else []
            lines = opening + [(spec["open"], {"IND_DAD": "0" if body or opening else "1"})] + body
            lines.append((spec["close"], {spec["count_field"]: len(lines) + 1}))
            ordered.extend(lines)

        # Bloco 9: uma linha 9900 por tipo, depois o encerramento do bloco e do arquivo.
        last_block = blocks[count_register["register"][0]]
        types_before = Counter(register for register, _ in ordered)
        extra = [last_block["close"], file_close["register"]]
        type_names = list(dict.fromkeys([register for register, _ in ordered] + [count_register["register"], *extra]))
        types = Counter(types_before)
        types[count_register["register"]] = len(type_names)
        for name in extra:
            types[name] = 1
        nine_start = next(index for index, (register, _) in enumerate(ordered) if register == last_block["open"])
        for name in type_names:
            ordered.append((count_register["register"], {count_register["type_field"]: name, count_register["count_field"]: types[name]}))
        block_nine = len(ordered) - nine_start + 2
        ordered.append((last_block["close"], {last_block["count_field"]: block_nine}))
        total = len(ordered) + 1
        ordered.append((file_close["register"], {file_close["count_field"]: total}))

        for register, field_name in structure.get("total_line_fields", ()):
            for index, (name, values) in enumerate(ordered):
                if name == register:
                    ordered[index] = (name, {**values, field_name: total})

        self.counts = dict(Counter(register for register, _ in ordered))
        ending = self.layout.file["line_ending"]
        return "".join(self.line(register, values) + ending for register, values in ordered)

    def layout_block(self, register: str) -> str:
        return register[0]

    # Uma linha

    def line(self, register: str, values: dict) -> str:
        fields = self.layout.fields(register)
        merged = {name: value for name, value in self.layout.constants.items() if name in {item.name for item in fields}}
        merged.update(values)
        merged.setdefault("REG", register)
        self._conditional(register, merged)
        delimiter = self.layout.file["delimiter"]
        cells = [self._cell(register, item, merged.get(item.name)) for item in fields]
        return delimiter + delimiter.join(cells) + delimiter

    def _conditional(self, register: str, values: dict) -> None:
        for rule in self.layout.conditional_required:
            if rule["register"] != register:
                continue
            if any(str(values.get(name, "")) != expected for name, expected in rule["when"].items()):
                continue
            for name in rule["fields"]:
                if _empty(values.get(name)):
                    self._flag(register, name, rule["rule"], rule["severity"], f"{register}.{name} é exigido quando {_when(rule['when'])}.")

    def _cell(self, register: str, item: LayoutField, value) -> str:
        if _empty(value):
            if item.required:
                self._flag(register, item.name, "required", "error", f"{register}.{item.name} é obrigatório e está vazio.")
            return ""
        if isinstance(value, date):
            return value.strftime(self.layout.file["date_format"])
        if isinstance(value, bool):
            raise ValueError(f"{register}.{item.name}: use texto, não booleano.")
        if isinstance(value, Decimal):
            return self._number(register, item, value)
        if isinstance(value, int):
            return str(value)
        return self._text(register, item, str(value))

    def _number(self, register: str, item: LayoutField, value: Decimal) -> str:
        if value < 0:
            self._flag(register, item.name, "sign", "error", f"{register}.{item.name} não aceita sinal; informe o indicador D ou C.")
            value = -value
        places = item.decimals or 0
        quantum = Decimal(1).scaleb(-places)
        rounded = value.quantize(quantum, rounding=ROUND_HALF_UP)
        if rounded != value:
            self._flag(register, item.name, "precision", "error", f"{register}.{item.name} tem mais de {places} casas decimais ({value}).")
        text = format(rounded, "f")
        return text.replace(".", self.layout.file["decimal_separator"])

    def _text(self, register: str, item: LayoutField, value: str) -> str:
        cleaned = _CONTROL.sub(" ", value).replace(self.layout.file["delimiter"], "/").strip()
        if cleaned != value.strip():
            self._flag(register, item.name, "characters", "warning", f"{register}.{item.name} tinha | ou caractere de controle, trocado.")
        encoding = self.layout.file["encoding"]
        try:
            cleaned.encode(encoding)
        except UnicodeEncodeError:
            cleaned = cleaned.encode(encoding, errors="replace").decode(encoding)
            self._flag(register, item.name, "encoding", "warning", f"{register}.{item.name} tem caractere fora do {encoding}, trocado por ?.")
        limit = item.size if item.type == "C" and item.size else self.layout.file.get("max_text_length")
        if item.type == "N" and item.size and not cleaned.isdigit():
            self._flag(register, item.name, "numeric", "error", f"{register}.{item.name} aceita só dígitos.")
        if limit and len(cleaned) > limit:
            self._flag(register, item.name, "size", "error", f"{register}.{item.name} passa de {limit} caracteres.")
        if item.type == "N" and item.size and len(cleaned) > item.size:
            self._flag(register, item.name, "size", "error", f"{register}.{item.name} passa de {item.size} dígitos.")
        return cleaned

    def _flag(self, register: str, field_name: str, rule: str, severity: str, message: str) -> None:
        self.violations.append(Violation(register, field_name, rule, severity, message))


def _empty(value) -> bool:
    return value is None or (isinstance(value, str) and value.strip() == "")


def _when(condition: dict) -> str:
    return " e ".join(f"{name} = {value}" for name, value in condition.items())
