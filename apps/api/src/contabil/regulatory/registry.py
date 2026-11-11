"""Registry regulatório mínimo (ADR 002 e ADR 031).

O leiaute fica como dado versionado em `data/<obrigação>/*.json`, com fonte, data de consulta e
vigência por ano-calendário. O código só escolhe a versão e lê os campos; nenhuma regra fiscal
fica escondida em condicional.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from functools import lru_cache
from pathlib import Path

DATA = Path(__file__).resolve().parent / "data"


@dataclass(frozen=True)
class LayoutField:
    order: int
    name: str
    type: str
    size: int | None
    decimals: int | None
    required: bool


@dataclass(frozen=True)
class Layout:
    obligation: str
    version: str
    valid_from_year: int
    valid_to_year: int | None
    source: dict
    verified: bool
    unverified: tuple[str, ...]
    file: dict
    structure: dict
    constants: dict
    codes: dict
    product_mappings: dict
    preview_defaults: dict
    conditional_required: tuple[dict, ...]
    registers: dict[str, tuple[LayoutField, ...]] = field(repr=False)

    def covers(self, fiscal_year: int) -> bool:
        return self.valid_from_year <= fiscal_year and (self.valid_to_year is None or fiscal_year <= self.valid_to_year)

    def fields(self, register: str) -> tuple[LayoutField, ...]:
        try:
            return self.registers[register]
        except KeyError as exc:
            raise KeyError(f"O registro {register} não está no leiaute {self.obligation} {self.version}.") from exc


class LayoutNotFound(LookupError):
    pass


def parse_layout(obligation: str, raw: dict) -> Layout:
    registers = {
        code: tuple(
            LayoutField(
                order=int(item["order"]),
                name=item["name"],
                type=item["type"],
                size=item.get("size"),
                decimals=item.get("decimals"),
                required=bool(item.get("required")),
            )
            for item in sorted(data["fields"], key=lambda entry: int(entry["order"]))
        )
        for code, data in raw["registers"].items()
    }
    return Layout(
        obligation=obligation,
        version=str(raw["layout_version"]),
        valid_from_year=int(raw["valid_from_year"]),
        valid_to_year=None if raw.get("valid_to_year") is None else int(raw["valid_to_year"]),
        source=raw.get("source", {}),
        verified=bool(raw.get("verified")),
        unverified=tuple(raw.get("unverified", ())),
        file=raw["file"],
        structure=raw["structure"],
        constants=raw.get("constants", {}),
        codes=raw.get("codes", {}),
        product_mappings=raw.get("product_mappings", {}),
        preview_defaults=raw.get("preview_defaults", {}),
        conditional_required=tuple(raw.get("conditional_required", ())),
        registers=registers,
    )


@lru_cache(maxsize=8)
def layouts(obligation: str) -> tuple[Layout, ...]:
    folder = DATA / obligation
    found = [parse_layout(obligation, json.loads(path.read_text(encoding="utf-8"))) for path in sorted(folder.glob("*.json"))]
    return tuple(found)


def select_layout(candidates: tuple[Layout, ...] | list[Layout], fiscal_year: int) -> Layout:
    """A versão em vigor no ano-calendário. Se duas cobrem o ano, vale a de vigência mais recente."""
    matching = [layout for layout in candidates if layout.covers(fiscal_year)]
    if not matching:
        raise LayoutNotFound(f"Nenhum leiaute cobre o ano-calendário {fiscal_year}.")
    return max(matching, key=lambda layout: layout.valid_from_year)


def layout_for(obligation: str, fiscal_year: int) -> Layout:
    return select_layout(layouts(obligation), fiscal_year)


@dataclass(frozen=True)
class IncomeNature:
    """Linha da Tabela 01 da EFD-Reinf (natureza do rendimento). Não traz alíquota."""

    code: str
    description: str
    beneficiary_kind: str
    taxes: tuple[str, ...]

    def as_dict(self) -> dict:
        return {"code": self.code, "description": self.description, "beneficiary_kind": self.beneficiary_kind}


@dataclass(frozen=True)
class IncomeNatureTable:
    version: str
    layout_version: str
    source: dict
    natures: dict[str, IncomeNature]

    def items(self, beneficiary_kind: str | None = None) -> list[IncomeNature]:
        return [nature for nature in self.natures.values() if beneficiary_kind is None or nature.beneficiary_kind == beneficiary_kind]


@lru_cache(maxsize=1)
def reinf_natures() -> IncomeNatureTable:
    """Recorte da Tabela 01 usado pela prévia da EFD-Reinf (ADR 032)."""
    raw = json.loads((DATA / "reinf" / "natureza-rendimentos.json").read_text(encoding="utf-8"))
    natures = {
        item["code"]: IncomeNature(
            code=item["code"],
            description=item["description"],
            beneficiary_kind=item["beneficiary_kind"],
            taxes=tuple(item.get("taxes", ())),
        )
        for item in raw["natures"]
    }
    return IncomeNatureTable(version=str(raw["version"]), layout_version=str(raw["layout_version"]), source=raw.get("source", {}), natures=natures)


@lru_cache(maxsize=1)
def uf_codes() -> dict[str, str]:
    """Sigla da UF para o código IBGE de dois dígitos."""
    return dict(json.loads((DATA / "ufs.json").read_text(encoding="utf-8"))["ufs"])
