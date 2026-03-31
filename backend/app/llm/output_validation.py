"""Generic output validation contracts and normalization for provider boundary."""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Mapping

from pydantic import BaseModel, ConfigDict, Field, ValidationError


class _StrictOutputModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RouteOutputSchema(_StrictOutputModel):
    route: str = Field(default="noop", min_length=1, max_length=64)
    summary: str = Field(min_length=1, max_length=8000)


class ExplanationOutputSchema(_StrictOutputModel):
    explanation: str = Field(min_length=1, max_length=8000)


class InvestigationOutputSchema(_StrictOutputModel):
    summary: str = Field(min_length=1, max_length=8000)


class BudgetOutputSchema(_StrictOutputModel):
    summary: str = Field(min_length=1, max_length=8000)


@dataclass(frozen=True, slots=True)
class ProviderOutputValidationSpec:
    surface: str
    schema_key: str
    schema_model: type[BaseModel]
    text_field: str
    max_attempts: int = 2


@dataclass(frozen=True, slots=True)
class OutputValidationResult:
    ok: bool
    code: str
    stage: str
    normalized_output_text: str
    normalized_payload: Mapping[str, Any] | None
    schema_key: str | None = None
    normalization_source: str | None = None
    error_detail: str | None = None


ROUTE_VALIDATION_SPEC = ProviderOutputValidationSpec(
    surface="route",
    schema_key="route_v1",
    schema_model=RouteOutputSchema,
    text_field="summary",
)

EXPLANATION_VALIDATION_SPEC = ProviderOutputValidationSpec(
    surface="explanation",
    schema_key="explanation_v1",
    schema_model=ExplanationOutputSchema,
    text_field="explanation",
)

INVESTIGATION_VALIDATION_SPEC = ProviderOutputValidationSpec(
    surface="investigation",
    schema_key="investigation_v1",
    schema_model=InvestigationOutputSchema,
    text_field="summary",
)

BUDGET_VALIDATION_SPEC = ProviderOutputValidationSpec(
    surface="budget_optimization",
    schema_key="budget_optimization_v1",
    schema_model=BudgetOutputSchema,
    text_field="summary",
)

VALIDATION_SPECS_BY_ENDPOINT: dict[str, ProviderOutputValidationSpec] = {
    "app.tasks.llm.route": ROUTE_VALIDATION_SPEC,
    "app.tasks.llm.explanation": EXPLANATION_VALIDATION_SPEC,
    "app.tasks.llm.investigation": INVESTIGATION_VALIDATION_SPEC,
    "app.tasks.llm.budget_optimization": BUDGET_VALIDATION_SPEC,
}


def validation_spec_for_endpoint(endpoint: str) -> ProviderOutputValidationSpec | None:
    return VALIDATION_SPECS_BY_ENDPOINT.get(endpoint)


def validate_provider_output_text(
    *,
    raw_output_text: str,
    validation_spec: ProviderOutputValidationSpec | None,
    stage: str,
) -> OutputValidationResult:
    if validation_spec is None:
        return OutputValidationResult(
            ok=True,
            code="success",
            stage=stage,
            normalized_output_text=str(raw_output_text or ""),
            normalized_payload=None,
        )

    normalized = _normalize_provider_output_text(raw_output_text)
    if normalized["error"] is not None:
        return OutputValidationResult(
            ok=False,
            code="normalization_failed",
            stage=stage,
            normalized_output_text="",
            normalized_payload=None,
            schema_key=validation_spec.schema_key,
            normalization_source=str(normalized.get("source") or "unknown"),
            error_detail=str(normalized["error"]),
        )

    candidate_payload: Mapping[str, Any]
    if normalized.get("source") == "plain_text":
        candidate_payload = {validation_spec.text_field: str(normalized["text"])}
    else:
        candidate_payload = normalized["payload"]

    try:
        parsed = validation_spec.schema_model.model_validate(candidate_payload)
    except ValidationError as exc:
        return OutputValidationResult(
            ok=False,
            code="schema_failed",
            stage=stage,
            normalized_output_text="",
            normalized_payload=None,
            schema_key=validation_spec.schema_key,
            normalization_source=str(normalized.get("source") or "unknown"),
            error_detail=str(exc.errors()),
        )

    payload = parsed.model_dump(mode="json")
    normalized_text = str(payload.get(validation_spec.text_field, "")).strip()
    if not normalized_text:
        return OutputValidationResult(
            ok=False,
            code="schema_failed",
            stage=stage,
            normalized_output_text="",
            normalized_payload=None,
            schema_key=validation_spec.schema_key,
            normalization_source=str(normalized.get("source") or "unknown"),
            error_detail=f"missing_or_empty_text_field:{validation_spec.text_field}",
        )

    return OutputValidationResult(
        ok=True,
        code="success",
        stage=stage,
        normalized_output_text=normalized_text,
        normalized_payload=payload,
        schema_key=validation_spec.schema_key,
        normalization_source=str(normalized.get("source") or "unknown"),
    )


def _normalize_provider_output_text(raw_output_text: str) -> dict[str, Any]:
    text = str(raw_output_text or "").strip()
    if not text:
        return {"payload": None, "source": "empty", "error": "empty_output_text"}

    fenced = _strip_markdown_fence(text)
    if fenced is not None:
        parsed = _parse_json_object(fenced)
        if parsed["error"] is not None:
            return {
                "payload": None,
                "source": "markdown_fence_json",
                "error": parsed["error"],
            }
        return {"payload": parsed["payload"], "source": "markdown_fence_json", "error": None}

    if text.startswith("{") or text.startswith("["):
        parsed = _parse_json_object(text)
        if parsed["error"] is not None:
            return {"payload": None, "source": "raw_json", "error": parsed["error"]}
        return {"payload": parsed["payload"], "source": "raw_json", "error": None}

    extracted = _extract_first_json_object(text)
    if extracted is not None:
        parsed = _parse_json_object(extracted)
        if parsed["error"] is not None:
            return {"payload": None, "source": "embedded_json", "error": parsed["error"]}
        return {"payload": parsed["payload"], "source": "embedded_json", "error": None}

    return {"payload": None, "text": text, "source": "plain_text", "error": None}


def _strip_markdown_fence(text: str) -> str | None:
    if not text.startswith("```"):
        return None
    lines = text.splitlines()
    if len(lines) < 2:
        return None
    first = lines[0].strip().lower()
    if not first.startswith("```"):
        return None
    if lines[-1].strip() != "```":
        return None
    return "\n".join(lines[1:-1]).strip()


def _parse_json_object(candidate: str) -> dict[str, Any]:
    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        return {"payload": None, "error": f"json_decode_error:{exc.msg}"}
    if not isinstance(parsed, Mapping):
        return {"payload": None, "error": f"json_root_not_object:{type(parsed).__name__}"}
    return {"payload": dict(parsed), "error": None}


def _extract_first_json_object(text: str) -> str | None:
    start = text.find("{")
    if start < 0:
        return None
    in_string = False
    escape = False
    depth = 0
    for idx in range(start, len(text)):
        ch = text[idx]
        if escape:
            escape = False
            continue
        if ch == "\\":
            escape = True
            continue
        if ch == '"':
            in_string = not in_string
            continue
        if in_string:
            continue
        if ch == "{":
            depth += 1
            continue
        if ch == "}":
            depth -= 1
            if depth == 0:
                return text[start : idx + 1]
    return None
