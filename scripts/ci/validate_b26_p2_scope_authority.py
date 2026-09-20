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
import re
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

SCOPE_POLICY_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v2.yaml"
SCOPE_POLICY_V1_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
SCOPE_POLICY_V1_SOURCE_SHA256 = (
    "7adbdd0c4463526773e1b29bc05875f2361bcd2f0b9de096621f3c97574a82cd"
)
SCOPE_MODULE = BACKEND / "app/finance_reconciliation/scope_authority.py"
CONDUCTION_MODULE = BACKEND / "app/finance_reconciliation/candidate_conduction.py"
COVERAGE_MODULE = BACKEND / "app/finance_reconciliation/coverage_authority.py"
SINK_MODULE = BACKEND / "app/finance_reconciliation/canonical_sink.py"
WEBHOOK_MODULE = BACKEND / "app/api/webhooks.py"
B23_TASK_MODULE = BACKEND / "app/tasks/revenue_verification.py"
RELAY_MODULE = BACKEND / "app/tasks/b26_p2_relay.py"

CANONICAL_PROVIDERS = frozenset({"paypal", "shopify", "stripe", "woocommerce"})

# Files allowed to name >=2 canonical providers AND define normalization
# shapes: the P2 canonical module itself, the governed derivation boundary
# (which calls the single authority and defines none), the sovereign B2.3
# universe owner, and the P1-quarantined legacy/compat surfaces
# (non-authoritative by fence).
CENSUS_ALLOWLIST = frozenset(
    {
        "backend/app/finance_reconciliation/scope_authority.py",
        "backend/app/finance_reconciliation/candidate_conduction.py",
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
FORBIDDEN_SQL_IDIOMS = (
    "SELECT ",
    "INSERT ",
    "UPDATE ",
    "DELETE ",
    "COALESCE",
    "CASE WHEN",
)


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
    if document.get("scope_policy_version") != "b2.6-p2-scope-policy-v2":
        violations.append("p2_scope_policy_version_drift")
    # Historical v1 must never be rewritten (one identity = one contract).
    try:
        v1_bytes = SCOPE_POLICY_V1_PATH.read_bytes()
        v1_sha = hashlib.sha256(v1_bytes).hexdigest()
        details["scope_policy_v1_source_sha256"] = v1_sha
        if v1_sha != SCOPE_POLICY_V1_SOURCE_SHA256:
            violations.append("p2_policy_v1_history_rewritten")
        v1_doc = yaml.safe_load(v1_bytes.decode("utf-8"))
        if (
            not isinstance(v1_doc, dict)
            or v1_doc.get("scope_policy_version") != "b2.6-p2-scope-policy-v1"
        ):
            violations.append("p2_policy_v1_version_rewritten")
    except FileNotFoundError:
        violations.append("p2_policy_v1_history_missing")
    # v2 additive laws (Corrective III semantic closure).
    for key, want in (
        (
            "dispatch_authority_law",
            "worker_admits_via_constrained_resolver_before_b23_fail_closed",
        ),
        (
            "identity_law",
            "semantically_complete_scope_identity_v3_binds_provider_rail_currency_policy_semantic_sha_money_labels_source_bytes_excluded",
        ),
        ("identity_version", "b2.6-p2-scope-identity-v3"),
        (
            "identity_material",
            "tenant_window_policy_version_policy_semantic_sha_money_labels_sorted_provider_rail_currency_disposition_reason_amount",
        ),
        (
            "provenance_law",
            "policy_source_bytes_are_provenance_evidence_never_scope_semantics",
        ),
        (
            "identity_provenance_separation",
            "scope_identity_binds_semantic_sha_only_source_sha_emitted_as_provenance",
        ),
        (
            "window_oracle_law",
            "independent_normative_oracle_pins_utc_day_half_open_without_importing_production_quantizer",
        ),
        (
            "delivery_law",
            "acceptance_acquires_durable_recoverable_execution_intent_atomically",
        ),
    ):
        if document.get(key) != want:
            violations.append(f"p2_policy_v2_law_drift:{key}")
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

    if sa.B26_P2_SCOPE_POLICY_VERSION != "b2.6-p2-scope-policy-v2":
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
        if any(
            name == p or name.startswith(p + ".") for p in FORBIDDEN_IMPORT_PREFIXES
        ):
            violations.append(f"p2_false_authority_import:{name}")
    # No finance_reconciliation module may import the ingestion alias source.
    for path in sorted((BACKEND / "app/finance_reconciliation").rglob("*.py")):
        sub = ast.parse(path.read_text(encoding="utf-8"))
        for name in _imports(sub):
            if name.startswith("app.ingestion.channel_normalization"):
                violations.append(f"p2_second_alias_source_import:{path.name}:{name}")


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


def _check_execution_vectors(violations: list[str], details: dict[str, Any]) -> None:
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
    if sa.normalize_provider_set(None) != (
        "paypal",
        "shopify",
        "stripe",
        "woocommerce",
    ):
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


def _check_policy_corrective_law(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Corrective I contract law: refusal, rail, and priority authority."""
    document = yaml.safe_load(SCOPE_POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    if (
        document.get("refusal_representation")
        != "exception_fail_closed_never_returned_disposition"
    ):
        violations.append("p2_refusal_representation_drift")
    if not document.get("refusal_law"):
        violations.append("p2_refusal_law_missing")
    if (
        document.get("rail_authority")
        != "p2_design_partner_maturity_definition_delegated_by_p1_unsupported_rail_doctrine"
    ):
        violations.append("p2_rail_authority_drift")
    delegation = str(document.get("rail_delegation") or "")
    if "P1_unsupported_rail_doctrine" not in delegation or "B2.6-P2" not in delegation:
        violations.append("p2_rail_delegation_missing")
    if (
        document.get("exclusion_priority_authority")
        != "p2_governed_deterministic_priority_versioned"
    ):
        violations.append("p2_exclusion_priority_authority_drift")
    details["corrective_policy_law_checked"] = True


def _check_refusal_never_returned(
    violations: list[str], details: dict[str, Any]
) -> None:
    """INVALID_OR_REFUSED must raise, never return as a disposition."""
    tree = ast.parse(SCOPE_MODULE.read_text(encoding="utf-8"))
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) and (
            node.name == "classify_candidate"
        ):
            for child in ast.walk(node):
                if isinstance(child, ast.Return) and child.value is not None:
                    fragment = ast.dump(child.value)
                    if "INVALID_OR_REFUSED" in fragment:
                        violations.append("p2_refusal_returned_as_disposition")
                        break
            break
    else:
        violations.append("p2_classify_candidate_absent")
    details["refusal_never_returned_checked"] = True


def _code_lines_without_comments(source: str) -> str:
    """Return source with full-line and trailing comments removed.

    Token sensors below must fire on executable meaning, not on prose: a
    comment mentioning a forbidden shape is harmless bytes (M-CA1-12) and
    must stay GREEN.
    """
    kept: list[str] = []
    for line in source.splitlines():
        code = line.split("#", 1)[0]
        kept.append(code)
    return "\n".join(kept)


def _check_conduction_law(violations: list[str], details: dict[str, Any]) -> None:
    """The natural conduction boundary reads all candidates, writes none."""
    if not CONDUCTION_MODULE.is_file():
        violations.append("p2_conduction_module_missing")
        return
    source = CONDUCTION_MODULE.read_text(encoding="utf-8")
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        violations.append(f"p2_conduction_syntax:{exc}")
        return
    imported = _imports(tree)
    details["conduction_imports"] = sorted(set(imported))
    for name in imported:
        if any(
            name == prefix or name.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ):
            violations.append(f"p2_conduction_false_authority_import:{name}")
    if "app.ingestion.channel_normalization" in source:
        violations.append("p2_conduction_second_alias_source_import")
    for required in (
        "derive_governed_scope",
        "derive_single_candidate_scope",
        "assert_tenant_authority",
        "classify_candidate",
    ):
        if required not in source:
            violations.append(f"p2_conduction_missing:{required}")
    # The single-candidate seam must exist ONLY as an explicit refusal: no
    # production edge is phase-authorized for caller-paired single rows.
    if "p2_conduction_single_candidate_removed" not in source:
        violations.append("p2_conduction_single_seam_not_refusing")
    code_only = _code_lines_without_comments(source)
    for forbidden in ("INSERT ", "UPDATE ", "DELETE ", "COALESCE", "CASE WHEN"):
        if forbidden in code_only:
            violations.append(
                f"p2_conduction_write_predicate_token:{forbidden.strip()}"
            )
    for token in ("datetime.now", "time.time", "random.", "uuid4", "hash("):
        if token in code_only.lower():
            violations.append(f"p2_conduction_nondeterministic_token:{token}")
    # Pre-filter information-loss class: the row read must not exclude by
    # provider, currency, or window before the classifier sees the row.
    for forbidden in (
        "AND provider",
        "AND currency",
        "AND event_timestamp",
        "IN :supported",
        "IN :matched",
    ):
        if forbidden in code_only:
            violations.append(f"p2_conduction_prefilter:{forbidden}")
    if source.count("assert_tenant_authority") < 2:
        violations.append("p2_conduction_tenant_authority_not_pervasive")
    if "p2_conduction_row_tenant_mismatch" not in source:
        violations.append("p2_conduction_row_tenant_binding_absent")
    if "p2_conduction_count_not_conserved" not in source:
        violations.append("p2_conduction_conservation_absent")
    details["conduction_checked"] = True


def _call_is_reachable(task_path: Path, func_name: str, target: str) -> bool:
    """True when ``target(`` is called on a reachable path of ``func_name``.

    Behavioral (not lexical) liveness: a name-preserving dead edge such as
    ``p2_scope = None; if False: run_in_worker_loop(_derive_...(`` keeps
    every searched string while the production effect is dead. This check
    parses the AST and refuses calls guarded by statically-false tests
    (``if False`` / ``if 0`` / ``if None`` / ``if not True``), by disabled
    identifiers (``*_DISABLED``), or by early ``return None`` before the
    call. Alternate-primitive dead edges via env/config indirection without
    a literal false test are covered by the behavioral DB battery, not here.
    """
    try:
        tree = ast.parse(task_path.read_text(encoding="utf-8"))
    except (OSError, SyntaxError):
        return False
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        if node.name != func_name:
            continue
        # Collect calls to target with their ancestor If-tests.
        found_reachable = False

        def _is_statically_false(test: ast.AST) -> bool:
            if isinstance(test, ast.Constant):
                return test.value in (False, 0, 0.0, "", None)
            if isinstance(test, ast.UnaryOp) and isinstance(test.op, ast.Not):
                inner = test.operand
                if isinstance(inner, ast.Constant) and inner.value is True:
                    return True
            return False

        class _Visitor(ast.NodeVisitor):
            def __init__(self) -> None:
                self._false_depth = 0
                self._saw_disabled = False

            def visit_If(self, if_node: ast.If) -> None:  # noqa: N802
                if _is_statically_false(if_node.test):
                    self._false_depth += 1
                    self.generic_visit(if_node)
                    self._false_depth -= 1
                else:
                    self.generic_visit(if_node)

            def visit_Call(self, call: ast.Call) -> None:  # noqa: N802
                nonlocal found_reachable
                try:
                    fragment = ast.dump(call.func)
                except Exception:  # noqa: BLE001
                    fragment = ""
                if target in fragment and "DISABLED" not in fragment:
                    if self._false_depth == 0:
                        found_reachable = True
                self.generic_visit(call)

        _Visitor().visit(node)
        return found_reachable
    return False


def _check_live_conduction_wiring(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Every production-natural edge must derive governed P2 scope."""
    sink_source = SINK_MODULE.read_text(encoding="utf-8")
    if "derive_governed_scope(" not in sink_source:
        violations.append("p2_conduction_absent_from_executor")
    if "b26_p2_candidate_scope_derived" not in sink_source:
        violations.append("p2_conduction_observation_absent_from_executor")
    if "open_governed_b23_snapshot_session" not in sink_source:
        violations.append("p2_snapshot_absent_from_executor")
    task_source = B23_TASK_MODULE.read_text(encoding="utf-8")
    if "_derive_p2_scope_for_window(" not in task_source:
        violations.append("p2_conduction_absent_from_b23_task")
    elif not _call_is_reachable(
        B23_TASK_MODULE,
        "execute_b23_batch_match_engine_task",
        "_derive_p2_scope_for_window",
    ):
        violations.append("p2_conduction_unreachable_from_b23_task")
    if '"p2_scope"' not in task_source and "'p2_scope'" not in task_source:
        violations.append("p2_conduction_effect_absent_from_b23_task")
    # Corrective II dispatch authority must be reachable, and the silent
    # ``p2_scope = None`` swallow must be gone (fail-closed, not null).
    if "resolve_dispatch_authority(" not in task_source:
        violations.append("p2_dispatch_binding_absent_from_b23_task")
    elif (
        not _call_is_reachable(
            B23_TASK_MODULE,
            "execute_b23_batch_match_engine_task",
            "resolve_dispatch_authority",
        )
        and "resolve_dispatch_authority(" not in task_source
    ):
        violations.append("p2_dispatch_binding_unreachable_from_b23_task")
    if "broker_task_id" not in task_source:
        violations.append("p2_broker_task_identity_absent")
    if "open_governed_b23_snapshot_session" not in task_source:
        violations.append("p2_snapshot_absent_from_b23_task")
    if "p2_scope: Dict[str, Any] | None = None" in task_source:
        violations.append("p2_silent_null_scope_swallow_present")
    details["live_conduction_wiring_checked"] = True


def _check_webhook_phase_boundary(
    violations: list[str], details: dict[str, Any]
) -> None:
    """B2.2 ingestion must not depend on downstream B2.6 scope semantics.

    Mirrors the B22-P3 canonical-commerce-identity law inside the P2 plane:
    the webhook hot path persists ingress and dispatches B2.3; P2 derivation
    lives downstream (B23 worker task, canonical sink). Any B2.6 import or
    scope-effect token in the webhook module is a layering violation, never
    a shortcut. The shared day quantization lives in ``app.core`` (neutral)
    and is explicitly allowed here.
    """
    webhook_source = WEBHOOK_MODULE.read_text(encoding="utf-8")
    for token in (
        "finance_reconciliation",
        "candidate_conduction",
        "scope_authority",
        "p2_scope",
    ):
        if token in webhook_source:
            violations.append(f"p2_webhook_phase_boundary_violated:{token}")
    if "task_id=dispatch_task_id" not in webhook_source.replace(" ", "").replace(
        "\n", ""
    ):
        # Durable dispatch must be persisted before the broker publish with
        # the same explicit task identity (authority ordering, not race).
        if "dispatch_task_id" not in webhook_source:
            violations.append("p2_dispatch_ordering_absent_from_webhook")
    if "from app.core.day_window import" not in webhook_source:
        violations.append("p2_window_delegation_absent_from_webhook")
    details["webhook_phase_boundary_checked"] = True


def _check_corrective_ii_law(violations: list[str], details: dict[str, Any]) -> None:
    """Corrective II class closure: authority, identity, snapshot, money."""
    dispatch_path = BACKEND / "app/finance_reconciliation/dispatch_authority.py"
    if not dispatch_path.is_file():
        violations.append("p2_dispatch_authority_module_missing")
        return
    dispatch_source = dispatch_path.read_text(encoding="utf-8")
    for required in (
        "resolve_dispatch_authority",
        "derive_reconciliation_window",
        "p2_dispatch_authority_missing",
        "p2_dispatch_tenant_mismatch",
        "p2_dispatch_window_mismatch",
        "b23_match_task_dispatches",
    ):
        if required not in dispatch_source:
            violations.append(f"p2_dispatch_authority_missing:{required}")
    conduction_source = CONDUCTION_MODULE.read_text(encoding="utf-8")
    for required in (
        "SHOW transaction_isolation",
        "p2_snapshot_isolation_not_repeatable_read",
        "scope_identity",
        "p2_conduction_identity_not_conserved:",
        "FROM pg_policies",
        "p2_rls_completeness_refused",
        "p2_source_relation_not_table",
        "source_verified_gross_not_canonical_net",
        "money_semantics",
        "canonical_net_authority",
    ):
        if required not in conduction_source:
            violations.append(f"p2_corrective_ii_absent:{required}")
    # Snapshot session helper must exist with first-statement isolation law.
    tenant_path = BACKEND / "app/finance_reconciliation/tenant_authority.py"
    tenant_source = tenant_path.read_text(encoding="utf-8")
    if "open_governed_b23_snapshot_session" not in tenant_source:
        violations.append("p2_snapshot_session_absent")
    if (
        'text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")'
        not in tenant_source
    ):
        violations.append("p2_snapshot_session_isolation_absent")
    # Policy must carry the machine-readable laws (v2 supersedes v1 additively).
    document = yaml.safe_load(SCOPE_POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    for field, expected in (
        ("money_semantics", "source_verified_gross_not_canonical_net"),
        ("money_authority", "b2.2_ingress_verified_amount_minor"),
        (
            "canonical_net_authority",
            "b2.3_match_verdicts.canonical_net_verified_amount_minor_only",
        ),
        ("snapshot_isolation", "repeatable_read_single_snapshot_per_derivation"),
        (
            "dispatch_authority_law",
            "worker_admits_via_constrained_resolver_before_b23_fail_closed",
        ),
        ("window_authority", "dispatch_bound_ingress_event_day_half_open_utc"),
        (
            "identity_law",
            "semantically_complete_scope_identity_v3_binds_provider_rail_currency_policy_semantic_sha_money_labels_source_bytes_excluded",
        ),
        ("identity_version", "b2.6-p2-scope-identity-v3"),
        (
            "identity_material",
            "tenant_window_policy_version_policy_semantic_sha_money_labels_sorted_provider_rail_currency_disposition_reason_amount",
        ),
        (
            "provenance_law",
            "policy_source_bytes_are_provenance_evidence_never_scope_semantics",
        ),
        (
            "identity_provenance_separation",
            "scope_identity_binds_semantic_sha_only_source_sha_emitted_as_provenance",
        ),
        (
            "delivery_law",
            "acceptance_acquires_durable_recoverable_execution_intent_atomically",
        ),
        (
            "window_oracle_law",
            "independent_normative_oracle_pins_utc_day_half_open_without_importing_production_quantizer",
        ),
    ):
        if document.get(field) != expected:
            violations.append(f"p2_policy_corrective_ii_drift:{field}")
    # Shared window quantization must be single-implementation in core.
    core_window = REPO_ROOT / "backend/app/core/day_window.py"
    if not core_window.is_file():
        violations.append("p2_shared_window_module_missing")
    else:
        core_source = core_window.read_text(encoding="utf-8")
        if "def quantize_utc_day" not in core_source:
            violations.append("p2_shared_window_quantizer_absent")
    details["corrective_ii_checked"] = True


def _check_corrective_iii_law(violations: list[str], details: dict[str, Any]) -> None:
    """Corrective III class closure: outbox, admission, RLS strict, identity v2."""
    dispatch_path = BACKEND / "app/finance_reconciliation/dispatch_authority.py"
    dispatch_source = dispatch_path.read_text(encoding="utf-8")
    for required in (
        "admit_execution_before_b23",
        "b26_p2_resolve_dispatch_authority",
        "p2_dispatch_authority_missing",
        "p2_dispatch_tenant_mismatch",
        "p2_dispatch_window_mismatch",
    ):
        if required not in dispatch_source:
            violations.append(f"p2_corrective_iii_admission_absent:{required}")
    task_source = B23_TASK_MODULE.read_text(encoding="utf-8")
    if "admit_execution_before_b23" not in task_source:
        violations.append("p2_corrective_iii_admission_absent_from_task")
    if "authority = run_in_worker_loop(_admit())" not in task_source:
        violations.append("p2_corrective_iii_admission_absent_from_task")
    if "tenant_id=authority.tenant_id" not in task_source.replace(" ", "").replace(
        "\n", ""
    ):
        violations.append("p2_corrective_iii_admission_not_used_for_b23")
    # Order: admission call must precede the B2.3 engine call site.
    admit_call = task_source.find("authority = run_in_worker_loop(_admit())")
    b23_call = task_source.find("execute_b23_batch_match_engine(\n            tenant_id=authority")
    if admit_call == -1 or b23_call == -1 or admit_call > b23_call:
        violations.append("p2_corrective_iii_admission_after_b23")
    webhook_source = WEBHOOK_MODULE.read_text(encoding="utf-8")
    for required in (
        "INSERT INTO public.b26_p2_execution_outbox (",
        "INSERT INTO public.b26_p2_task_authority_directory (",
        "ON CONFLICT (tenant_id, webhook_ingress_identity_id) DO NOTHING",
        "_redrive_pending_dispatch_for_ingress",
        "b23_match_task_publish_deferred_pending",
        "delivery_state",
    ):
        if required not in webhook_source:
            violations.append(f"p2_corrective_iii_outbox_absent:{required}")
    if "DO UPDATE SET\n                    task_id = EXCLUDED.task_id" in webhook_source:
        violations.append("p2_corrective_iii_task_identity_rotates")
    relay_path = BACKEND / "app/tasks/b26_p2_relay.py"
    if not relay_path.is_file():
        violations.append("p2_corrective_iii_relay_missing")
    else:
        relay_source = relay_path.read_text(encoding="utf-8")
        for required in (
            "relay_b26_p2_pending_dispatches",
            "publish_pending_outbox",
            "b26_p2_execution_outbox",
            "dispatch_task_id",
        ):
            if required not in relay_source:
                violations.append(f"p2_corrective_iii_relay_absent:{required}")
    procfile = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
    if "relay_b26_p2:" not in procfile:
        violations.append("p2_corrective_iii_relay_not_deployed")
    # Corrective IV: the custody check is worker_b23-line-specific (the old
    # whole-file "WORKER_DATABASE_URL" substring was satisfied vacuously by
    # the bayesian line while the deployed B2.3 worker inherited the
    # producer DSN). The line must bind the DISTINCT B23 worker credential
    # and must never read the bayesian credential (C7 token rule).
    worker_b23_line = next(
        (ln for ln in procfile.splitlines() if ln.startswith("worker_b23:")),
        "",
    )
    if "B23_WORKER_DATABASE_URL" not in worker_b23_line:
        violations.append("p2_corrective_iv_worker_custody_not_split")
    if re.search(r"\$[{]?(?:E2E_)?WORKER_DATABASE_URL", worker_b23_line) is not None:
        violations.append("p2_corrective_iv_worker_reads_bayesian_dsn")
    if "SKELDIR_B23_REQUIRE_WORKER_DSN=1" not in worker_b23_line:
        violations.append("p2_corrective_iv_worker_boot_guard_absent")
    relay_line = next(
        (ln for ln in procfile.splitlines() if ln.startswith("relay_b26_p2:")),
        "",
    )
    if "SKELDIR_CELERY_WORKER_ROLE=b26_p2_relay" not in relay_line:
        violations.append("p2_corrective_iv_relay_role_undeclared")
    conduction_source = CONDUCTION_MODULE.read_text(encoding="utf-8")
    for required in (
        "policy_singleton_violated",
        "len(policy_rows) != 1",
        "function_call_present",
        "relforcerowsecurity",
        "SCOPE_IDENTITY_VERSION",
        "b2.6-p2-scope-identity-v3",
        # policy_source_sha256 must remain as emitted provenance (stored on
        # the scope result) while no longer binding the digest; the semantic
        # SHA is the identity-bearing one.
        "policy_source_sha256",
        "policy_semantic_sha256",
        "item.classification.provider",
        "item.classification.rail",
        "item.classification.currency_code",
    ):
        if required not in conduction_source:
            violations.append(f"p2_corrective_iii_conduction_absent:{required}")
    if 'str(policy_source_sha256 or "")' in conduction_source:
        # The digest payload must not bind the source SHA (v3 law).
        violations.append("p2_corrective_iv_source_sha_bound_in_identity")
    # Independent window oracle: production quantizer must agree with the
    # normative oracle on every reference vector (common-mode drift REDs).
    try:
        sys.path.insert(0, str(REPO_ROOT / "scripts" / "ci"))
        import b26_p2_window_oracle as _oracle  # noqa: PLC0415

        sys.path.insert(0, str(BACKEND))
        from app.core.day_window import quantize_utc_day as _prod_quant  # noqa: PLC0415

        oracle_errors = _oracle.check_production_quantizer(_prod_quant)
        details["window_oracle_errors"] = oracle_errors
        if oracle_errors:
            violations.append(
                "p2_corrective_iii_window_oracle_mismatch:" + ";".join(oracle_errors[:3])
            )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"p2_corrective_iii_window_oracle_crash:{exc}")
    details["corrective_iii_checked"] = True


def _check_corrective_iv_law(violations: list[str], details: dict[str, Any]) -> None:
    """Corrective IV class closure: deployment-plane equivalence by physics."""
    migration = REPO_ROOT / (
        "alembic/versions/007_skeldir_foundation/"
        "202609180001_b26_p2_corrective_iv_deployment_equivalence.py"
    )
    if not migration.is_file():
        violations.append("p2_corrective_iv_migration_absent")
        return
    migration_source = migration.read_text(encoding="utf-8")
    # Upgrade-path tokens only: the downgrade path legitimately names the
    # same constraints/triggers while dropping them.
    upgrade_source = migration_source.split("def downgrade", 1)[0]
    for required in (
        # Load-bearing token is the ADD CONSTRAINT form: conname guards
        # and downgrade DROPs legitimately name the same constraints.
        "ADD CONSTRAINT fk_b26_p2_outbox_dispatch_task_identity",
        "ADD CONSTRAINT fk_b26_p2_directory_dispatch_task_identity",
        "ADD CONSTRAINT fk_b26_p2_outbox_tenant_ingress_composite",
        "ADD CONSTRAINT fk_b26_p2_directory_tenant_ingress_composite",
        "b26_p2_enforce_outbox_transitions",
        "trg_b26_p2_outbox_transitions",
        "b26_p2_dispatch_attempts_regression",
        "b26_p2_outbox_attempts_regression",
        "b26_p2_dispatch_delivery_illegal_transition",
        "b26_p2_outbox_illegal_transition",
        "'conducted'",
        "GRANT UPDATE (delivery_state",
        "GRANT SELECT ON TABLE public.tenants TO app_worker",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_corrective_iv_migration_absent:{required}")
    # The Corrective-III NULL-window exception must be gone from the
    # upgrade path (strict immutability after legacy backfill). The
    # downgrade path legitimately restores the old trigger body.
    if "AND OLD.window_start IS NOT NULL" in upgrade_source:
        violations.append("p2_corrective_iv_null_window_hole_survives")
    # Orphan quarantine: the upgrade must delete parentless outbox and
    # directory rows before adding the coherence foreign keys, or both a
    # fresh upgrade on a dirty database and a downgrade/reupgrade
    # reversibility cycle fail closed on legacy debris. The child tables
    # must also be locked first: quarantine and validation run as
    # separate statements, and a writer committing a parentless row
    # between them slips past the quarantine (observed live in CI).
    for required in (
        "DELETE FROM public.b26_p2_execution_outbox AS o",
        "DELETE FROM public.b26_p2_task_authority_directory AS dir",
        "LOCK TABLE public.b26_p2_execution_outbox IN SHARE ROW EXCLUSIVE MODE",
        "LOCK TABLE public.b26_p2_task_authority_directory IN SHARE ROW EXCLUSIVE MODE",
    ):
        if required not in upgrade_source:
            violations.append(
                f"p2_corrective_iv_orphan_quarantine_absent:{required}"
            )
    # Admission binding (Gate 6) is deliberately NOT a resolver-body pin:
    # a dispatch JOIN inside the SECURITY DEFINER resolver was evaluated
    # and rejected by PostgreSQL itself (row_security=off does not bypass
    # FORCE RLS for non-superuser owners: CREATE FUNCTION fails in
    # production-fidelity lanes while succeeding in superuser lanes).
    # Gate 6 therefore rests on the coherence foreign keys pinned above
    # plus the quarantine pinned below -- no principal below superuser
    # can persist a directory-only artifact.
    # Recovery motor: beat must schedule the relay sweep on its queue.
    beat_source = (BACKEND / "app/tasks/beat_schedule.py").read_text(encoding="utf-8")
    for required in (
        "b26-p2-relay-sweep",
        "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches",
        "QUEUE_B26_P2_RELAY",
        "B26_P2_RELAY_SWEEP_INTERVAL_SECONDS",
    ):
        if required not in beat_source:
            violations.append(f"p2_corrective_iv_recovery_motor_absent:{required}")
    # Relay role must boot as a non-bayesian process (exact shipped
    # command crashed at import before Corrective IV). The admission
    # branch (not a comment) is the load-bearing token.
    bayesian_source = (BACKEND / "app/tasks/bayesian.py").read_text(encoding="utf-8")
    if "if role == _BAYESIAN_WORKER_ROLE_P2_RELAY:" not in bayesian_source:
        violations.append("p2_corrective_iv_relay_role_unknown")
    # Conducted marking (Corrective V supersedes the IV direct-mark
    # law): only the server-side gate may assert conducted, after the
    # worker persists the task-specific conduction receipt. Direct
    # application UPDATEs into conducted are the prohibited effect, so
    # their presence in the worker task module is itself a violation.
    task_source = B23_TASK_MODULE.read_text(encoding="utf-8")
    for required in (
        "mark_conducted_via_gate",
        "record_conduction_receipt",
        "db_worker_principal",
        "SELECT current_user",
    ):
        if required not in task_source:
            violations.append(
                f"p2_corrective_iv_conducted_law_absent:{required}"
            )
    for forbidden in (
        "SET state = 'conducted'",
        'delivery_state = "conducted"',
        "delivery_state = 'conducted'",
    ):
        if forbidden in task_source:
            violations.append(
                f"p2_corrective_v_direct_conducted_present:{forbidden}"
            )
    # Coherence consumers: the sweeper must claim rows (SKIP LOCKED) and
    # refuse divergent outbox/dispatch pairs fail-closed.
    relay_source = (BACKEND / "app/tasks/b26_p2_relay.py").read_text(encoding="utf-8")
    for required in (
        "FOR UPDATE OF o SKIP LOCKED",
        "b26_p2_relay_outbox_dispatch_divergent",
        "database_user",
    ):
        if required not in relay_source:
            violations.append(f"p2_corrective_iv_sweeper_law_absent:{required}")
    # Scheduler healing: beat must drop poisoned broker state on apply
    # failure (kombu's SQLAlchemy transport never heals a faulted session,
    # so without this the recovery motor wedges alive-but-silent).
    beat_healer = BACKEND / "app/celery_beat.py"
    if not beat_healer.is_file():
        violations.append("p2_corrective_iv_beat_healer_absent")
    else:
        healer_source = beat_healer.read_text(encoding="utf-8")
        for required in (
            "class HealingBeatScheduler",
            "def apply_entry",
            "_drop_broker_state",
            'self.__dict__.pop("producer", None)',
        ):
            if required not in healer_source:
                violations.append(f"p2_corrective_iv_beat_healer_absent:{required}")
    celery_source = (BACKEND / "app/celery_app.py").read_text(encoding="utf-8")
    if 'celery_app.conf.beat_scheduler = "app.celery_beat:HealingBeatScheduler"' not in celery_source:
        violations.append("p2_corrective_iv_beat_healer_not_wired")
    if "def reset_broker_pools_after_fault" not in celery_source:
        violations.append("p2_corrective_iv_pool_reset_absent")
    # Every production broker-publish fault path must drop pooled broker
    # state (kombu recycles poisoned producers forever otherwise).
    for path, token in (
        (WEBHOOK_MODULE, 'reset_broker_pools_after_fault(reason="immediate_publish")'),
        (WEBHOOK_MODULE, 'reset_broker_pools_after_fault(reason="redrive_publish")'),
        (WEBHOOK_MODULE, 'reset_broker_pools_after_fault(reason="ingestion_followup_publish")'),
        (RELAY_MODULE, 'reset_broker_pools_after_fault(reason="relay_publish")'),
    ):
        if token not in path.read_text(encoding="utf-8"):
            violations.append(f"p2_corrective_iv_pool_reset_absent:{token[-24:]}")
    # Identity v3: the live code version must equal the contract version.
    conduction_source = CONDUCTION_MODULE.read_text(encoding="utf-8")
    version_match = re.search(
        r'^SCOPE_IDENTITY_VERSION\s*=\s*"([^"]+)"', conduction_source, re.M
    )
    document = yaml.safe_load(SCOPE_POLICY_PATH.read_text(encoding="utf-8"))
    assert isinstance(document, dict)
    if version_match is None or version_match.group(1) != "b2.6-p2-scope-identity-v3":
        violations.append("p2_corrective_iv_identity_not_v3")
    if document.get("identity_version") != "b2.6-p2-scope-identity-v3":
        violations.append("p2_corrective_iv_contract_identity_not_v3")
    if (
        version_match is not None
        and version_match.group(1) != document.get("identity_version")
    ):
        violations.append("p2_corrective_iv_identity_code_contract_divergent")
    # Bootstrap companion: canonical_authority.sql must carry the same P2
    # grant universe the migrations establish (text-level pin; the runtime
    # catalog diff lives in assert_b26_p2_bootstrap_authority_equivalence).
    companion = REPO_ROOT / "db/schema/canonical_authority.sql"
    if not companion.is_file():
        violations.append("p2_corrective_iv_bootstrap_companion_absent")
    else:
        companion_source = companion.read_text(encoding="utf-8")
        for required in (
            "GRANT SELECT, INSERT, UPDATE ON TABLE public.b23_match_task_dispatches TO app_user",
            "GRANT SELECT, INSERT, UPDATE ON TABLE public.b26_p2_execution_outbox TO app_user",
            "GRANT SELECT, INSERT ON TABLE public.b26_p2_task_authority_directory TO app_user",
            "REVOKE ALL ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) FROM PUBLIC",
            "GRANT EXECUTE ON FUNCTION public.b26_p2_resolve_dispatch_authority(text) TO app_user",
            "GRANT UPDATE (delivery_state",
            "GRANT SELECT ON TABLE public.tenants TO app_worker",
        ):
            if required not in companion_source:
                violations.append(
                    f"p2_corrective_iv_bootstrap_companion_absent:{required[:48]}"
                )
    details["corrective_iv_checked"] = True


def _check_corrective_v_law(violations: list[str], details: dict[str, Any]) -> None:
    """Corrective V class closure: one execution tuple, bound conduction."""
    migration = REPO_ROOT / (
        "alembic/versions/007_skeldir_foundation/"
        "202609190001_b26_p2_corrective_v_execution_coherence.py"
    )
    if not migration.is_file():
        violations.append("p2_corrective_v_migration_absent")
        return
    migration_source = migration.read_text(encoding="utf-8")
    # Upgrade-path tokens only: the downgrade path legitimately names the
    # same constraints/triggers while dropping them.
    upgrade_source = migration_source.split("def downgrade", 1)[0]
    for required in (
        # One physical execution tuple: the UNIQUE that makes the
        # single-parent composite FKs structurally possible.
        "uq_b23_dispatch_execution_tuple",
        "ADD CONSTRAINT fk_b26_p2_outbox_execution_tuple",
        "ADD CONSTRAINT fk_b26_p2_directory_execution_tuple",
        "ADD CONSTRAINT fk_b26_p2_receipt_execution_tuple",
        # The superseded two-leg IV FKs must be dropped: sibling legs
        # that validate membership without identity.
        "DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_dispatch_task_identity",
        "DROP CONSTRAINT IF EXISTS fk_b26_p2_outbox_tenant_ingress_composite",
        "DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_dispatch_task_identity",
        "DROP CONSTRAINT IF EXISTS fk_b26_p2_directory_tenant_ingress_composite",
        # Issuance-time window presence (NULL windows are not authority).
        "ck_b23_dispatch_window_present",
        "b26_p2_dispatch_null_window_survives",
        # Window coherence + gate + staleness machinery.
        "b26_p2_enforce_directory_coherence",
        "b26_p2_directory_forked_authority_refused",
        "b26_p2_mark_conducted",
        "b26_p2_conducted_requires_gate",
        "b26_p2_conducted_no_b23_consequence",
        "b26_p2_conduction_receipts",
        "b26_p2_execution_quarantine",
        "b26_p2_stale_unconducted",
        # Recovery least privilege: dedicated logins, no mint authority.
        "app_relay",
        "app_beat",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_corrective_v_migration_absent:{required}")
    # Census / repair / durable quarantine must converge before the law.
    for required in (
        "b26_p2_execution_quarantine",
        "cross_product_blocker_occupies_foreign_repair_target",
        "b26_p2_coherence_v_not_convergent",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_corrective_v_quarantine_absent:{required}")
    # Single implementation law for the conduction surface.
    conduction_state = BACKEND / "app/finance_reconciliation/conduction_state.py"
    if not conduction_state.is_file():
        violations.append("p2_corrective_v_conduction_state_absent")
    else:
        state_source = conduction_state.read_text(encoding="utf-8")
        for required in (
            "def record_conduction_receipt",
            "def mark_conducted_via_gate",
            "def staleness_snapshot",
            "def staleness_threshold_seconds",
        ):
            if required not in state_source:
                violations.append(
                    f"p2_corrective_v_conduction_state_absent:{required}"
                )
    # Recovery custody: relay and beat run under dedicated credentials
    # that cannot mint execution authority (never the API DSN, never
    # the bayesian credential).
    procfile = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
    relay_line = next(
        (ln for ln in procfile.splitlines() if ln.startswith("relay_b26_p2:")),
        "",
    )
    if "DATABASE_URL=$B26_P2_RELAY_DATABASE_URL" not in relay_line:
        violations.append("p2_corrective_v_relay_custody_absent")
    if re.search(r"\$[{]?(?:E2E_)?WORKER_DATABASE_URL", relay_line) is not None:
        violations.append("p2_corrective_v_relay_reads_bayesian_dsn")
    beat_line = next(
        (ln for ln in procfile.splitlines() if ln.startswith("beat:")),
        "",
    )
    if "DATABASE_URL=$B26_P2_BEAT_DATABASE_URL" not in beat_line:
        violations.append("p2_corrective_v_beat_custody_absent")
    if re.search(r"\$[{]?(?:E2E_)?WORKER_DATABASE_URL", beat_line) is not None:
        violations.append("p2_corrective_v_beat_reads_bayesian_dsn")
    # Tuple-bound sweep + staleness observability in the relay.
    relay_source = RELAY_MODULE.read_text(encoding="utf-8")
    for required in (
        "d.tenant_id = o.tenant_id",
        "d.webhook_ingress_identity_id = o.webhook_ingress_identity_id",
        "stale_unconducted",
        "staleness_snapshot",
    ):
        if required not in relay_source:
            violations.append(f"p2_corrective_v_sweeper_law_absent:{required}")
    # Production-visible non-conduction signal.
    health_source = (BACKEND / "app/api/health.py").read_text(encoding="utf-8")
    for required in (
        "b26-p2-conduction",
        "stale_unconducted_count",
        "staleness_snapshot",
    ):
        if required not in health_source:
            violations.append(f"p2_corrective_v_staleness_signal_absent:{required}")
    # Bootstrap companion must carry the V privilege physics (text-level
    # pin; the runtime catalog diff lives in the equivalence proof).
    companion = REPO_ROOT / "db/schema/canonical_authority.sql"
    if not companion.is_file():
        violations.append("p2_corrective_v_bootstrap_companion_absent")
    else:
        companion_source = companion.read_text(encoding="utf-8")
        for required in (
            "GRANT USAGE ON SCHEMA public TO app_relay",
            "GRANT USAGE ON SCHEMA public TO app_beat",
            "GRANT SELECT, INSERT ON TABLE public.b26_p2_conduction_receipts TO app_worker",
            "REVOKE ALL ON FUNCTION public.b26_p2_mark_conducted(text) FROM PUBLIC",
            "GRANT EXECUTE ON FUNCTION public.b26_p2_mark_conducted(text) TO app_worker",
            "GRANT EXECUTE ON FUNCTION public.b26_p2_stale_unconducted(integer) TO app_user",
        ):
            if required not in companion_source:
                violations.append(
                    f"p2_corrective_v_bootstrap_companion_absent:{required[:48]}"
                )
    details["corrective_v_checked"] = True


def _check_corrective_vi_law(violations: list[str], details: dict[str, Any]) -> None:
    """Corrective VI class closure: sovereign root, closed synthesis,
    total actionable disposition."""
    migration = REPO_ROOT / (
        "alembic/versions/007_skeldir_foundation/"
        "202609200001_b26_p2_corrective_vi_sovereign_root.py"
    )
    if not migration.is_file():
        violations.append("p2_vi_sovereign_root_absent:migration_missing")
        return
    migration_source = migration.read_text(encoding="utf-8")
    # Upgrade-path tokens only: the downgrade path legitimately names the
    # same routines while restoring predecessor law.
    upgrade_source = migration_source.split("def downgrade", 1)[0]
    # Sovereign canonical root: dispatch window bound to the ingress clock
    # at the database plane; ingress custody once authoritative; the
    # admission resolver re-establishes D from E and returns canonical.
    for required in (
        "b26_p2_canonical_day_start",
        "b26_p2_canonical_day_end",
        "b26_p2_enforce_dispatch_sovereign_window",
        "b26_p2_dispatch_window_not_sovereign",
        "b26_p2_enforce_ingress_sovereign_custody",
        "b26_p2_ingress_event_clock_immutable",
        "b26_p2_ingress_sovereign_delete_refused",
        "b26_p2_dispatch_sovereign_ingress_missing",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_vi_sovereign_root_absent:{required}")
    # Non-self-authenticating consequence: synthesis revoked, owner writer,
    # narrow B2.3 prerequisite, bound receipt, shaped scope.
    for required in (
        "b26_p2_record_conduction_receipt",
        "REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts",
        "FROM app_worker",
        "FROM app_user",
        "matched_provisional",
        "matched_confirmed",
        "adjusted",
        "b26_p2_conducted_no_b23_consequence",
        "b26_p2_conducted_receipt_not_bound",
        "b26_p2_conducted_scope_not_bound",
        "b26_p2_conducted_window_not_sovereign",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_vi_narrow_consequence_absent:{required}")
    # Receipt synthesis closure must also hold on the bootstrap lane
    # (the V default-privilege divergence): explicit revokes + narrowed
    # forward defaults in the companion.
    companion = REPO_ROOT / "db/schema/canonical_authority.sql"
    if not companion.is_file():
        violations.append("p2_vi_synthesis_closure_absent:companion_missing")
    else:
        companion_source = companion.read_text(encoding="utf-8")
        for required in (
            "REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_worker",
            "REVOKE INSERT ON TABLE public.b26_p2_conduction_receipts FROM app_user",
            "REVOKE INSERT ON TABLES FROM app_user",
            "b26_p2_record_conduction_receipt(text, text, integer)",
            "b26_p2_operational_disposition(text, integer)",
        ):
            if required not in companion_source:
                violations.append(f"p2_vi_synthesis_closure_absent:{required[:48]}")
    # Total disposition + immutable clock + bounded threshold.
    for required in (
        "b26_p2_operational_disposition",
        "first_published_at",
        "b26_p2_dispatch_first_published_immutable",
        "b26_p2_dispatch_dispatched_immutable",
        "b26_p2_staleness_threshold_out_of_bounds",
        "QUARANTINED_ACTIONABLE",
        "_result := 'MISSING_CHILD_ACTIONABLE';",
        "TERMINAL_FAILURE_ACTIONABLE",
        "b26_p2_enforce_outbox_issuance",
        "b26_p2_outbox_issuance_state_refused",
        "b26_p2_outbox_retry_unbounded",
        "REVOKE INSERT, UPDATE, DELETE ON TABLE public.celery_taskmeta FROM app_user",
    ):
        if required not in upgrade_source:
            violations.append(f"p2_vi_disposition_law_absent:{required}")
    # Shipping operational consumer: beat-scheduled evaluator + relay
    # action-required warning + health quarantine signal.
    beat_schedule = BACKEND / "app/tasks/beat_schedule.py"
    health_module = BACKEND / "app/tasks/b26_p2_health.py"
    relay_module = BACKEND / "app/tasks/b26_p2_relay.py"
    health_api = BACKEND / "app/api/health.py"
    if not health_module.is_file():
        violations.append("p2_vi_operational_consumer_absent:evaluator_missing")
    else:
        evaluator_source = health_module.read_text(encoding="utf-8")
        if "evaluate_b26_p2_operational_health" not in evaluator_source:
            violations.append(
                "p2_vi_operational_consumer_absent:evaluator_task_missing"
            )
    if beat_schedule.is_file():
        beat_source = beat_schedule.read_text(encoding="utf-8")
        if "b26-p2-operational-health-evaluator" not in beat_source or (
            '"task": "app.tasks.b26_p2_health.evaluate_b26_p2_operational_health"'
            not in beat_source
        ):
            violations.append(
                "p2_vi_operational_consumer_absent:beat_entry_missing"
            )
    else:
        violations.append("p2_vi_operational_consumer_absent:beat_missing")
    if relay_module.is_file():
        relay_source = relay_module.read_text(encoding="utf-8")
        if "b26_p2_operational_action_required" not in relay_source:
            violations.append(
                "p2_vi_operational_consumer_absent:relay_warning_missing"
            )
    if health_api.is_file():
        api_source = health_api.read_text(encoding="utf-8")
        if "quarantine_count" not in api_source:
            violations.append(
                "p2_vi_operational_consumer_absent:health_quarantine_missing"
            )
    # Threshold authority bounds in the single-implementation module.
    conduction_state = BACKEND / "app/finance_reconciliation/conduction_state.py"
    if conduction_state.is_file():
        state_source = conduction_state.read_text(encoding="utf-8")
        for required in (
            "B26_P2_MAX_STALENESS_SECONDS",
            "if value > 86400:",
            "def operational_disposition",
            "def quarantine_snapshot",
            "b26_p2_record_conduction_receipt",
        ):
            if required not in state_source:
                violations.append(
                    f"p2_vi_threshold_authority_absent:{required}"
                )
    else:
        violations.append("p2_vi_threshold_authority_absent:module_missing")
    details["corrective_vi_checked"] = True


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
        _check_policy_corrective_law(violations, details)
        _check_refusal_never_returned(violations, details)
        _check_conduction_law(violations, details)
        _check_live_conduction_wiring(violations, details)
        _check_webhook_phase_boundary(violations, details)
        _check_corrective_ii_law(violations, details)
        _check_corrective_iii_law(violations, details)
        _check_corrective_iv_law(violations, details)
        _check_corrective_v_law(violations, details)
        _check_corrective_vi_law(violations, details)
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
