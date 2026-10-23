from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class LineIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    account_id: str = Field(min_length=1, max_length=160)
    side: Literal["debit", "credit"]
    amount: str
    description: str = Field(min_length=1, max_length=1000)
    cost_center_id: str | None = Field(default=None, max_length=160)
    dimension_values: dict[str, str] = Field(default_factory=dict)

    @field_validator("dimension_values")
    @classmethod
    def limit_dimensions(cls, value: dict[str, str]) -> dict[str, str]:
        if len(value) > 20:
            raise ValueError("no máximo 20 dimensões")
        for key, item in value.items():
            if len(key) > 160 or len(item) > 160:
                raise ValueError("dimensão excede 160 caracteres")
        return value


class JournalCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    legal_entity_id: str = Field(min_length=1, max_length=160)
    period_id: str = Field(min_length=1, max_length=80)
    currency: str = Field(pattern=r"^[A-Z]{3}$")
    entry_date: date
    description: str = Field(min_length=1, max_length=2000)
    lines: list[LineIn] = Field(min_length=2, max_length=500)
    source_type: Literal[
        "manual",
        "import",
        "payable",
        "receivable",
        "bank",
        "inventory",
        "asset",
        "fiscal_document",
        "adjustment",
        "reversal",
    ] = "manual"
    source_id: str | None = Field(default=None, max_length=200)
    source_hash: str | None = Field(default=None, max_length=128)


class AccountCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    code: str = Field(min_length=1, max_length=40)
    name: str = Field(min_length=1, max_length=200)
    account_type: Literal["asset", "liability", "equity", "revenue", "expense"]
    postable: bool
    parent_id: str | None = Field(default=None, max_length=160)


class ReasonBody(BaseModel):
    model_config = ConfigDict(extra="forbid")

    reason: str = Field(min_length=3, max_length=2000)
