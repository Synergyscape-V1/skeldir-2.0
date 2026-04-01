"""Generic output validation contracts and normalization for provider boundary."""

from __future__ import annotations

import json
import re
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
    numeric_tolerance_ratio: float | None = None
    numeric_mismatch_count: int = 0


@dataclass(frozen=True, slots=True)
class NumericAuthorityBindingSpec:
    claim_path: str
    truth_path: str
    tolerance_ratio: float


@dataclass(frozen=True, slots=True)
class NumericAuthorityPolicySpec:
    active: bool
    default_tolerance_ratio: float
    bindings: tuple[NumericAuthorityBindingSpec, ...]
    configuration_errors: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class NumericAuthorityValidationResult:
    ok: bool
    active: bool
    tolerance_ratio: float
    mismatch_count: int
    error_detail: str | None = None


NUMERIC_AUTHORITY_DEFAULT_TOLERANCE_RATIO = 0.05
NUMERIC_AUTHORITY_POLICY_ID = "b1.6-p3-numeric-authority-v1"


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
    validation_context: Mapping[str, Any] | None = None,
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

    numeric_validation = _validate_numeric_authority(
        normalized_payload=payload,
        validation_context=validation_context,
    )
    if not numeric_validation.ok:
        return OutputValidationResult(
            ok=False,
            code="numeric_mismatch",
            stage=stage,
            normalized_output_text="",
            normalized_payload=None,
            schema_key=validation_spec.schema_key,
            normalization_source=str(normalized.get("source") or "unknown"),
            error_detail=str(numeric_validation.error_detail or "numeric_mismatch"),
            numeric_tolerance_ratio=float(numeric_validation.tolerance_ratio),
            numeric_mismatch_count=int(numeric_validation.mismatch_count),
        )

    return OutputValidationResult(
        ok=True,
        code="success",
        stage=stage,
        normalized_output_text=normalized_text,
        normalized_payload=payload,
        schema_key=validation_spec.schema_key,
        normalization_source=str(normalized.get("source") or "unknown"),
        numeric_tolerance_ratio=(
            float(numeric_validation.tolerance_ratio)
            if numeric_validation.active
            else None
        ),
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


def _validate_numeric_authority(
    *,
    normalized_payload: Mapping[str, Any],
    validation_context: Mapping[str, Any] | None,
) -> NumericAuthorityValidationResult:
    context = validation_context if isinstance(validation_context, Mapping) else {}
    policy = _numeric_authority_policy(context)
    if not policy.active:
        return NumericAuthorityValidationResult(
            ok=True,
            active=False,
            tolerance_ratio=policy.default_tolerance_ratio,
            mismatch_count=0,
            error_detail=None,
        )

    policy_failures: list[str] = []
    if policy.configuration_errors:
        for error in policy.configuration_errors:
            policy_failures.append(f"type=binding_config_error,reason={error}")
        return NumericAuthorityValidationResult(
            ok=False,
            active=True,
            tolerance_ratio=policy.default_tolerance_ratio,
            mismatch_count=len(policy_failures),
            error_detail=f"numeric_authority_policy={NUMERIC_AUTHORITY_POLICY_ID};"
            + ";".join(policy_failures),
        )

    deterministic_truth = context.get("deterministic_truth")
    if not isinstance(deterministic_truth, Mapping):
        return NumericAuthorityValidationResult(
            ok=False,
            active=True,
            tolerance_ratio=policy.default_tolerance_ratio,
            mismatch_count=1,
            error_detail=(
                f"numeric_authority_policy={NUMERIC_AUTHORITY_POLICY_ID};"
                "type=binding_resolution_error,reason=deterministic_truth_missing_or_invalid"
            ),
        )
    truth_mapping = deterministic_truth

    mismatches: list[str] = []
    for binding in policy.bindings:
        expected, truth_status = _extract_numeric_from_mapping_with_status(
            truth_mapping,
            binding.truth_path,
        )
        if expected is None:
            mismatches.append(
                "type=binding_resolution_error,claim_path="
                + binding.claim_path
                + ",truth_path="
                + binding.truth_path
                + ",reason=truth_"
                + truth_status
            )
            continue

        observed, claim_status = _extract_numeric_claim_with_status(
            normalized_payload=normalized_payload,
            claim_path=binding.claim_path,
        )
        if observed is None:
            mismatches.append(
                "type=binding_resolution_error,claim_path="
                + binding.claim_path
                + ",truth_path="
                + binding.truth_path
                + ",reason=claim_"
                + claim_status
            )
            continue

        if _numeric_within_tolerance(
            observed=observed,
            expected=expected,
            tolerance_ratio=binding.tolerance_ratio,
        ):
            continue

        delta = _relative_delta(observed=observed, expected=expected)
        mismatches.append(
            "type=value_mismatch,claim_path="
            + binding.claim_path
            + ",truth_path="
            + binding.truth_path
            + ",expected="
            + _format_numeric(expected)
            + ",observed="
            + _format_numeric(observed)
            + ",tolerance_ratio="
            + _format_numeric(binding.tolerance_ratio)
            + ",delta_ratio="
            + _format_numeric(delta)
        )

    if mismatches:
        return NumericAuthorityValidationResult(
            ok=False,
            active=True,
            tolerance_ratio=policy.default_tolerance_ratio,
            mismatch_count=len(mismatches),
            error_detail=f"numeric_authority_policy={NUMERIC_AUTHORITY_POLICY_ID};"
            + ";".join(mismatches),
        )

    return NumericAuthorityValidationResult(
        ok=True,
        active=True,
        tolerance_ratio=policy.default_tolerance_ratio,
        mismatch_count=0,
        error_detail=None,
    )


def _numeric_authority_policy(context: Mapping[str, Any]) -> NumericAuthorityPolicySpec:
    default_tolerance = _coerce_tolerance_ratio(
        context.get("numeric_tolerance_ratio"),
        default=NUMERIC_AUTHORITY_DEFAULT_TOLERANCE_RATIO,
    )
    bindings: list[NumericAuthorityBindingSpec] = []
    configuration_errors: list[str] = []

    raw_bindings = context.get("numeric_claim_bindings")
    if isinstance(raw_bindings, list):
        for idx, entry in enumerate(raw_bindings):
            if not isinstance(entry, Mapping):
                configuration_errors.append(f"binding_{idx}_not_mapping")
                continue
            claim_path = entry.get("claim_path")
            truth_path = entry.get("truth_path")
            if not isinstance(claim_path, str) or not claim_path.strip():
                configuration_errors.append(f"binding_{idx}_claim_path_invalid")
                continue
            if not isinstance(truth_path, str) or not truth_path.strip():
                configuration_errors.append(f"binding_{idx}_truth_path_invalid")
                continue
            tolerance_ratio = _coerce_tolerance_ratio(
                entry.get("tolerance_ratio"),
                default=default_tolerance,
            )
            bindings.append(
                NumericAuthorityBindingSpec(
                    claim_path=claim_path.strip(),
                    truth_path=truth_path.strip(),
                    tolerance_ratio=tolerance_ratio,
                )
            )

    if not bindings:
        raw_paths = context.get("numeric_claim_paths")
        if isinstance(raw_paths, list):
            for idx, path in enumerate(raw_paths):
                if not isinstance(path, str) or not path.strip():
                    configuration_errors.append(f"path_{idx}_claim_path_invalid")
                    continue
                normalized_path = path.strip()
                bindings.append(
                    NumericAuthorityBindingSpec(
                        claim_path=normalized_path,
                        truth_path=normalized_path,
                        tolerance_ratio=default_tolerance,
                    )
                )

    is_active = bool(bindings) or bool(configuration_errors)
    return NumericAuthorityPolicySpec(
        active=is_active,
        default_tolerance_ratio=default_tolerance,
        bindings=tuple(bindings),
        configuration_errors=tuple(configuration_errors),
    )


def _extract_numeric_claim(
    *,
    normalized_payload: Mapping[str, Any],
    claim_path: str,
) -> float | None:
    direct = _extract_numeric_from_mapping(normalized_payload, claim_path)
    if direct is not None:
        return direct
    first_key, _, label = claim_path.partition(".")
    candidate_text = normalized_payload.get(first_key)
    if not isinstance(candidate_text, str):
        return None
    if not label:
        return _extract_first_number(candidate_text)
    return _extract_labeled_number(candidate_text, label)


def _extract_numeric_from_mapping(payload: Mapping[str, Any], path: str) -> float | None:
    current: Any = payload
    for segment in path.split("."):
        if not segment:
            return None
        if not isinstance(current, Mapping) or segment not in current:
            return None
        current = current[segment]
    return _coerce_numeric(current)


def _extract_numeric_from_mapping_with_status(
    payload: Mapping[str, Any], path: str
) -> tuple[float | None, str]:
    current: Any = payload
    for segment in path.split("."):
        if not segment:
            return None, "path_invalid"
        if not isinstance(current, Mapping):
            return None, "path_missing"
        if segment not in current:
            return None, "path_missing"
        current = current[segment]
    coerced = _coerce_numeric(current)
    if coerced is None:
        return None, "value_not_numeric"
    return coerced, "ok"


def _extract_numeric_claim_with_status(
    *,
    normalized_payload: Mapping[str, Any],
    claim_path: str,
) -> tuple[float | None, str]:
    direct, direct_status = _extract_numeric_from_mapping_with_status(
        normalized_payload, claim_path
    )
    if direct is not None:
        return direct, "ok"
    first_key, _, label = claim_path.partition(".")
    candidate_text = normalized_payload.get(first_key)
    if not isinstance(candidate_text, str):
        return None, direct_status
    if not label:
        value = _extract_first_number(candidate_text)
        return (value, "ok") if value is not None else (None, "text_number_missing")
    value = _extract_labeled_number(candidate_text, label)
    return (value, "ok") if value is not None else (None, "labeled_text_number_missing")


def _extract_labeled_number(text: str, label: str) -> float | None:
    normalized = re.escape(label.strip()).replace("\\_", r"[_\s-]*")
    pattern = re.compile(
        rf"(?i)\b{normalized}\b[^0-9+\-]*([-+]?\d[\d,]*(?:\.\d+)?)"
    )
    match = pattern.search(text)
    if not match:
        return None
    return _coerce_numeric(match.group(1))


def _extract_first_number(text: str) -> float | None:
    match = re.search(r"([-+]?\d[\d,]*(?:\.\d+)?)", text)
    if not match:
        return None
    return _coerce_numeric(match.group(1))


def _coerce_numeric(value: Any) -> float | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        candidate = value.strip().replace(",", "")
        if not candidate:
            return None
        try:
            return float(candidate)
        except ValueError:
            return None
    return None


def _numeric_within_tolerance(
    *,
    observed: float,
    expected: float,
    tolerance_ratio: float,
) -> bool:
    delta = abs(observed - expected)
    if expected == 0:
        return delta <= tolerance_ratio
    return (delta / abs(expected)) <= tolerance_ratio


def _relative_delta(*, observed: float, expected: float) -> float:
    delta = abs(observed - expected)
    if expected == 0:
        return delta
    return delta / abs(expected)


def _coerce_tolerance_ratio(value: Any, *, default: float) -> float:
    numeric = _coerce_numeric(value)
    if numeric is None:
        return default
    return max(0.0, min(1.0, numeric))


def _format_numeric(value: float) -> str:
    return f"{value:.8f}".rstrip("0").rstrip(".")
