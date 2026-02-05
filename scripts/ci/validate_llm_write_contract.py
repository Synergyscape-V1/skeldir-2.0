#!/usr/bin/env python3
from __future__ import annotations

import json
import sys
from collections.abc import Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class ContractTarget(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    schema_name: str = Field(alias="schema")
    table: str
    tenant_scoped: bool = True


class RequiredColumn(BaseModel):
    name: str
    type: str
    nullable: bool
    constraints: list[str] = Field(default_factory=list)
    notes: str | None = None


class B07TargetRowShape(BaseModel):
    required_columns: list[RequiredColumn]
    required_uniques: list[list[str]]


class LLMWriteContract(BaseModel):
    contract_id: str
    contract_version: str
    owner: Literal["llm"]
    purpose: str
    targets: list[ContractTarget]
    b07_target_row_shape: B07TargetRowShape


@dataclass(frozen=True, slots=True)
class ValidationResult:
    path: Path
    ok: bool
    error: str | None = None


def _read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def validate_contract(path: Path) -> ValidationResult:
    try:
        LLMWriteContract.model_validate(_read_json(path))
    except (OSError, json.JSONDecodeError, ValidationError) as exc:
        return ValidationResult(path=path, ok=False, error=str(exc))
    return ValidationResult(path=path, ok=True)


def main(argv: Sequence[str]) -> int:
    if len(argv) < 2:
        print("usage: validate_llm_write_contract.py <contract.json> [more.json ...]")
        return 2

    failures: list[ValidationResult] = []
    for raw in argv[1:]:
        result = validate_contract(Path(raw))
        if not result.ok:
            failures.append(result)

    if failures:
        print("LLM write contract validation failed:")
        for entry in failures:
            print(f"  - {entry.path}: {entry.error}")
        return 1

    print("LLM write contract validation passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
