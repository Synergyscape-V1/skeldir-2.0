#!/usr/bin/env python3
"""Validate B2.6-P2 canonical scope, rail, and normalization authority."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import importlib.util
import inspect
import json
import sys
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any
from uuid import UUID

import yaml  # type: ignore[import-untyped]


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(BACKEND))
sys.path.insert(0, str(REPO_ROOT))

SCOPE_POLICY_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
SCOPE_MODULE = BACKEND / "app/finance_reconciliation/scope_authority.py"
COVERAGE_MODULE = BACKEND / "app/finance_reconciliation/coverage_authority.py"
SINK_MODULE = BACKEND / "app/finance_reconciliation/canonical_sink.py"

CANONICAL_PROVIDERS = frozenset({"paypal", "shopify", "stripe", "woocommerce"})

# Files allowed to name >=2 canonical providers AND define normalization
# shapes: the P2 canonical module itself, the sovereign B2.3 universe owner,
# and the P1-quarantined legacy/compat surfaces (non-authoritative by fence).
CENSUS_ALLOWLIST = frozenset(
    {
        "backend/app/finance_reconciliation/scope_authority.py",
        "backend/app/revenue_verification/verification_coverage.py",
        "backend/app/finance_reconciliation/coverage_authority.py",
        "backend/app/finance_reconciliation/semantic_contract.py",
        "backend/app/finance_reconciliation/external_semantics.py",
        "backend/app/finance_reconciliation/authoritative_fields.py",
        "backend/app/finance_reconciliation/canonical_sink.py",
        "backend/app/api/reconciliation.py",
        "backend/app/services/revenue_reconciliation.py",
        "backend/app/api/export.py",
        "backend/app/ingestion/channel_normalization.py",
    }
)
QUARANTINED_NON_AUTHORITATIVE = frozenset(
    {
        "backend/app/api/reconciliation.py",
        "backend/app/services/revenue_reconciliation.py",
        "backend/app/api/export.py",
        "backend/app/ingestion/channel_normalization.py",
    }
)

FORBIDDEN_IMPORT_PREFIXES = (
    "app.services.revenue_reconciliation",
    "app.api.reconciliation",
    "app.api.export",
    "app.llm",
    "app.bayesian",
    "app.b24",
    "app.simulation",
    "app.explanation",
    "celery",
    "kombu",
    "httpx",
    "requests",
    "aiohttp",
)
FORBIDDEN_TEXT_TOKENS = (
    "clock_timestamp",
    "statement_timestamp",
    "transaction_timestamp",
    "current_timestamp",
    "set_config",
    "current_setting",
    "bypassrls",
    "security definer",
)
# Uppercase SQL idioms only: prose never carries these, sovereign SQL does.
# scope_authority.py must contain none (no persisted P2 predicate exists).
FORBIDDEN_SQL_IDIOMS = ("SELECT ", "INSERT ", "UPDATE ", "DELETE ", "COALESCE", "CASE WHEN")


def _module_ast_sha256(path: Path) -> str:
    source = path.read_text(encoding="utf-8")
    return hashlib.sha256(
        ast.dump(ast.parse(source), include_attributes=False).encode("utf-8")
    ).hexdigest()


def _imports(tree: ast.AST) -> list[str]:
    out: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            out.extend(a.name for a in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            out.append(node.module)
    return out


def _check_contract(violations: list[str], details: dict[str, Any]) -> dict[str, Any]:
    document = yaml.safe_load(SCOPE_POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    if document.get("scope_policy_version") != "b2.6-p2-scope-policy-v1":
        violations.append("p2_scope_policy_version_drift")
    if set(document.get("canonical_providers", [])) != set(CANONICAL_PROVIDERS):
        violations.append("p2_canonical_provider_universe_drift")
    if set(document.get("canonical_rails", [])) != set(CANONICAL_PROVIDERS):
        violations.append("p2_canonical_rail_universe_drift")
    if set(document.get("dispositions", [])) != {
        "SUPPORTED_AND_IN_SCOPE",
        "SUPPORTED_BUT_UNRESOLVED",
        "EXPLICITLY_EXCLUDED",
        "INVALID_OR_REFUSED",
    }:
        violations.append("p2_disposition_vocabulary_drift")
    details["scope_policy_version"] = document.get("scope_policy_version")
    details["scope_policy_source_sha256"] = hashlib.sha256(
        SCOPE_POLICY_PATH.read_bytes()
    ).hexdigest()
    pinned = document.get("module_ast_sha256")
    live = _module_ast_sha256(SCOPE_MODULE)
    details["scope_module_ast_sha256"] = live
    details["scope_module_ast_pinned"] = pinned
    if not isinstance(pinned, str) or len(pinned) != 64:
        violations.append("p2_scope_module_ast_pin_missing")
    elif pinned != live:
        violations.append("p2_scope_module_ast_drift")
    return document


def _check_sovereign_correspondence(
    violations: list[str], details: dict[str, Any]
) -> None:
    leaf = BACKEND / "app/revenue_verification/verification_coverage.py"
    name = "b26_p2_validator_sovereign_leaf"
    spec = importlib.util.spec_from_file_location(name, leaf)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[name] = module
    spec.loader.exec_module(module)
    providers = set(module.SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS)
    currencies = set(module.SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES)
    details["sovereign_providers"] = sorted(providers)
    details["sovereign_currencies"] = sorted(currencies)
    if providers != set(CANONICAL_PROVIDERS):
        violations.append("p2_sovereign_provider_universe_mismatch")
    if currencies != {"USD"}:
        violations.append("p2_sovereign_currency_universe_mismatch")


def _check_live_module_law(violations: list[str], details: dict[str, Any]) -> None:
    import app.finance_reconciliation.scope_authority as sa

    if sa.B26_P2_SCOPE_POLICY_VERSION != "b2.6-p2-scope-policy-v1":
        violations.append("p2_live_policy_version_drift")
    if sa.GOVERNED_P2_DISPOSITIONS != frozenset(
        {
            "SUPPORTED_AND_IN_SCOPE",
            "SUPPORTED_BUT_UNRESOLVED",
            "EXPLICITLY_EXCLUDED",
            "INVALID_OR_REFUSED",
        }
    ):
        violations.append("p2_live_disposition_drift")
    params = set(inspect.signature(sa.classify_candidate).parameters)
    for forbidden in ("amount", "money", "cents", "minor", "percent", "price"):
        if forbidden in params or forbidden in {p.lower() for p in params}:
            violations.append(f"p2_money_path_in_classifier:{forbidden}")
    fields = set(sa.CanonicalScopeClassification.__dataclass_fields__)
    for forbidden in ("amount", "money", "cents", "minor", "percent"):
        if any(forbidden in name for name in fields):
            violations.append(f"p2_money_field_in_classification:{forbidden}")
    for required in (
        "tenant_id",
        "provider",
        "rail",
        "currency_code",
        "window_start",
        "window_end",
        "scope_policy_version",
        "disposition",
        "reason",
    ):
        if required not in fields:
            violations.append(f"p2_scope_identity_incomplete:{required}")
    details["classifier_params"] = sorted(params)
    details["classification_fields"] = sorted(fields)


def _check_import_fence(violations: list[str], details: dict[str, Any]) -> None:
    tree = ast.parse(SCOPE_MODULE.read_text(encoding="utf-8"))
    imported = _imports(tree)
    details["scope_module_imports"] = sorted(set(imported))
    for name in imported:
        if any(name == p or name.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES):
            violations.append(f"p2_false_authority_import:{name}")
    # No finance_reconciliation module may import the ingestion alias source.
    for path in sorted((BACKEND / "app/finance_reconciliation").rglob("*.py")):
        sub = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imports(sub):
            if name.startswith("app.ingestion.channel_normalization"):
                violations.append(
                    f"p2_second_alias_source_import:{path.name}:{name}"
                )


def _check_text_purity(violations: list[str], details: dict[str, Any]) -> None:
    source = SCOPE_MODULE.read_text(encoding="utf-8")
    lowered = source.lower()
    for token in FORBIDDEN_TEXT_TOKENS:
        if token in lowered:
            violations.append(f"p2_impure_authority_token:{token}")
    for idiom in FORBIDDEN_SQL_IDIOMS:
        if idiom in source:
            violations.append(f"p2_persisted_predicate_token:{idiom.strip()}")
    for token in ("datetime.now", "time.time", "random.", "uuid4", "hash("):
        if token in lowered:
            violations.append(f"p2_nondeterministic_token:{token}")
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            violations.append("p2_authoritative_float_literal")
            break


def _check_sibling_census(violations: list[str], details: dict[str, Any]) -> None:
    """Effect-based second-authority census.

    A provider-aware normalizer outside the B2.6 truth path cannot change
    P2 meaning (P2 never calls it): sovereign B2.3, ingress, and connection
    substrates are layer-separated and recorded, not violations. A second
    normalizer is load-bearing only when it lives on the B2.6 surface
    (finance_reconciliation / reconcil / b26 path) or reaches into
    ``app.finance_reconciliation`` -- i.e. it can actually determine B2.6
    truth-path meaning. Alias-table shapes (dicts binding canonical names)
    and SQL CASE shapes are covered without relying on function-name tokens.
    """
    second_authorities: list[str] = []
    layered: list[str] = []
    for path in sorted((BACKEND / "app").rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source)
        except (OSError, SyntaxError):
            continue
        lowered = source.lower()
        names = sum(1 for p in CANONICAL_PROVIDERS if p in lowered)
        if names < 2:
            continue
        defines_normalize = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and "normaliz" in n.name.lower()
            for n in ast.walk(tree)
        )
        defines_rail_scope = any(
            isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef))
            and any(k in n.name.lower() for k in ("rail", "scope", "alias"))
            for n in ast.walk(tree)
        )
        defines_alias_table = any(
            isinstance(n, ast.Dict)
            and sum(
                1
                for k in n.keys
                if isinstance(k, ast.Constant)
                and isinstance(k.value, str)
                and k.value.lower() in CANONICAL_PROVIDERS
            )
            >= 2
            for n in ast.walk(tree)
        )
        defines_sql_case = "case when" in lowered and any(
            p in lowered for p in CANONICAL_PROVIDERS
        )
        if not (
            defines_normalize
            or defines_rail_scope
            or defines_alias_table
            or defines_sql_case
        ):
            continue
        on_b26_surface = (
            "finance_reconciliation" in rel or "reconcil" in rel or "/b26" in rel
        )
        reaches_b26 = "app.finance_reconciliation" in source
        if (on_b26_surface or reaches_b26) and rel not in CENSUS_ALLOWLIST:
            second_authorities.append(rel)
            violations.append(f"p2_second_normalization_authority:{rel}")
        else:
            layered.append(rel)
    details["second_authority_candidates"] = second_authorities
    details["layer_separated_surfaces"] = sorted(set(layered))
    details["census_allowlist_size"] = len(CENSUS_ALLOWLIST)


def _check_execution_vectors(
    violations: list[str], details: dict[str, Any]
) -> None:
    import app.finance_reconciliation.scope_authority as sa

    ws = datetime(2026, 1, 1, tzinfo=timezone.utc)
    we = datetime(2026, 2, 1, tzinfo=timezone.utc)
    occ = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    tenant = UUID("11111111-2222-3333-4444-555555555555")
    ver = sa.B26_P2_SCOPE_POLICY_VERSION

    def classify(**over: Any) -> Any:
        base: dict[str, Any] = {
            "tenant_id": tenant,
            "provider_raw": "stripe",
            "currency_raw": "USD",
            "event_time": occ,
            "window_start": ws,
            "window_end": we,
            "scope_policy_version": ver,
            "source_reference": "ord-1",
        }
        base.update(over)
        return sa.classify_candidate(**base)

    checks: list[str] = []
    if classify().disposition != "SUPPORTED_AND_IN_SCOPE":
        violations.append("p2_vector_lawful_not_in_scope")
    checks.append("lawful")
    if classify(provider_raw="SQUARE").disposition != "EXPLICITLY_EXCLUDED":
        violations.append("p2_vector_unsupported_rail_not_excluded")
    checks.append("unsupported-rail")
    if classify(currency_raw="EUR").reason != "unsupported_currency_excluded":
        violations.append("p2_vector_wrong_currency_not_excluded")
    checks.append("currency")
    if classify(event_time=we).reason != "outside_governed_window_excluded":
        violations.append("p2_vector_window_end_not_exclusive")
    checks.append("window-end")
    if classify(event_time=ws).disposition != "SUPPORTED_AND_IN_SCOPE":
        violations.append("p2_vector_window_start_not_inclusive")
    checks.append("window-start")
    if classify(event_time=we - timedelta(microseconds=1)).disposition != (
        "SUPPORTED_AND_IN_SCOPE"
    ):
        violations.append("p2_vector_window_epsilon_not_in_scope")
    checks.append("window-epsilon")
    if classify(source_reference=None).disposition != "SUPPORTED_BUT_UNRESOLVED":
        violations.append("p2_vector_blank_reference_not_unresolved")
    checks.append("unresolved")
    try:
        classify(tenant_id="bad")
        violations.append("p2_vector_bad_tenant_not_refused")
    except sa.ScopeAuthorityError:
        checks.append("tenant")
    try:
        classify(scope_policy_version="bad")
        violations.append("p2_vector_bad_policy_not_refused")
    except sa.ScopeAuthorityError:
        checks.append("policy")
    if sa.normalize_provider_set(None) != ("paypal", "shopify", "stripe", "woocommerce"):
        violations.append("p2_vector_provider_universe_not_canonical")
    checks.append("universe")
    from app.finance_reconciliation.coverage_authority import (
        independent_coverage_percent,
    )

    if independent_coverage_percent(76000, 80000) != (Decimal("95.00"), False):
        violations.append("p2_vector_coverage_math_drift")
    checks.append("coverage-95")
    details["execution_vectors"] = checks


def _check_delegation_and_wiring(
    violations: list[str], details: dict[str, Any]
) -> None:
    import app.finance_reconciliation.coverage_authority as ca
    import app.finance_reconciliation.scope_authority as sa

    if ca._normalize_platforms(None) != sa.normalize_provider_set(None):
        violations.append("p2_delegation_provider_set_diverged")
    try:
        ca._normalize_platforms(["square"])
        violations.append("p2_delegation_unsupported_not_refused")
    except ca.CanonicalCoverageAuthorityError:
        pass
    sink_source = SINK_MODULE.read_text(encoding="utf-8")
    if "_p2_scope.assert_aggregate_scope_supported(" not in sink_source:
        violations.append("p2_live_wiring_absent_from_executor")
    if "governed_sink_p2_scope_incoherent" not in sink_source:
        violations.append("p2_live_wiring_fail_closed_absent")
    details["delegation_checked"] = True


def _check_container_file_coverage(
    violations: list[str], details: dict[str, Any]
) -> None:
    dockerfile = (REPO_ROOT / "backend/Dockerfile").read_text(encoding="utf-8")
    if "contracts/reconciliation" not in dockerfile:
        violations.append("p2_scope_policy_not_in_production_image")
    if not SCOPE_POLICY_PATH.is_file():
        violations.append("p2_scope_policy_missing")
    details["dockerfile_covers_contracts"] = "contracts/reconciliation" in dockerfile


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    details: dict[str, Any] = {}
    try:
        _check_contract(violations, details)
        _check_sovereign_correspondence(violations, details)
        _check_live_module_law(violations, details)
        _check_import_fence(violations, details)
        _check_text_purity(violations, details)
        _check_sibling_census(violations, details)
        _check_execution_vectors(violations, details)
        _check_delegation_and_wiring(violations, details)
        _check_container_file_coverage(violations, details)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"p2_validator_crash:{exc}")
    details["violations"] = sorted(violations)
    if args.evidence_dir is not None and not violations:
        from scripts.ci.b26_p2_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_dir / "normalization-authority.json",
            gate_id="B26-P2-G2-NORMALIZATION-AUTHORITY",
            producer="b26-p2-static-authority",
            scenario_id="scope-authority-pristine",
            falsifier_id="p2-second-alias-dict-through-live-wiring-removal",
            details=details,
        )
    if violations:
        print("B26_P2_AUTHORITY_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_AUTHORITY_PASS")
    print(json.dumps(details, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
