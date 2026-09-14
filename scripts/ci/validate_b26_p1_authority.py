#!/usr/bin/env python3
"""Validate B2.6-P1 semantic, import-boundary, and CI authority."""

from __future__ import annotations

import argparse
import ast
import hashlib
import importlib
import json
import os
import sys
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Iterable
from uuid import UUID

import yaml  # type: ignore[import-untyped]


REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"
sys.path.insert(0, str(REPO_ROOT))
CONTRACT_PATH = REPO_ROOT / "contracts/reconciliation/b2.6/semantic-authority.v1.yaml"
PROOF_REQUIREMENTS_PATH = (
    REPO_ROOT / "contracts/reconciliation/b2.6/proof-requirements.v1.yaml"
)
GOVERNANCE_PATH = (
    REPO_ROOT / "contracts/reconciliation/b2.6/expected-governance.v1.yaml"
)
REQUIRED_STATUS_PATH = (
    REPO_ROOT
    / "contracts-internal/governance/b03_phase2_required_status_checks.main.json"
)
WORKFLOW_PATH = (
    REPO_ROOT / ".github/workflows/b2_6-p1-finance-reconciliation-adjudication.yml"
)
B26_PACKAGE = BACKEND / "app/finance_reconciliation"
PRODUCTION_DOCKERFILE = REPO_ROOT / "backend/Dockerfile"

GOVERNING_CONTEXT = "B2.6 Finance Reconciliation Adjudication"
DIAGNOSTIC_CONTEXT = "B2.6 P1 Exact-Main Diagnostics"
AGGREGATE_JOB = "b26-p1-finance-reconciliation-adjudication"
PRODUCER_JOBS = {
    "b26-p1-static-authority",
    "b26-p1-container-equivalence",
    "b26-p1-inherited-conduction",
}
EXPECTED_AGGREGATE_NAME = (
    "${{ github.event_name == 'push' && 'B2.6 P1 Exact-Main Diagnostics' "
    "|| 'B2.6 Finance Reconciliation Adjudication' }}"
)
EXPECTED_GATES = {
    "B26-P1-G1-G2-INHERITED-PHYSICS",
    "B26-P1-G3-G10-CONTAINER-EQUIVALENCE",
    "B26-P1-G4-SEMANTIC-AUTHORITY",
    "B26-P1-G8-EXECUTION-IDENTITY",
    "B26-P1-G9-NEGATIVE-CONTROLS",
}
EXPECTED_GATE_PRODUCERS = {
    "B26-P1-G4-SEMANTIC-AUTHORITY": "b26-p1-static-authority",
    "B26-P1-G8-EXECUTION-IDENTITY": "b26-p1-static-authority",
    "B26-P1-G9-NEGATIVE-CONTROLS": "b26-p1-static-authority",
    "B26-P1-G3-G10-CONTAINER-EQUIVALENCE": "b26-p1-container-equivalence",
    "B26-P1-G1-G2-INHERITED-PHYSICS": "b26-p1-inherited-conduction",
}
EXPECTED_IDENTITY_FIELDS = {
    "gate_id",
    "phase",
    "contract_version",
    "contract_hash",
    "candidate_sha",
    "candidate_tree",
    "migration_head",
    "producer",
    "workflow",
    "event_type",
    "run_id",
    "artifact_hash",
    "scenario_id",
    "falsifier_id",
    "status",
}

FORBIDDEN_IMPORT_PREFIXES = (
    "app.services.revenue_reconciliation",
    "app.api.reconciliation",
    "app.api.export",
    "app.llm",
    "app.bayesian",
    "app.simulation",
    "app.explanation",
    "celery",
    "kombu",
)
# Worker-mechanism subset of the import fence (Corrective II-2): broker-client
# imports are P1-closure-prohibited worker wiring, lifted together with AST
# machinery names under a governed successor authorization. Every other
# forbidden import (legacy finance authority, LLM/estimation surfaces) is a
# permanent ontological boundary and is never lifted.
WORKER_MECHANISM_IMPORT_PREFIXES = (
    "celery",
    "kombu",
)
# Repo-wide legacy fence (Corrective II): these first-party modules must never
# be imported as finance authority anywhere under backend/app. Zero legitimate
# production importers exist, so repo-wide enforcement has no false positives.
REPO_WIDE_FORBIDDEN_IMPORT_PREFIXES = (
    "app.services.revenue_reconciliation",
    "app.api.reconciliation",
    "app.api.export",
)
FORBIDDEN_SQL_AUTHORITY_TOKENS = (
    "revenue_ledger",
    "reconciliation_runs",
    "attribution_allocations",
    "canonical_net_verified_amount_minor",
    "verified_amount_minor",
)
# P1 closure coordinate (historical fact). Permanent law is ancestry, not equality.
P1_CLOSURE_MIGRATION_HEAD = "202609072001"
# A file is a plausible future B2.6 authority surface when its repo-relative
# path contains one of these substrings. Canonical package always matches via
# "finance_reconciliation". Audit probes used future_b26_probe/.
B26_SURFACE_SUBSTRINGS = (
    "finance_reconciliation",
    "finance",
    "reconcil",
    "b26",
    "future_b26",
    "future_finance",
)
# Known fenced legacy definitions (Corrective II-2): these files ARE the fenced
# false authorities, not future consumers. They are NOT skipped: every new
# violation signature inside them is RED. Only the exact violation signatures
# measured at P1 closure (rule + symbol, line numbers stripped so cosmetic
# edits stay GREEN) are grandfathered. schemas/reconciliation.py carries no
# violations and is scanned as an ordinary surface.
KNOWN_GRANDFATHERED_SURFACE_SIGNATURES = {
    "backend/app/api/reconciliation.py": frozenset(
        {
            "b26_prohibited_product_machinery:APIRouter",
            "b26_authoritative_float_literal",
            "b26_duplicate_financial_sql",
        }
    ),
    "backend/app/api/export.py": frozenset(
        {
            "b26_prohibited_product_machinery:APIRouter",
            "b26_authoritative_float_literal",
            "b26_duplicate_financial_sql",
        }
    ),
    "backend/app/services/revenue_reconciliation.py": frozenset(
        {
            "b26_duplicate_financial_sql",
        }
    ),
}
# Coverage-money columns: the B2.3 coverage-money identity. Any SQL aggregation
# over these columns outside the grandfathered sovereign files is a duplicate
# coverage authority candidate and is RED, regardless of directory naming.
# Legitimate growth consumes the B2.3 callable (LG-09, GREEN); new coverage SQL
# must amend this registry through a recorded contract migration, never silently.
COVERAGE_MONEY_SQL_TOKENS = (
    "verified_amount_minor",
    "canonical_net_verified_amount_minor",
)
COVERAGE_SQL_GRANDFATHERED_FILES = frozenset(
    {
        "backend/app/revenue_verification/verification_coverage.py",
        "backend/app/revenue_verification/batch_engine.py",
        "backend/app/revenue_verification/match_engine_kernel.py",
        "backend/app/bayesian/eligibility.py",
    }
)
# semantic_contract.py legitimately names total_business_minor inside the golden
# falsification vector as the forbidden reference. Exclude only that file from
# the total-business string fence; every other B2.6 surface must not name it.
TOTAL_BUSINESS_ALLOWLIST_FILES = frozenset(
    {
        "backend/app/finance_reconciliation/semantic_contract.py",
    }
)
# Network-capable clients must never appear in a canonical B2.6 surface
# (Corrective III, Theorem A). A B2.6 module holding one of these clients
# could invoke the mounted legacy reconciliation surface and consume its
# response, so capability is refused at the boundary. Plain URL parsing
# (urllib.parse) carries no fetch capability and stays permitted. Diagnostic
# code outside B2.6 surfaces is unaffected: it simply can never be admitted
# as canonical authority (see coverage_authority.admit_*).
LEGACY_NETWORK_CLIENT_PREFIXES = (
    "httpx",
    "requests",
    "aiohttp",
    "urllib.request",
    "urllib3",
    "http.client",
)
# Legacy operation paths quarantined as compatibility-only (Corrective III).
# The /api/reconciliation prefix itself is shared with the sovereign B2.3
# verdict routes, so only the legacy operations are fenced. The quarantine
# registry module and the semantic contract declare these paths as data;
# every other B2.6 surface must not name them.
LEGACY_QUARANTINED_ROUTE_LITERALS = (
    "/api/reconciliation/status",
    "/api/reconciliation/platform",
    "/api/reconciliation/sync",
)
LEGACY_ROUTE_LITERAL_ALLOWLIST_FILES = frozenset(
    {
        "backend/app/finance_reconciliation/legacy_quarantine.py",
        "backend/app/finance_reconciliation/semantic_contract.py",
    }
)
# Positive coverage-origin seal (Corrective III, Theorem B). The sealed type
# may only be constructed inside its defining authority module; every other
# B2.6 surface holding a CanonicalVerificationCoverage(...) construction is
# attempting to forge canonical origin and is RED. Unsealed runtime forgeries
# are additionally refused by admit_canonical_verification_coverage.
CANONICAL_SEALED_TYPE_NAME = "CanonicalVerificationCoverage"
CANONICAL_SEAL_DEFINING_FILE = (
    "backend/app/finance_reconciliation/coverage_authority.py"
)
# Executable canonical-output fence (Corrective V): the framework-owned
# final output type may only be constructed inside its defining framework
# module; every other first-party application module constructing it is an
# unregistered canonical origin and is RED. Ordinary analytics that never
# touch this type stay GREEN: canonicality is the governed interface, not
# the ability to compute a ratio.
FINAL_OUTPUT_TYPE_NAME = "FinalCanonicalOutput"
FINAL_OUTPUT_DEFINING_FILE = "backend/app/finance_reconciliation/canonical_sink.py"
# AST names that would create P1-prohibited product machinery inside a B2.6
# surface (tables, APIs, workers/schedulers, outbox). Docstrings/comments are
# not AST names, so prose mentioning these words stays GREEN.
FORBIDDEN_B26_PRODUCT_MACHINERY_NAMES = frozenset(
    {
        "Table",
        "Column",
        "APIRouter",
        "shared_task",
        "Celery",
        "outbox",
        "Outbox",
    }
)


def _load_yaml(path: Path, *, base_loader: bool = False) -> Any:
    loader = yaml.BaseLoader if base_loader else yaml.SafeLoader
    return yaml.load(path.read_text(encoding="utf-8"), Loader=loader)


def _resolve_dotted(path: str) -> Any:
    module_name, _, attribute = path.rpartition(".")
    if not module_name or not attribute:
        raise ValueError(f"invalid_dotted_authority:{path}")
    module = importlib.import_module(module_name)
    return getattr(module, attribute)


def _imports(tree: ast.AST) -> Iterable[str]:
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                yield alias.name
        elif isinstance(node, ast.ImportFrom) and node.module:
            yield node.module


def _dynamic_imports(tree: ast.AST) -> Iterable[str]:
    """Yield dotted module names loaded via importlib.import_module/__import__.

    Open-world probe (Corrective II-2): a static Import-node fence alone misses
    dynamic loads of fenced legacy authority. Aliased imports
    (``import importlib as il`` / ``from importlib import import_module as im``)
    are resolved so renaming does not evade the fence. Only constant-string
    targets are reported; non-constant targets cannot be resolved statically
    and remain a documented residual (see final report).
    """
    importlib_aliases = {"importlib"}
    import_module_aliases: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name == "importlib":
                    importlib_aliases.add(alias.asname or alias.name)
        elif isinstance(node, ast.ImportFrom) and node.module == "importlib":
            for alias in node.names:
                if alias.name == "import_module":
                    import_module_aliases.add(alias.asname or alias.name)
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        target: str | None = None
        if (
            isinstance(func, ast.Attribute)
            and func.attr == "import_module"
            and isinstance(func.value, ast.Name)
            and func.value.id in importlib_aliases
        ):
            if node.args and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                target = value if isinstance(value, str) else None
        elif isinstance(func, ast.Name) and (
            func.id == "__import__" or func.id in import_module_aliases
        ):
            if node.args and isinstance(node.args[0], ast.Constant):
                value = node.args[0].value
                target = value if isinstance(value, str) else None
        if target:
            yield target


def _successor_authorizes_machinery() -> bool:
    """Return True only when the live contract records a governed phase grant."""
    try:
        sys.path.insert(0, str(BACKEND))
        from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
            B26_SUCCESSOR_STATUS_AUTHORIZED,
            load_b26_p1_semantic_contract,
        )

        contract = load_b26_p1_semantic_contract()
        successor = contract.get("successor_product_authorization", {})
        return successor.get("status") == B26_SUCCESSOR_STATUS_AUTHORIZED
    except Exception:  # noqa: BLE001
        return False


def _violation_signature(violation: str) -> str:
    """Reduce a violation line to its grandfather-comparable signature.

    Line numbers are stripped so cosmetic edits inside grandfathered files stay
    GREEN; any new rule or symbol is a new signature and stays RED. Legacy
    imports are never grandfathered (always emitted separately).
    """
    parts = violation.split(":")
    rule = parts[0]
    if rule == "b26_prohibited_product_machinery" and len(parts) >= 4:
        return f"{rule}:{parts[2]}"
    return rule


def _native_revision_graph() -> tuple[dict[str, list[str]], set[str]]:
    """Load the authoritative revision graph through native Alembic machinery.

    Corrective III, Theorem C: P1 observes Alembic's own configured revision
    universe (ScriptDirectory over the repository's actual alembic.ini
    version_locations) instead of a redundant custom language parser. Any
    legal Python declaration form Alembic accepts is therefore observed
    identically, and files outside the configured locations never enter the
    authoritative graph. Offline: no database required.
    """
    from alembic.config import Config  # noqa: PLC0415
    from alembic.script import ScriptDirectory  # noqa: PLC0415

    config = Config(str(REPO_ROOT / "alembic.ini"))
    script = ScriptDirectory.from_config(config)
    graph: dict[str, list[str]] = {}
    for revision in script.walk_revisions():
        down = revision.down_revision
        if down is None:
            parents: list[str] = []
        elif isinstance(down, str):
            parents = [down]
        else:
            parents = list(down)
        graph[revision.revision] = parents
    return graph, set(script.get_heads())


def _migration_heads() -> set[str]:
    _, heads = _native_revision_graph()
    return heads


def _alembic_revision_graph() -> dict[str, list[str]]:
    """Authoritative revision graph: native Alembic, single universe."""
    graph, _ = _native_revision_graph()
    return graph


def _is_ancestor(ancestor: str, descendant: str, graph: dict[str, list[str]]) -> bool:
    seen: set[str] = set()
    stack = [descendant]
    while stack:
        current = stack.pop()
        if current == ancestor:
            return True
        if current in seen:
            continue
        seen.add(current)
        stack.extend(graph.get(current, []))
    return False


def _check_migration_ancestry(
    violations: list[str], details: dict[str, Any], expected_closure_head: str
) -> None:
    """Permanent law: every current head must descend from P1 closure head.

    Historical equality (heads == {closure}) is a PHASE_LOCAL closure fact and
    MUST NOT block lawful descendant migrations. Ancestry + intact P1 semantics
    (checked via the semantic contract loader above) is the permanent law.
    """
    try:
        graph, migration_heads = _native_revision_graph()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"b26_p1_migration_heads_unresolvable:{exc}")
        return
    details["migration_heads"] = sorted(migration_heads)
    details["p1_closure_migration_head"] = expected_closure_head
    details["revision_graph_source"] = "alembic_native_ScriptDirectory"
    details["native_revision_count"] = len(graph)
    if len(migration_heads) != 1:
        violations.append(
            f"b26_p1_migration_branch_detected:heads={sorted(migration_heads)}"
        )
        return
    if expected_closure_head in migration_heads:
        if expected_closure_head not in graph:
            violations.append(
                f"b26_p1_closure_head_missing_from_history:expected={expected_closure_head}"
            )
            return
        details["migration_ancestry"] = "at_p1_closure_head"
        return
    head = next(iter(migration_heads))
    if (
        expected_closure_head not in graph
        and expected_closure_head not in migration_heads
    ):
        # Closure revision file missing entirely: history was rewritten.
        violations.append(
            f"b26_p1_closure_head_missing_from_history:expected={expected_closure_head}"
        )
        return
    if not _is_ancestor(expected_closure_head, head, graph):
        violations.append(
            f"b26_p1_unjustified_migration_head_drift:"
            f"expected_ancestor={expected_closure_head}:actual={sorted(migration_heads)}"
        )
        return
    details["migration_ancestry"] = f"descendant_of_{expected_closure_head}"


def _validate_contract_and_b23_binding(
    violations: list[str], details: dict[str, Any]
) -> None:
    os.environ.setdefault(
        "DATABASE_URL",
        "postgresql+asyncpg://app_user:app_user@127.0.0.1:5432/b26_p1_static",
    )
    sys.path.insert(0, str(BACKEND))
    try:
        from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
            load_b26_p1_semantic_contract,
            semantic_contract_identity,
        )
        from app.revenue_verification.verification_coverage import (  # noqa: PLC0415
            SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES,
            SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS,
            VerificationCoverageAggregate,
        )

        contract = load_b26_p1_semantic_contract()
        identity = semantic_contract_identity()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"semantic_contract_refused:{exc}")
        return

    coverage = contract["coverage_authority"]
    expected_closure_head = contract["migration_authority"].get(
        "p1_closure_head", P1_CLOSURE_MIGRATION_HEAD
    )
    _check_migration_ancestry(violations, details, str(expected_closure_head))
    try:
        aggregate_callable = _resolve_dotted(coverage["aggregate_callable"])
        metric = _resolve_dotted(coverage["metric_object"])
        providers = _resolve_dotted(coverage["supported_provider_scope_reference"])
        currencies = _resolve_dotted(coverage["supported_currency_scope_reference"])
    except Exception as exc:  # noqa: BLE001
        violations.append(f"coverage_authority_unresolvable:{exc}")
        return

    if (
        aggregate_callable.__module__
        != "app.revenue_verification.verification_coverage"
    ):
        violations.append("coverage_aggregate_callable_not_b23_sovereign")
    if metric.__class__.__module__ != "app.revenue_verification.verification_coverage":
        violations.append("coverage_metric_object_not_b23_sovereign")
    if providers != SUPPORTED_VERIFICATION_COVERAGE_PLATFORMS:
        violations.append("coverage_provider_scope_reference_mismatch")
    if currencies != SUPPORTED_VERIFICATION_COVERAGE_CURRENCIES:
        violations.append("coverage_currency_scope_reference_mismatch")

    seam = contract["coverage_authority"]["canonical_admission_seam"]
    try:
        seam_module = importlib.import_module(seam["module"])
        sealed_type = getattr(seam_module, "CanonicalVerificationCoverage")
        loader = getattr(seam_module, "load_canonical_verification_coverage")
        admitter = getattr(seam_module, "admit_canonical_verification_coverage")
        scope_verifier = getattr(seam_module, "require_canonical_scope")
        producer = getattr(seam_module, "B23_SOVEREIGN_COVERAGE_PRODUCER")
        resolver = getattr(seam_module, "resolve_canonical_coverage")
        oracle = getattr(seam_module, "independent_coverage_percent")
        diagnostic = getattr(seam_module, "to_diagnostic_dict")
        law = getattr(seam_module, "CANONICAL_COVERAGE_LAW")
        provenance_model = getattr(seam_module, "CANONICAL_PROVENANCE_MODEL")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"coverage_admission_seam_unresolvable:{exc}")
        return
    if producer != seam["sovereign_producer"]:
        violations.append("coverage_admission_producer_reference_mismatch")
    if (
        sealed_type.__module__ != "app.finance_reconciliation.coverage_authority"
        or loader.__module__ != "app.finance_reconciliation.coverage_authority"
        or admitter.__module__ != "app.finance_reconciliation.coverage_authority"
        or scope_verifier.__module__ != "app.finance_reconciliation.coverage_authority"
        or resolver.__module__ != "app.finance_reconciliation.coverage_authority"
    ):
        violations.append("coverage_admission_seam_not_authority_owned")
    if law != seam.get("law"):
        violations.append("coverage_admission_law_mismatch")
    if law != "only_sovereign_rederivation_may_be_canonical":
        violations.append("coverage_admission_law_not_scope_only_rederivation")
    if provenance_model != seam.get("provenance_model"):
        violations.append("coverage_provenance_model_mismatch")
    if seam.get("admitter_behavior") != "always_refuses_caller_observation_fail_closed":
        violations.append("coverage_admitter_behavior_not_fail_closed")
    if seam.get("resolver") != (
        "app.finance_reconciliation.coverage_authority.resolve_canonical_coverage"
    ):
        violations.append("coverage_resolver_identity_mismatch")
    # The seam must refuse a numerically correct but unregistered value:
    # origin refusal is runtime physics, not lexical coincidence.
    try:
        admitter(9500)
    except Exception:  # noqa: BLE001
        pass
    else:
        violations.append("coverage_admission_seam_accepts_unregistered_origin")
    # Corrective IV non-vacuity: the transferable seal is removed, and every
    # caller-manufactured representation -- however shaped, however
    # numerically correct -- is refused by the fail-closed admission shim.
    # These falsifiers run on every validator execution so a green validator
    # implies red forgeries (proof plane targets consequence, not form).
    try:
        from app.revenue_verification.verification_coverage import (  # noqa: PLC0415
            VerificationCoverageResult,
        )

        from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
            CanonicalVerificationCoverage,
        )

        if hasattr(CanonicalVerificationCoverage, "_sealed") or (
            "_sealed" in getattr(sealed_type, "__dataclass_fields__", {})
        ):
            violations.append("coverage_transferable_seal_survives")
        golden_aggregate = VerificationCoverageAggregate(
            tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
            currency_code="USD",
            window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
            window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
            matched_webhook_revenue_minor=76000,
            connected_platform_revenue_minor=80000,
        )
        golden_result = VerificationCoverageResult(
            tenant_id=golden_aggregate.tenant_id,
            currency_code="USD",
            window_start=golden_aggregate.window_start,
            window_end=golden_aggregate.window_end,
            numerator_matched_webhook_revenue_minor=76000,
            denominator_connected_platform_revenue_minor=80000,
            coverage_percent=Decimal("95.00"),
            zero_denominator=False,
        )
        forged_correct = CanonicalVerificationCoverage(
            aggregate=golden_aggregate,
            result=golden_result,
            producer=producer,
            supported_platforms=("paypal", "shopify", "stripe", "woocommerce"),
        )
        for probe, probe_id in (
            (forged_correct, "forged_correct_shape"),
            (9500, "plain_scalar"),
            ({"coverage_percent": "95.00"}, "plain_mapping"),
        ):
            try:
                admitter(probe)
            except Exception:  # noqa: BLE001
                pass
            else:
                violations.append(
                    f"coverage_admission_accepts_caller_observation:{probe_id}"
                )
        wrong_result = VerificationCoverageResult(
            tenant_id=golden_aggregate.tenant_id,
            currency_code="USD",
            window_start=golden_aggregate.window_start,
            window_end=golden_aggregate.window_end,
            numerator_matched_webhook_revenue_minor=76000,
            denominator_connected_platform_revenue_minor=80000,
            coverage_percent=Decimal("76.00"),
            zero_denominator=False,
        )
        forged_wrong = CanonicalVerificationCoverage(
            aggregate=golden_aggregate,
            result=wrong_result,
            producer=producer,
            supported_platforms=("paypal", "shopify", "stripe", "woocommerce"),
        )
        try:
            scope_verifier(
                forged_wrong,
                tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
                currency_code="USD",
                window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
                window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
                supported_platforms=["paypal", "shopify", "stripe", "woocommerce"],
            )
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append("coverage_scope_verifier_trusts_wrong_mathematics")
        # Independent oracle (never calls sovereign compute for expected):
        if oracle(76000, 80000) != (Decimal("95.00"), False):
            violations.append("coverage_independent_oracle_wrong_95")
        if oracle(0, 0) != (Decimal("0.00"), True):
            violations.append("coverage_independent_oracle_wrong_zero")
        # Diagnostic must project only the one-way tenant hash, never raw UUID.
        rendered = diagnostic(forged_correct)
        if "tenant_id" in rendered:
            violations.append("coverage_diagnostic_emits_raw_tenant_id")
        if "tenant_id_hash" not in rendered:
            violations.append("coverage_diagnostic_missing_tenant_hash")
        else:
            from app.trust.refusal import tenant_hash  # noqa: PLC0415

            if rendered["tenant_id_hash"] != tenant_hash(
                UUID("11111111-1111-1111-1111-111111111111")
            ):
                violations.append("coverage_diagnostic_tenant_hash_mismatch")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"coverage_corrective_iv_falsifier_error:{exc}")
    details["coverage_admission_seam"] = {
        "module": seam["module"],
        "law": seam["law"],
        "producer": producer,
        "provenance_model": provenance_model,
    }

    coverage_source = (
        REPO_ROOT / "backend/app/revenue_verification/verification_coverage.py"
    )
    source_ast_hash = hashlib.sha256(
        ast.dump(
            ast.parse(coverage_source.read_text(encoding="utf-8")),
            include_attributes=False,
        ).encode("utf-8")
    ).hexdigest()
    if source_ast_hash != coverage.get("implementation_ast_sha256"):
        violations.append(
            "coverage_implementation_identity_mismatch:"
            f"expected={coverage.get('implementation_ast_sha256')}:actual={source_ast_hash}"
        )

    vector = coverage["golden_falsification_vector"]
    aggregate = VerificationCoverageAggregate(
        tenant_id=UUID("11111111-1111-1111-1111-111111111111"),
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(2026, 2, 1, tzinfo=timezone.utc),
        matched_webhook_revenue_minor=vector["matched_minor"],
        connected_platform_revenue_minor=vector["connected_supported_minor"],
    )
    observed = metric.compute(aggregate).coverage_percent
    if observed != Decimal(vector["required_percent"]):
        violations.append(f"coverage_golden_vector_wrong:{observed}")
    if observed == Decimal(vector["forbidden_percent"]):
        violations.append("coverage_total_business_denominator_reentered")

    details.update(
        {
            "contract_source_sha256": identity.source_sha256,
            "contract_semantic_sha256": identity.semantic_sha256,
            "coverage_implementation_ast_sha256": source_ast_hash,
            "coverage_observed_percent": str(observed),
            "coverage_providers": sorted(providers),
            "coverage_currencies": sorted(currencies),
        }
    )
    if "migration_heads" not in details:
        try:
            details["migration_heads"] = sorted(_migration_heads())
        except Exception:  # noqa: BLE001
            pass


def _is_b26_surface(path: Path) -> bool:
    rel = path.relative_to(REPO_ROOT).as_posix().lower()
    return any(sub in rel for sub in B26_SURFACE_SUBSTRINGS)


def _check_b26_file_semantics(
    path: Path,
    source: str,
    tree: ast.AST,
    violations: list[str],
    *,
    enforce_product_machinery: bool = True,
) -> None:
    rel = path.relative_to(REPO_ROOT).as_posix()
    for imported in _imports(tree):
        if any(
            imported == prefix or imported.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ):
            if not enforce_product_machinery and any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in WORKER_MECHANISM_IMPORT_PREFIXES
            ):
                # Governed successor phase: the worker-mechanism imports are
                # permitted alongside machinery names. Legacy finance authority
                # and LLM/estimation imports below stay banned permanently.
                continue
            violations.append(f"b26_false_authority_import:{rel}:{imported}")
        if any(
            imported == prefix or imported.startswith(prefix + ".")
            for prefix in LEGACY_NETWORK_CLIENT_PREFIXES
        ):
            violations.append(
                f"b26_legacy_network_client_in_canonical_surface:{rel}:{imported}"
            )
    for dynamic in _dynamic_imports(tree):
        if any(
            dynamic == prefix or dynamic.startswith(prefix + ".")
            for prefix in FORBIDDEN_IMPORT_PREFIXES
        ):
            violations.append(f"b26_dynamic_false_authority_import:{rel}:{dynamic}")
        if any(
            dynamic == prefix or dynamic.startswith(prefix + ".")
            for prefix in LEGACY_NETWORK_CLIENT_PREFIXES
        ):
            violations.append(
                f"b26_legacy_network_client_in_canonical_surface:{rel}:{dynamic}"
            )
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, float):
            violations.append(f"b26_authoritative_float_literal:{rel}:{node.lineno}")
        if isinstance(node, ast.Call):
            func = node.func
            called = (
                func.id
                if isinstance(func, ast.Name)
                else func.attr if isinstance(func, ast.Attribute) else ""
            )
            if (
                called == CANONICAL_SEALED_TYPE_NAME
                and rel != CANONICAL_SEAL_DEFINING_FILE
            ):
                violations.append(
                    f"b26_unregistered_coverage_origin:{rel}:{node.lineno}"
                )
        if enforce_product_machinery:
            if (
                isinstance(node, ast.Name)
                and node.id in FORBIDDEN_B26_PRODUCT_MACHINERY_NAMES
            ):
                violations.append(
                    f"b26_prohibited_product_machinery:{rel}:{node.id}:{node.lineno}"
                )
            if (
                isinstance(node, ast.Attribute)
                and node.attr in FORBIDDEN_B26_PRODUCT_MACHINERY_NAMES
            ):
                violations.append(
                    f"b26_prohibited_product_machinery:{rel}:{node.attr}:{node.lineno}"
                )
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            lowered = node.value.lower()
            if "select " in lowered or "sum(" in lowered:
                if any(token in lowered for token in FORBIDDEN_SQL_AUTHORITY_TOKENS):
                    violations.append(
                        f"b26_duplicate_financial_sql:{rel}:{node.lineno}"
                    )
            if (
                "total_business" in lowered
                and rel not in TOTAL_BUSINESS_ALLOWLIST_FILES
            ):
                violations.append(
                    f"b26_total_business_denominator_authority:{rel}:{node.lineno}"
                )
            if rel not in LEGACY_ROUTE_LITERAL_ALLOWLIST_FILES and any(
                literal in node.value for literal in LEGACY_QUARANTINED_ROUTE_LITERALS
            ):
                violations.append(
                    f"b26_legacy_route_reference_in_canonical_surface:{rel}:{node.lineno}"
                )
    if "total_business" in source.lower() and rel not in TOTAL_BUSINESS_ALLOWLIST_FILES:
        # Catch non-string occurrences (variable names, comments excluded by AST
        # are intentionally not distinguished: B2.6 surfaces must not name a
        # total-business denominator at all).
        if not any(
            f"b26_total_business_denominator_authority:{rel}:" in v for v in violations
        ):
            violations.append(f"b26_total_business_denominator_authority:{rel}:source")


def _validate_b26_namespace(
    violations: list[str], details: dict[str, Any], *, enforce_product_machinery: bool
) -> None:
    """Permanent law is semantic prohibition, not file count.

    Lawful future modules under backend/app/finance_reconciliation/ (or any
    plausible future B2.6 surface) are GREEN when they contain no forbidden
    authority. Only semantic violations turn RED. The P1 closure file census
    is preserved in the contract closure_snapshot as a historical fact.
    The product-machinery prohibition is a P1-closure check: it is enforced
    unless the live contract records a governed successor-phase grant.
    """
    files = sorted(B26_PACKAGE.rglob("*.py"))
    if not files:
        violations.append("b26_p1_authority_package_missing")
        return
    for path in files:
        source = path.read_text(encoding="utf-8")
        try:
            tree = ast.parse(source, filename=str(path))
        except SyntaxError as exc:
            violations.append(
                f"b26_package_syntax_error:{path.relative_to(REPO_ROOT)}:{exc}"
            )
            continue
        _check_b26_file_semantics(
            path,
            source,
            tree,
            violations,
            enforce_product_machinery=enforce_product_machinery,
        )
    details["b26_namespace_files"] = [
        path.relative_to(REPO_ROOT).as_posix() for path in files
    ]
    details["b26_successor_product_machinery_enforced"] = enforce_product_machinery


def _check_repo_wide_coverage_and_denominator(
    path: Path, source: str, tree: ast.AST, violations: list[str]
) -> None:
    """System-wide duplicate-coverage fence (Corrective II-2).

    The coverage-money columns are the B2.3 coverage-money identity, and
    total_business names the forbidden denominator. Outside the grandfathered
    sovereign files, SQL aggregating coverage money or any mention of a
    total-business denominator in first-party application code is RED,
    regardless of directory naming (SW-08). Consuming the B2.3 callable
    without new coverage SQL stays GREEN (LG-09).
    """
    rel = path.relative_to(REPO_ROOT).as_posix()
    if rel not in COVERAGE_SQL_GRANDFATHERED_FILES:
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                lowered = node.value.lower()
                if "select " in lowered or "sum(" in lowered:
                    if any(token in lowered for token in COVERAGE_MONEY_SQL_TOKENS):
                        violations.append(
                            f"b26_duplicate_coverage_authority:{rel}:{node.lineno}"
                        )
                        break
    if rel not in TOTAL_BUSINESS_ALLOWLIST_FILES:
        found = False
        for node in ast.walk(tree):
            if isinstance(node, ast.Constant) and isinstance(node.value, str):
                if "total_business" in node.value.lower():
                    violations.append(
                        f"b26_total_business_denominator_authority:{rel}:{node.lineno}"
                    )
                    found = True
                    break
        if not found and "total_business" in source.lower():
            violations.append(f"b26_total_business_denominator_authority:{rel}:source")


def _validate_repo_wide_false_authority(
    violations: list[str], details: dict[str, Any], *, enforce_product_machinery: bool
) -> None:
    """System-wide fence (Corrective II).

    Legacy finance authority must not become reachable from any first-party
    application module, and duplicate finance-coverage authority must not appear
    in any plausible future B2.6 surface outside the canonical package.
    Grandfathered legacy definition files are scanned like any other surface:
    only their exact P1-closure violation signatures are tolerated, so new
    authority inside them is RED.
    """
    app_root = BACKEND / "app"
    legacy_hits: list[str] = []
    dynamic_hits: list[str] = []
    b26_surface_files: list[str] = []
    scanned = 0
    for path in sorted(app_root.rglob("*.py")):
        scanned += 1
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for imported in _imports(tree):
            if any(
                imported == prefix or imported.startswith(prefix + ".")
                for prefix in REPO_WIDE_FORBIDDEN_IMPORT_PREFIXES
            ):
                # The definition module itself and the B2.3 freeze list reference
                # the legacy symbol as a fenced string/registry entry, never as
                # an import. Only real imports are violations.
                legacy_hits.append(f"{rel}:{imported}")
                violations.append(f"b26_false_authority_import:{rel}:{imported}")
        for dynamic in _dynamic_imports(tree):
            if any(
                dynamic == prefix or dynamic.startswith(prefix + ".")
                for prefix in REPO_WIDE_FORBIDDEN_IMPORT_PREFIXES
            ):
                dynamic_hits.append(f"{rel}:{dynamic}")
                violations.append(f"b26_dynamic_false_authority_import:{rel}:{dynamic}")
        _check_repo_wide_coverage_and_denominator(path, source, tree, violations)
        # Corrective IV positive consumer governance (repo-wide, not surface
        # selected): the canonical coverage type may only be constructed
        # inside its defining authority module. Any other first-party
        # application module constructing it -- however named, however
        # pathed -- is an unregistered canonical origin and is RED. The
        # runtime root is stronger (admission always refuses), so this fence
        # is defense-in-depth that makes neutral emitters merge-blocking.
        if rel != CANONICAL_SEAL_DEFINING_FILE:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    called = (
                        func.id
                        if isinstance(func, ast.Name)
                        else func.attr if isinstance(func, ast.Attribute) else ""
                    )
                    if called == CANONICAL_SEALED_TYPE_NAME:
                        violations.append(
                            f"b26_unregistered_coverage_origin:{rel}:{node.lineno}"
                        )
                        break
        # Corrective V executable-output fence: the framework-owned final
        # output type may only be constructed inside the canonical-sink
        # framework module. Ordinary analytics never names it (GREEN).
        if rel != FINAL_OUTPUT_DEFINING_FILE:
            for node in ast.walk(tree):
                if isinstance(node, ast.Call):
                    func = node.func
                    called = (
                        func.id
                        if isinstance(func, ast.Name)
                        else func.attr if isinstance(func, ast.Attribute) else ""
                    )
                    if called == FINAL_OUTPUT_TYPE_NAME:
                        violations.append(
                            f"b26_unregistered_canonical_output:{rel}:{node.lineno}"
                        )
                        break
        if _is_b26_surface(path) or rel in KNOWN_GRANDFATHERED_SURFACE_SIGNATURES:
            # Canonical package already checked above to avoid duplicate lines.
            if path.is_relative_to(B26_PACKAGE):
                continue
            b26_surface_files.append(rel)
            collected: list[str] = []
            _check_b26_file_semantics(
                path,
                source,
                tree,
                collected,
                enforce_product_machinery=enforce_product_machinery,
            )
            known = KNOWN_GRANDFATHERED_SURFACE_SIGNATURES.get(rel, frozenset())
            for item in collected:
                if item.startswith("b26_false_authority_import:"):
                    # Legacy imports are never grandfathered; already reported above.
                    continue
                if _violation_signature(item) not in known:
                    violations.append(item)
    details["repo_wide_app_files_scanned"] = scanned
    details["repo_wide_legacy_import_hits"] = legacy_hits
    details["repo_wide_dynamic_import_hits"] = dynamic_hits
    details["b26_future_surface_files"] = sorted(b26_surface_files)


def _validate_governance(violations: list[str], details: dict[str, Any]) -> None:
    for path in (
        PROOF_REQUIREMENTS_PATH,
        GOVERNANCE_PATH,
        REQUIRED_STATUS_PATH,
        WORKFLOW_PATH,
    ):
        if not path.is_file():
            violations.append(
                f"required_authority_file_missing:{path.relative_to(REPO_ROOT)}"
            )
    if violations:
        return
    governance = _load_yaml(GOVERNANCE_PATH)
    requirements = _load_yaml(PROOF_REQUIREMENTS_PATH)
    required_status = json.loads(REQUIRED_STATUS_PATH.read_text(encoding="utf-8"))
    workflow = _load_yaml(WORKFLOW_PATH, base_loader=True)
    triggers = workflow.get("on", {})
    if set(triggers) != {"pull_request", "merge_group", "push"}:
        violations.append(f"b26_workflow_event_identity_drift:{sorted(triggers)}")
    push = triggers.get("push", {})
    if push.get("branches") != ["main"]:
        violations.append("b26_push_diagnostic_not_exact_main")
    jobs = workflow.get("jobs", {})
    if set(PRODUCER_JOBS) - set(jobs):
        violations.append("b26_required_producer_job_missing")
    aggregate = jobs.get(AGGREGATE_JOB, {})
    if aggregate.get("name") != EXPECTED_AGGREGATE_NAME:
        violations.append("b26_required_context_event_identity_ambiguous")
    if aggregate.get("if") != "always()":
        violations.append("b26_aggregate_not_fail_closed_always")
    if set(aggregate.get("needs", [])) != PRODUCER_JOBS:
        violations.append("b26_aggregate_dependency_set_drift")
    names = [str(job.get("name", "")) for job in jobs.values()]
    if sum(GOVERNING_CONTEXT in name for name in names) != 1:
        violations.append("b26_governing_context_emitter_count_not_one")
    if governance.get("required_context") != GOVERNING_CONTEXT:
        violations.append("b26_expected_governance_context_drift")
    if governance.get("diagnostic_context") != DIAGNOSTIC_CONTEXT:
        violations.append("b26_expected_diagnostic_context_drift")
    if set(governance.get("required_producer_jobs", [])) != PRODUCER_JOBS:
        violations.append("b26_expected_governance_producers_drift")
    if set(governance.get("governing_events", [])) != {"pull_request", "merge_group"}:
        violations.append("b26_governing_event_set_drift")
    if set(governance.get("required_context_must_not_emit_on", [])) != {
        "push",
        "workflow_dispatch",
    }:
        violations.append("b26_required_context_exclusion_set_drift")
    proof_cells = requirements.get("required_cells", [])
    observed_gates = {cell.get("gate_id") for cell in proof_cells}
    if not EXPECTED_GATES.issubset(observed_gates):
        violations.append("b26_proof_gate_census_drift")
    for gate_id, expected_producer in EXPECTED_GATE_PRODUCERS.items():
        matches = [cell for cell in proof_cells if cell.get("gate_id") == gate_id]
        if not matches:
            continue  # already reported as census drift above
        if matches[0].get("producer") != expected_producer:
            violations.append(f"b26_proof_producer_census_drift:{gate_id}")
    manifest_version = str(requirements.get("manifest_version", ""))
    if not manifest_version.startswith("b2.6-p1-proof-requirements-v"):
        violations.append("b26_proof_manifest_version_drift")
    if requirements.get("manifest_evolution_policy") != (
        "additive_only_permanent_P1_cells_remain_required"
    ):
        violations.append("b26_proof_manifest_evolution_policy_drift")
    additional = requirements.get("additional_accepted_cells", [])
    if not isinstance(additional, list):
        violations.append("b26_proof_additional_cells_malformed")
    else:
        for entry in additional:
            if (
                not isinstance(entry, dict)
                or "gate_id" not in entry
                or "producer" not in entry
            ):
                violations.append("b26_proof_additional_cells_malformed")
                break
            if "required" in entry and not isinstance(entry["required"], bool):
                violations.append("b26_proof_additional_cells_malformed")
                break
            if entry["gate_id"] in observed_gates:
                violations.append(
                    f"b26_proof_additional_cell_collides:{entry['gate_id']}"
                )
                break
    if (
        set(requirements.get("required_identity_fields", []))
        != EXPECTED_IDENTITY_FIELDS
    ):
        violations.append("b26_proof_identity_fields_drift")
    try:
        sys.path.insert(0, str(BACKEND))
        from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
            load_b26_p1_semantic_contract as _load_contract,
        )

        _contract_doc = _load_contract()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"semantic_contract_refused:{exc}")
        return
    if set(_contract_doc.get("proof_artifact_identity_requirements", [])) != set(
        requirements.get("required_identity_fields", [])
    ):
        violations.append("b26_proof_identity_fields_contract_manifest_mismatch")
    if set(requirements.get("accepted_events", [])) != {
        "pull_request",
        "merge_group",
        "push",
    }:
        violations.append("b26_proof_accepted_events_drift")
    required_contexts = required_status.get("required_contexts", [])
    if required_contexts.count(GOVERNING_CONTEXT) != 1:
        violations.append("b26_required_status_contract_binding_missing")
    workflow_text = WORKFLOW_PATH.read_text(encoding="utf-8")
    required_tokens = (
        "validate_b26_p1_authority.py",
        "test_b26_p1_negative_controls.py",
        "assert_b26_p1_container_equivalence.py",
        "attest_b26_p1_inherited_conduction.py",
        "adjudicate_b26_p1_proof_plane.py",
        "if-no-files-found: error",
    )
    for token in required_tokens:
        if token not in workflow_text:
            violations.append(f"b26_workflow_required_wiring_missing:{token}")
    details["workflow_events"] = sorted(triggers)
    details["aggregate_producers"] = sorted(PRODUCER_JOBS)


def _validate_corrective_v_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-VI authority: registry, executor, guards, law."""
    sys.path.insert(0, str(BACKEND))
    try:
        from app.finance_reconciliation import (
            tenant_authority as authority_module,
        )  # noqa: PLC0415
        from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
            SINK_REGISTRY,
            CanonicalSinkError,
            DuplicateSinkError,
            FinalCanonicalOutput,
            SuccessorProvenanceError,
            _SINK_IMPLEMENTATIONS,
            authorize_successor_persistence,
            canonical_sink,
            deregister_successor_persistence,
            executor_binds_tenant_from_verified_auth_only,
            executor_signature_has_no_session_capability,
            external_renderer_signature_is_execution_bound,
            register_successor_persistence,
            reject_authoritative_adjunct,
            render_governed_external,
            require_registered_sink,
        )
        from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
            GOVERNED_CANONICAL_SINK_NAMES,
        )
        from app.finance_reconciliation.proof_manifest import (  # noqa: PLC0415
            REQUIRED_SINK_PROOFS,
            require_proofs_bound,
        )
        from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
            B26_P1_CONTRACT_VERSION,
            load_b26_p1_semantic_contract,
        )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_v_authority_unresolvable:{exc}")
        return

    try:
        contract = load_b26_p1_semantic_contract()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"semantic_contract_refused:{exc}")
        return
    seam = contract["coverage_authority"]["canonical_admission_seam"]
    framework = contract["canonical_sink_framework"]
    if seam.get("tenant_authority_mode") != authority_module.TENANT_AUTHORITY_MODE:
        violations.append("corrective_v_tenant_authority_mode_mismatch")
    if (
        seam.get("database_capability_mode")
        != authority_module.DATABASE_CAPABILITY_MODE
    ):
        violations.append("corrective_v_database_capability_mode_mismatch")
    if (
        seam.get("sink_framework")
        != "app.finance_reconciliation.canonical_sink.execute_governed_sink"
    ):
        violations.append("corrective_v_sink_framework_identity_mismatch")
    if set(framework.get("governed_sink_ids", [])) != set(
        GOVERNED_CANONICAL_SINK_NAMES
    ):
        violations.append("corrective_v_sink_id_set_mismatch")
    if set(framework.get("governed_principals", [])) != set(
        authority_module.GOVERNED_CANONICAL_PRINCIPALS
    ):
        violations.append("corrective_v_governed_principals_mismatch")

    # Every governed sink id resolves to an importable executable with a
    # versioned registration bound to the current contract, a stable
    # executable hash, and the governed manifest proof set.
    for sink_id in sorted(GOVERNED_CANONICAL_SINK_NAMES):
        try:
            registration = require_registered_sink(sink_id)
        except Exception:  # noqa: BLE001
            violations.append(f"corrective_v_sink_not_executable:{sink_id}")
            continue
        if registration.contract_version != B26_P1_CONTRACT_VERSION:
            violations.append(f"corrective_v_sink_contract_stale:{sink_id}")
        if tuple(registration.required_runtime_proof_ids) != tuple(
            REQUIRED_SINK_PROOFS.get(sink_id, ())
        ):
            violations.append(f"corrective_v_sink_proofs_unbound:{sink_id}")
        if (
            not isinstance(registration.implementation_hash, str)
            or len(registration.implementation_hash) != 64
        ):
            violations.append(f"corrective_v_sink_executable_unbound:{sink_id}")
        try:
            module_name, _, attribute = registration.implementation.rpartition(".")
            implementation = getattr(importlib.import_module(module_name), attribute)
        except Exception:  # noqa: BLE001
            violations.append(f"corrective_v_sink_implementation_dead:{sink_id}")
            continue
        if not callable(implementation):
            violations.append(f"corrective_v_sink_implementation_dead:{sink_id}")
    try:
        if require_registered_sink("neutral_analytics_helper"):
            violations.append("corrective_v_unregistered_sink_admitted")
    except Exception:  # noqa: BLE001
        pass

    # Duplicate sink registration is refused: the first binding wins and a
    # second binding with different executable identity must not replace it.
    try:
        pristine_registration = SINK_REGISTRY.get("future_finance_projection")
        pristine_implementation = _SINK_IMPLEMENTATIONS.get("future_finance_projection")

        def _validator_probe_impl(context: Any) -> dict[str, Any]:
            return {}

        try:
            canonical_sink(
                sink_id="future_finance_projection",
                version="v9.9-validator-probe",
                required_runtime_proof_ids=("V-2", "V-3", "V-4"),
            )(_validator_probe_impl)
        except DuplicateSinkError:
            pass
        except Exception as exc:  # noqa: BLE001
            violations.append(f"canonical_sink_duplicate_wrong_refusal:{exc}")
        else:
            violations.append("canonical_sink_duplicate_not_refused")
        finally:
            if pristine_registration is not None:
                SINK_REGISTRY["future_finance_projection"] = pristine_registration
            if pristine_implementation is not None:
                _SINK_IMPLEMENTATIONS["future_finance_projection"] = (
                    pristine_implementation
                )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_sink_duplicate_probe_error:{exc}")

    # Forged proof identifiers are refused at declaration time.
    try:
        require_proofs_bound(
            sink_id="future_finance_projection",
            required_runtime_proof_ids=("FAKE",),
            contract_version=B26_P1_CONTRACT_VERSION,
        )
    except Exception:  # noqa: BLE001
        pass
    else:
        violations.append("proof_manifest_forgery_not_refused")
    try:
        require_proofs_bound(
            sink_id="future_finance_projection",
            required_runtime_proof_ids=("V-5",),
            contract_version=B26_P1_CONTRACT_VERSION,
        )
    except Exception:  # noqa: BLE001
        pass
    else:
        violations.append("proof_manifest_required_set_not_enforced")

    # No transferable canonical token may exist: the issuance map, the mint
    # helper, the nonce predicate, and the boolean predicate are deleted.
    # NOTE: the ``canonical_sink`` decorator re-exported on the package
    # shadows the submodule for ``import ... as`` bindings; importlib
    # returns the real module under test (a function binding would pass
    # these checks vacuously).
    try:
        sink_module = importlib.import_module(
            "app.finance_reconciliation.canonical_sink"
        )

        for deleted in (
            "_ISSUED_PROVENANCE_DIGESTS",
            "_issue_provenance",
            "is_canonical_output",
            "require_canonical_output",
        ):
            if hasattr(sink_module, deleted):
                violations.append(f"canonical_transferable_authority_present:{deleted}")
        import dataclasses as _dataclasses  # noqa: PLC0415

        output_fields = {
            field.name for field in _dataclasses.fields(FinalCanonicalOutput)
        }
        if "provenance_nonce" in output_fields:
            violations.append("canonical_transferable_nonce_present")
        if "content_digest" not in output_fields:
            violations.append("canonical_content_digest_missing")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_transferable_authority_unverifiable:{exc}")

    # The canonical executor must take no session capability parameter:
    # injection is structurally impossible, not merely refused. It must
    # additionally bind its tenant only from verified server auth: no
    # caller-supplied tenant and no callable parameter may exist.
    try:
        if not executor_signature_has_no_session_capability():
            violations.append("canonical_executor_accepts_session_capability")
        if not executor_binds_tenant_from_verified_auth_only():
            violations.append("canonical_executor_tenant_not_auth_bound")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_executor_signature_unverifiable:{exc}")

    # Tenant-authority bracketing must be present at the sovereign resolver:
    # one observation before aggregation, one after (mid-transaction switch
    # detection). Static sensor; behavior is proven by the DB consequence
    # battery, which is the load-bearing leg.
    try:
        resolver_source = (
            REPO_ROOT / "backend/app/finance_reconciliation/coverage_authority.py"
        ).read_text(encoding="utf-8")
        if (
            resolver_source.count("await assert_tenant_authority(session, tenant_id)")
            < 2
        ):
            violations.append("coverage_tenant_authority_not_enforced")
    except OSError as exc:
        violations.append(f"coverage_resolver_source_unreadable:{exc}")

    # Adjunct guard is live on every run: authoritative keys refuse, benign
    # adjuncts pass, tenant-bearing keys refuse.
    try:
        reject_authoritative_adjunct({"note": "lawful adjunct"})
        for hostile in (
            {"coverage_percent": "11.11"},
            {"matched_minor": 1},
            {"tenant_id": "raw"},
            {"tenant_label": "raw"},
        ):
            try:
                reject_authoritative_adjunct(hostile)
            except Exception:  # noqa: BLE001
                pass
            else:
                violations.append(
                    "canonical_adjunct_guard_not_enforced:" f"{sorted(hostile)}"
                )
    except CanonicalSinkError as exc:
        violations.append(f"canonical_adjunct_guard_rejects_lawful:{exc}")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_adjunct_guard_error:{exc}")

    # Successor provenance law is live: unknown refused, ungoverned mode
    # unregistrable, forged proofs unregistrable, and -- because P1 has no
    # migration-backed durable binding -- even a well-formed declaration
    # authorizes nothing durable.
    try:
        try:
            authorize_successor_persistence("no_such_successor_registration")
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append("successor_provenance_law_not_enforced:unknown")
        try:
            register_successor_persistence(
                registration_id="validator_probe_invalid",
                provenance_mode="anything",
                required_runtime_proof_ids=("VI-6",),
            )
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append("successor_provenance_law_not_enforced:mode")
            deregister_successor_persistence("validator_probe_invalid")
        try:
            register_successor_persistence(
                registration_id="validator_probe_fake",
                provenance_mode="RE_DERIVE_ON_READ",
                required_runtime_proof_ids=("FAKE-PROOF",),
            )
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append("successor_provenance_law_not_enforced:proof")
            deregister_successor_persistence("validator_probe_fake")
        register_successor_persistence(
            registration_id="validator_probe_valid",
            provenance_mode="RE_DERIVE_ON_READ",
            required_runtime_proof_ids=("VI-6",),
        )
        try:
            authorize_successor_persistence("validator_probe_valid")
        except SuccessorProvenanceError:
            pass
        except Exception as exc:  # noqa: BLE001
            violations.append(f"successor_provenance_law_wrong_refusal:{exc}")
        else:
            violations.append("successor_provenance_law_not_enforced:authorize")
        finally:
            deregister_successor_persistence("validator_probe_valid")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"successor_provenance_law_error:{exc}")

    # Approved external projection never carries raw tenant identity.
    # Corrective-VII law: the projection is execution-bound (it renders the
    # fresh consequence of its own governed execution), so this DB-less
    # sensor proves the projection's static shape -- the exact emitted key
    # census of the `rendered` mapping -- while the consequence battery
    # proves runtime behavior with a database.
    try:
        import inspect as _inspect  # noqa: PLC0415

        from app.finance_reconciliation.external_semantics import (  # noqa: PLC0415
            EXTERNAL_SEMANTICS as _emitted_contract,
        )

        # Since Corrective XI the emitted universe IS the transform
        # contract's key census (the renderer derives every field through
        # it); the raw-tenant/adjunct exclusion law is unchanged.
        emitted_keys: set[str] = set(_emitted_contract)
        if "tenant_id" in emitted_keys:
            violations.append("canonical_external_emits_raw_tenant")
        if "tenant_id_hash" not in emitted_keys:
            violations.append("canonical_external_tenant_hash_mismatch")
        if "adjunct_json" in emitted_keys:
            violations.append("canonical_external_emits_non_authoritative_adjunct")
        if not external_renderer_signature_is_execution_bound():
            violations.append("canonical_external_renderer_not_execution_bound")
        renderer_source = (
            REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
        ).read_text(encoding="utf-8")
        if "await execute_governed_sink(" not in renderer_source:
            violations.append("canonical_external_renderer_not_execution_bound")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_projection_error:{exc}")

    # Independent oracle is pinned against ambient Decimal-context coupling.
    try:
        from decimal import getcontext  # noqa: PLC0415

        from app.finance_reconciliation.coverage_authority import (  # noqa: PLC0415
            independent_coverage_percent,
        )

        previous = getcontext().prec
        getcontext().prec = 2
        try:
            if independent_coverage_percent(76000, 80000) != (
                Decimal("95.00"),
                False,
            ):
                violations.append("coverage_oracle_context_coupled")
        finally:
            getcontext().prec = previous
    except Exception as exc:  # noqa: BLE001
        violations.append(f"coverage_oracle_pinning_error:{exc}")

    details["corrective_v_sinks"] = sorted(SINK_REGISTRY)
    details["corrective_v_executor"] = (
        "app.finance_reconciliation.canonical_sink.execute_governed_sink"
    )


def _returns_mapping(returns: ast.AST | None) -> bool:
    """Report whether a return annotation denotes a mapping projection."""
    if returns is None:
        return False
    if isinstance(returns, ast.Name) and returns.id == "dict":
        return True
    if isinstance(returns, ast.Subscript) and isinstance(returns.value, ast.Name):
        return returns.value.id == "dict"
    if isinstance(returns, ast.Constant) and isinstance(returns.value, str):
        return returns.value.strip().startswith("dict")
    return False


def _validate_corrective_vii_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-VII authority: token lifecycle, renderer shape, materialization."""
    sys.path.insert(0, str(BACKEND))
    sink_path = REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
    try:
        sink_source = sink_path.read_text(encoding="utf-8")
        sink_tree = ast.parse(sink_source)
    except (OSError, SyntaxError) as exc:
        violations.append(f"corrective_vii_sink_source_unreadable:{exc}")
        return

    # VII-A: the canonical boundary composes the complete sovereign
    # access-token state machine -- mandatory-claim extraction plus current
    # lifecycle enforcement -- never signature verification alone.
    if "extract_access_token_claims(claims)" not in sink_source:
        violations.append("canonical_required_claims_not_enforced")
    if "await assert_access_token_active(token_claims)" not in sink_source:
        violations.append("canonical_revocation_law_not_composed")

    # VII-B: no detached-object renderer may exist at any visibility; the
    # only approved projection executes the governed sink itself.
    try:
        sink_module = importlib.import_module(
            "app.finance_reconciliation.canonical_sink"
        )
        for deleted in ("to_canonical_external", "_project_external_fields"):
            if hasattr(sink_module, deleted):
                violations.append("canonical_external_promotion_surface_present")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_vii_sink_module_unresolvable:{exc}")
    if "async def render_governed_external" not in sink_source:
        violations.append("canonical_execution_bound_renderer_missing")
    for node in ast.walk(sink_tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        takes_detached_output = any(
            "FinalCanonicalOutput" in ast.dump(a.annotation)
            for a in (*node.args.args, *node.args.kwonlyargs)
            if a.annotation is not None
        )
        if not takes_detached_output:
            continue
        emits_mapping = _returns_mapping(node.returns) or any(
            isinstance(child, ast.Return) and isinstance(child.value, ast.Dict)
            for child in ast.walk(node)
        )
        if emits_mapping:
            violations.append("canonical_object_accepting_renderer_present")
            break

    # VII-C: authoritative fields are materialized from the sovereign
    # derivation (the `context` readout), never from projection output.
    # Only `adjunct_json` may derive from the governed `cleaned` adjuncts.
    found_output_construction = False
    for node in ast.walk(sink_tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else ""
        )
        if called != "FinalCanonicalOutput":
            continue
        found_output_construction = True
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            names = {
                child.id
                for child in ast.walk(keyword.value)
                if isinstance(child, ast.Name)
            }
            if keyword.arg == "adjunct_json":
                if "cleaned" not in names:
                    violations.append("canonical_adjunct_channel_not_governed")
            elif names & {"cleaned", "raw_adjunct"}:
                violations.append("canonical_framework_materialization_bypassed")
    if not found_output_construction:
        violations.append("canonical_framework_materialization_unverifiable")

    details["corrective_vii_sensors"] = sorted(
        [
            "canonical_required_claims_not_enforced",
            "canonical_revocation_law_not_composed",
            "canonical_external_promotion_surface_present",
            "canonical_object_accepting_renderer_present",
            "canonical_execution_bound_renderer_missing",
            "canonical_framework_materialization_bypassed",
        ]
    )


def _validate_corrective_viii_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-VIII authority: snapshot isolation + executable binding.

    VIII-A: every authoritative FinalCanonicalOutput field must derive
    from the framework-private ``_s_*`` snapshot locals (or a module
    constant for authority/provenance/producer identity) -- never from
    any projection-visible object (``context``, ``projection_view``,
    ``projection``, ``raw_adjunct``, ``cleaned``, ``adjunct``). Only
    ``adjunct_json`` may derive from the governed ``cleaned`` adjuncts.

    VIII-B: executable identity must be verified and captured atomically
    via ``_capture_verified_implementation`` after the last framework
    ``await``, and the captured ``verified_implementation`` reference
    must be the object invoked on the separate ``projection_view``.
    The legacy split pattern (verify-then-subscript-lookup across an
    ``await``) is refused.
    """
    sys.path.insert(0, str(BACKEND))
    sink_path = REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
    try:
        sink_source = sink_path.read_text(encoding="utf-8")
        sink_tree = ast.parse(sink_source)
    except (OSError, SyntaxError) as exc:
        violations.append(f"corrective_viii_sink_source_unreadable:{exc}")
        return

    projection_visible = {
        "context",
        "projection_view",
        "projection",
        "raw_adjunct",
        "cleaned",
        "adjunct",
    }
    snapshot_derived_fields = {
        "sink_id",
        "contract_version",
        "tenant_id_hash",
        "currency_code",
        "window_start",
        "window_end",
        "supported_platforms",
        "matched_minor",
        "connected_minor",
        "coverage_percent",
        "zero_denominator",
    }
    found_output_construction = False
    for node in ast.walk(sink_tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else ""
        )
        if called != "FinalCanonicalOutput":
            continue
        found_output_construction = True
        for keyword in node.keywords:
            if keyword.arg is None:
                continue
            names = {
                child.id
                for child in ast.walk(keyword.value)
                if isinstance(child, ast.Name)
            }
            if keyword.arg == "adjunct_json":
                if "cleaned" not in names:
                    violations.append("canonical_adjunct_channel_not_governed")
                continue
            if names & projection_visible:
                violations.append(
                    "canonical_authoritative_snapshot_not_isolated:" f"{keyword.arg}"
                )
            elif keyword.arg in snapshot_derived_fields and not (
                any(name.startswith("_s_") for name in names)
            ):
                violations.append(
                    "canonical_authoritative_snapshot_not_isolated:" f"{keyword.arg}"
                )
    if not found_output_construction:
        violations.append("canonical_authoritative_snapshot_unverifiable")

    # VIII-A structural shape: a private snapshot and a separate view.
    if "projection_view = AdjunctContext(" not in sink_source:
        violations.append("canonical_authoritative_snapshot_not_isolated:view")
    if (
        "_s_matched_minor" not in sink_source
        or "_s_coverage_percent" not in sink_source
    ):
        violations.append("canonical_authoritative_snapshot_not_isolated:snapshot")
    if "verified_implementation(projection_view)" not in sink_source:
        violations.append("canonical_authoritative_snapshot_not_isolated:invoke")

    # VIII-B structural shape: atomic capture, no split lookup.
    if "def _capture_verified_implementation(" not in sink_source:
        violations.append("canonical_executable_binding_not_atomic")
    if "_capture_verified_implementation(sink_id)" not in sink_source:
        violations.append("canonical_executable_binding_not_atomic")
    if "implementation = _SINK_IMPLEMENTATIONS[str(sink_id)]" in sink_source:
        violations.append("canonical_executable_check_use_diverged")
    # VIII-B ordering law: inside execute_governed_sink, the final atomic
    # capture must occur AFTER the last framework await that precedes the
    # projection invocation, so no suspension can split verification from
    # execution. Presence of the call is insufficient; position is law.
    executor = next(
        (
            node
            for node in ast.walk(sink_tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "execute_governed_sink"
        ),
        None,
    )
    if executor is None:
        violations.append("canonical_executable_binding_not_atomic:executor")
    else:
        invoke_lineno: int | None = None
        capture_linenos: list[int] = []
        await_linenos: list[int] = []
        for node in ast.walk(executor):
            if isinstance(node, ast.Call):
                func = node.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else ""
                )
                if called == "_capture_verified_implementation":
                    capture_linenos.append(node.lineno)
                elif called == "verified_implementation":
                    invoke_lineno = node.lineno
            elif isinstance(node, ast.Await):
                await_linenos.append(node.lineno)
        if invoke_lineno is None:
            violations.append("canonical_executable_binding_not_atomic:invoke")
        elif not capture_linenos:
            violations.append("canonical_executable_binding_not_atomic:capture")
        else:
            prior_awaits = [n for n in await_linenos if n < invoke_lineno]
            prior_captures = [n for n in capture_linenos if n < invoke_lineno]
            if prior_awaits and max(prior_captures) < max(prior_awaits):
                violations.append("canonical_executable_binding_not_atomic:order")

    details["corrective_viii_sensors"] = sorted(
        [
            "canonical_authoritative_snapshot_not_isolated",
            "canonical_authoritative_snapshot_unverifiable",
            "canonical_adjunct_channel_not_governed",
            "canonical_executable_binding_not_atomic",
            "canonical_executable_check_use_diverged",
        ]
    )


def _validate_corrective_ix_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-IX authority: mutable-alias class closure.

    IX-A law: authoritative state S and projection-visible state P must never
    share mutable storage that can change a later canonical consequence::

        MUTABLE_REACHABLE_GRAPH(P) ∩ AUTHORITATIVE_MATERIALIZATION_GRAPH(S) = ∅

    Static defense-in-depth (behavioral consequence proof is the load-bearing
    leg; this sensor makes the alias shape merge-blocking):

    1. Authoritative field census: the registry in
       ``app.finance_reconciliation.authoritative_fields`` must exactly cover
       the ``FinalCanonicalOutput`` dataclass. A new authoritative field
       without a registry declaration (sovereign source, snapshot point,
       allowed type family, projection representation, alias policy,
       externalization policy) is RED.
    2. Immutable snapshot construction: every ``_s_*`` snapshot assignment
       must normalize through an immutable boundary (``freeze_*`` / ``tuple``
       / ``str`` / ``int`` / ``Decimal`` / ``bool``); direct mutable
       constructors (``list(`` / ``dict(`` / ``set(`` / ``bytearray(``) or
       collection literals for snapshot locals are RED.
    3. Projection view independence: the mutable-risk scope field handed to
       ``AdjunctContext`` must be an immutable copy construction
       (``freeze_platform_scope(_s_*)`` or ``tuple(_s_*)``), never a bare
       ``_s_*`` alias that could share mutable backing storage.
    4. Runtime tripwire presence: the pre/post-projection snapshot digest
       comparison plus the snapshot type invariant must be present in
       ``execute_governed_sink``. Removing the tripwire while keeping names
       is RED.
    """
    sys.path.insert(0, str(BACKEND))
    sink_path = REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
    try:
        sink_source = sink_path.read_text(encoding="utf-8")
        sink_tree = ast.parse(sink_source)
    except (OSError, SyntaxError) as exc:
        violations.append(f"corrective_ix_sink_source_unreadable:{exc}")
        return

    # 1. Field census: registry exactly covers the canonical output type.
    try:
        from app.finance_reconciliation.authoritative_fields import (  # noqa: PLC0415
            AUTHORITATIVE_FIELD_REGISTRY,
            assert_registry_covers_output,
        )
        from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
            FinalCanonicalOutput,
        )

        try:
            assert_registry_covers_output(FinalCanonicalOutput)
        except ValueError as exc:
            violations.append(f"canonical_authoritative_census_incomplete:{exc}")
        else:
            import dataclasses as _dataclasses  # noqa: PLC0415

            declared = {
                field.name for field in _dataclasses.fields(FinalCanonicalOutput)
            }
            if set(AUTHORITATIVE_FIELD_REGISTRY) != declared:
                violations.append(
                    "canonical_authoritative_census_incomplete:registry_drift"
                )
            for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items():
                for required in (
                    "sovereign_source",
                    "snapshot_point",
                    "allowed_type_family",
                    "projection_representation",
                    "alias_policy",
                    "externalization_policy",
                ):
                    if not getattr(spec, required, ""):
                        violations.append(
                            "canonical_authoritative_census_incomplete:"
                            f"{name}:{required}"
                        )
                        break
            details["corrective_ix_census_fields"] = sorted(declared)
            details["corrective_ix_authoritative_fields"] = sorted(
                name
                for name, spec in AUTHORITATIVE_FIELD_REGISTRY.items()
                if spec.authoritative
            )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_authoritative_census_unverifiable:{exc}")

    # 2. Snapshot construction must be immutable-normalizing.
    executor = next(
        (
            node
            for node in ast.walk(sink_tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "execute_governed_sink"
        ),
        None,
    )
    if executor is None:
        violations.append("canonical_authoritative_snapshot_not_immutable:executor")
    else:
        snapshot_assigns: dict[str, ast.AST] = {}
        for node in ast.walk(executor):
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id.startswith("_s_"):
                        snapshot_assigns[target.id] = node.value
        if "_s_supported_platforms" not in snapshot_assigns:
            violations.append(
                "canonical_authoritative_snapshot_not_immutable:missing_platforms"
            )
        else:
            rhs = snapshot_assigns["_s_supported_platforms"]
            # Direct mutable constructors or literals for the snapshot are RED.
            if isinstance(rhs, (ast.List, ast.Dict, ast.Set)):
                violations.append(
                    "canonical_authoritative_snapshot_not_immutable:"
                    "supported_platforms_literal"
                )
            elif isinstance(rhs, ast.Call):
                func = rhs.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else ""
                )
                if called in {"list", "dict", "set", "bytearray"}:
                    violations.append(
                        "canonical_authoritative_snapshot_not_immutable:"
                        f"supported_platforms_{called}"
                    )
                elif called not in {
                    "tuple",
                    "freeze_platform_scope",
                    "frozenset",
                }:
                    # Unknown constructor for the mutable-risk field: fail
                    # closed so a new aliasing shape must be declared first.
                    violations.append(
                        "canonical_authoritative_snapshot_not_immutable:"
                        f"supported_platforms_{called}"
                    )
            else:
                violations.append(
                    "canonical_authoritative_snapshot_not_immutable:"
                    "supported_platforms_shape"
                )
        # Any snapshot assignment calling a mutable constructor is RED,
        # regardless of field (sibling-surface sweep).
        for name, rhs in snapshot_assigns.items():
            if isinstance(rhs, ast.Call):
                func = rhs.func
                called = (
                    func.id
                    if isinstance(func, ast.Name)
                    else func.attr if isinstance(func, ast.Attribute) else ""
                )
                if called in {"list", "dict", "set", "bytearray"}:
                    violations.append(
                        f"canonical_authoritative_snapshot_not_immutable:{name}"
                    )

    # 3. Projection view independence for the mutable-risk scope field.
    found_view = False
    for node in ast.walk(sink_tree):
        if not isinstance(node, ast.Call):
            continue
        func = node.func
        called = (
            func.id
            if isinstance(func, ast.Name)
            else func.attr if isinstance(func, ast.Attribute) else ""
        )
        if called != "AdjunctContext":
            continue
        found_view = True
        for keyword in node.keywords:
            if keyword.arg != "supported_platforms":
                continue
            value = keyword.value
            if isinstance(value, ast.Name) and value.id.startswith("_s_"):
                violations.append(
                    "canonical_projection_view_shares_mutable_storage:"
                    "supported_platforms_bare_alias"
                )
            elif isinstance(value, ast.Call):
                func2 = value.func
                called2 = (
                    func2.id
                    if isinstance(func2, ast.Name)
                    else func2.attr if isinstance(func2, ast.Attribute) else ""
                )
                if called2 not in {"tuple", "freeze_platform_scope", "frozenset"}:
                    violations.append(
                        "canonical_projection_view_shares_mutable_storage:"
                        f"supported_platforms_{called2}"
                    )
            else:
                violations.append(
                    "canonical_projection_view_shares_mutable_storage:"
                    "supported_platforms_shape"
                )
    if not found_view:
        violations.append("canonical_projection_view_shares_mutable_storage:view")

    # 4. Runtime tripwire presence (defense that converts alias to refusal).
    for token, rule in (
        ("freeze_platform_scope", "canonical_snapshot_alias_tripwire_missing:freeze"),
        (
            "assert_snapshot_types_immutable",
            "canonical_snapshot_alias_tripwire_missing:type_invariant",
        ),
        (
            "authoritative_snapshot_mutated_during_projection",
            "canonical_snapshot_alias_tripwire_missing:digest_tripwire",
        ),
        ("_s_pre_digest", "canonical_snapshot_alias_tripwire_missing:pre_digest"),
        ("_s_post_digest", "canonical_snapshot_alias_tripwire_missing:post_digest"),
    ):
        if token not in sink_source:
            violations.append(rule)

    details["corrective_ix_sensors"] = sorted(
        [
            "canonical_authoritative_census_incomplete",
            "canonical_authoritative_snapshot_not_immutable",
            "canonical_projection_view_shares_mutable_storage",
            "canonical_snapshot_alias_tripwire_missing",
        ]
    )


def _validate_corrective_x_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-X authority: closed external universe + lineage.

    Theorem X-A (CLOSED EXTERNAL FIELD UNIVERSE): actual emitted keys must
    equal the governed external keys -- not merely avoid three forbidden
    keys. The runtime leg (``validate_external_rendering`` inside the only
    approved renderer) refuses extra/missing/prohibited keys on the FINAL
    mapping regardless of construction primitive; this static leg pins the
    exact census merge-blocking and additionally requires the renderer to
    stay in statically provable form (no dynamic key mutation whose result
    a literal census cannot observe).

    Theorem X-B (EXTERNAL FIELD CAUSAL ORIGIN): every emitted value must
    name its declared ``FinalCanonicalOutput`` source attribute and no
    caller/projection/detached/adjacent-domain state.

    Theorem X-C (NO DETACHED AUTHORITY PROMOTION): no function outside the
    governed externalization boundary may return canonical-looking B2.6
    authority, independently of annotations, parameter/function names,
    DTO class, dict-vs-dataclass form, or construction syntax. The sensor
    keys on the behavioral structure (canonical authority marker +
    financial semantics in a returned mapping, or canonical-type
    serialization promotion), never on a type annotation or a name.
    """
    sys.path.insert(0, str(BACKEND))
    sink_path = REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
    try:
        from app.finance_reconciliation.authoritative_fields import (  # noqa: PLC0415
            EXTERNAL_FIELD_RENDER_ATTRS,
            EXTERNAL_FIELD_SOURCES,
            GOVERNED_EXTERNAL_KEYS,
            PROHIBITED_EXTERNAL_KEYS,
            REQUIRED_EXTERNAL_KEYS,
            assert_external_keys_derive_from_registry,
            authoritative_field_names,
            governed_external_keys,
            validate_external_rendering,
        )
        from app.finance_reconciliation.external_semantics import (  # noqa: PLC0415
            EXTERNAL_SEMANTICS,
        )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_x_external_contract_unresolvable:{exc}")
        return

    # 0. Single-source unity: the external universe must be a mechanical
    # registry projection; every authoritative field must externalize
    # (no silent internal-only authoritative drift); the source map must
    # cover every governed key with non-empty obligations.
    try:
        assert_external_keys_derive_from_registry()
    except ValueError as exc:
        violations.append(f"canonical_external_registry_drift:{exc}")
    try:
        if set(authoritative_field_names()) != set(governed_external_keys()):
            violations.append(
                "canonical_external_registry_drift:authoritative_not_external"
            )
        if set(REQUIRED_EXTERNAL_KEYS) != set(GOVERNED_EXTERNAL_KEYS):
            violations.append(
                "canonical_external_registry_drift:required_not_governed"
            )
        for key in GOVERNED_EXTERNAL_KEYS:
            if key in PROHIBITED_EXTERNAL_KEYS:
                violations.append(
                    f"canonical_external_registry_drift:governed_prohibited:{key}"
                )
        for key, spec in EXTERNAL_FIELD_SOURCES.items():
            for required in (
                "canonical_source",
                "transform",
                "authority_class",
                "render_attr",
            ):
                if not spec.get(required, ""):
                    violations.append(
                        "canonical_external_lineage_obligation_missing:"
                        f"{key}:{required}"
                    )
                    break
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_registry_unverifiable:{exc}")

    # The proof-oracle pin: the exact governed census. This pin lives in
    # the proof plane as the oracle against which the mechanical
    # derivation is checked; changing external semantics requires changing
    # the registry row AND this pin together (a governed contract change),
    # never a renderer-only edit.
    expected_external_keys = frozenset(
        {
            "authority",
            "sink_id",
            "contract_version",
            "tenant_id_hash",
            "currency_code",
            "window_start",
            "window_end",
            "supported_platforms",
            "matched_minor",
            "connected_minor",
            "coverage_percent",
            "zero_denominator",
            "provenance_mode",
            "sovereign_producer",
        }
    )
    if set(GOVERNED_EXTERNAL_KEYS) != set(expected_external_keys):
        violations.append("canonical_external_census_pin_mismatch")

    # Runtime leg liveness: the validator executes the refusal itself so a
    # green validator implies red forgeries (never a dead import).
    try:
        validate_external_rendering(dict.fromkeys(expected_external_keys, 1))
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_runtime_leg_dead:lawful:{exc}")
    else:
        for probe, probe_id in (
            (dict.fromkeys([*expected_external_keys, "verified_revenue_minor"], 1), "extra"),
            ({k: 1 for k in expected_external_keys if k != "matched_minor"}, "missing"),
            ({**dict.fromkeys(expected_external_keys, 1), "tenant_id": "raw"}, "prohibited"),
        ):
            try:
                validate_external_rendering(probe)
            except ValueError:
                pass
            else:
                violations.append(
                    f"canonical_external_runtime_leg_dead:{probe_id}"
                )
    try:
        sink_source = sink_path.read_text(encoding="utf-8")
        sink_tree = ast.parse(sink_source)
    except (OSError, SyntaxError) as exc:
        violations.append(f"corrective_x_sink_source_unreadable:{exc}")
        return

    # 1-3. Approved-renderer census + provability + value lineage. Since
    # Corrective XI the renderer derives every value through the frozen
    # transform contract and returns a sealed capability: the census pins
    # the contract-derived universe (checked in XI-2 above) and this leg
    # pins the renderer's structural provability -- no hand-written
    # external mapping may reappear at the renderer layer.
    renderer = next(
        (
            node
            for node in ast.walk(sink_tree)
            if isinstance(node, ast.AsyncFunctionDef)
            and node.name == "render_governed_external"
        ),
        None,
    )
    if renderer is None:
        violations.append("canonical_execution_bound_renderer_missing")
    else:
        # A hand-written external mapping (Dict literal, dict() call,
        # comprehension, or dynamic mutation) escapes the contract census,
        # so the frozen renderer must stay in statically provable form:
        # execution plus sealed issuance, nothing else.
        for node in ast.walk(renderer):
            if isinstance(node, ast.Dict):
                violations.append(
                    "canonical_external_key_closure_not_statically_provable:"
                    "renderer_dict_literal"
                )
            elif isinstance(node, ast.DictComp):
                violations.append(
                    "canonical_external_key_closure_not_statically_provable:"
                    "renderer_dict_comp"
                )
            elif (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "dict"
            ):
                violations.append(
                    "canonical_external_key_closure_not_statically_provable:"
                    "renderer_dict_call"
                )
        # The emitted universe is the contract projection: pin it against
        # the governed keys right here as well (census unity).
        if set(EXTERNAL_SEMANTICS) != set(GOVERNED_EXTERNAL_KEYS):
            violations.append(
                "canonical_external_undeclared_key:"
                f"contract={sorted(EXTERNAL_SEMANTICS)}"
            )

    details["corrective_x_governed_external_keys"] = sorted(GOVERNED_EXTERNAL_KEYS)
    details["corrective_x_sensors"] = sorted(
        [
            "canonical_external_registry_drift",
            "canonical_external_census_pin_mismatch",
            "canonical_external_undeclared_key",
            "canonical_external_required_key_missing",
            "canonical_external_prohibited_key",
            "canonical_external_value_source_not_sovereign",
            "canonical_external_key_closure_not_statically_provable",
            "canonical_detached_authority_emission",
            "canonical_serialization_promotion",
        ]
    )


_CANONICAL_AUTHORITY_MARKER = "canonical_B2.6_financial_truth"
_X_FINANCE_KEY_HINTS = frozenset(
    {
        "sink_id",
        "contract_version",
        "tenant_id_hash",
        "currency_code",
        "window_start",
        "window_end",
        "supported_platforms",
        "matched_minor",
        "connected_minor",
        "coverage_percent",
        "zero_denominator",
        "provenance_mode",
        "sovereign_producer",
    }
)
_X_FINANCE_AFFIX_HINTS = ("_minor", "_revenue", "_amount", "revenue", "coverage")


def _x_dict_has_canonical_claim(
    dict_node: ast.Dict,
) -> tuple[bool, bool]:
    """Report (authority_marker, finance_hint) for a returned mapping.

    The authority marker is recognized by VALUE semantics -- the literal
    canonical label, the framework constant, or a carried ``.authority``
    attribute -- never by parameter names or type annotations. Finance
    hints recognize governed keys and finance affixes.
    """
    marker = False
    literal_marker = False
    finance = False
    for key_node, value_node in zip(dict_node.keys, dict_node.values):
        if not (isinstance(key_node, ast.Constant) and isinstance(key_node.value, str)):
            continue
        key = key_node.value
        if key in _X_FINANCE_KEY_HINTS or key.endswith(_X_FINANCE_AFFIX_HINTS) or key.startswith(
            ("verified_", "settled_", "reconciled_", "attributed_", "canonical_")
        ):
            finance = True
        if key != "authority":
            continue
        if isinstance(value_node, ast.Constant) and isinstance(value_node.value, str):
            if _CANONICAL_AUTHORITY_MARKER in value_node.value:
                marker = True
                literal_marker = True
        elif isinstance(value_node, ast.Name):
            if value_node.id in {
                "CANONICAL_OUTPUT_AUTHORITY",
                "authority",
                "canonical_authority",
            }:
                marker = True
        elif isinstance(value_node, ast.Attribute):
            if value_node.attr in {"CANONICAL_OUTPUT_AUTHORITY", "authority"}:
                marker = True
        elif isinstance(value_node, ast.Call):
            # Laundered label: kwargs.get("authority", <canonical marker>)
            # or dict(...)/Mapping constructions carrying the marker.
            for child in ast.walk(value_node):
                if (
                    isinstance(child, ast.Constant)
                    and isinstance(child.value, str)
                    and _CANONICAL_AUTHORITY_MARKER in child.value
                ):
                    marker = True
                    literal_marker = True
                    break
                if isinstance(child, ast.Name) and child.id in {
                    "CANONICAL_OUTPUT_AUTHORITY",
                }:
                    marker = True
                    break
    return marker, (literal_marker or finance)


_X_SERIALIZER_CALLS = frozenset(
    {"asdict", "model_dump", "model_dump_json", "jsonable_encoder", "vars"}
)


def _x_is_serializer_call(called: str) -> bool:
    """Recognize generic serializers independently of import aliasing."""
    if called in _X_SERIALIZER_CALLS:
        return True
    # Aliased imports (``asdict as _nc_asdict``) keep the capability name
    # as a suffix; a bare unrelated name never matches this shape.
    return any(
        called == name or called.endswith(f"_{name}") or called.endswith(f".{name}")
        for name in _X_SERIALIZER_CALLS
    )


def _x_function_references_canonical(func: ast.AST) -> bool:
    for child in ast.walk(func):
        if isinstance(child, ast.Name) and child.id in {
            "FinalCanonicalOutput",
            "CANONICAL_OUTPUT_AUTHORITY",
        }:
            return True
        if isinstance(child, ast.Attribute) and child.attr in {
            "FinalCanonicalOutput",
            "CANONICAL_OUTPUT_AUTHORITY",
        }:
            return True
        if (
            isinstance(child, ast.Constant)
            and isinstance(child.value, str)
            and _CANONICAL_AUTHORITY_MARKER in child.value
        ):
            return True
    return False


def _validate_corrective_x_detached_sensors(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Repo-wide annotation-independent detached-promotion sensors."""
    app_root = BACKEND / "app"
    scanned_functions = 0
    for path in sorted(app_root.rglob("*.py")):
        try:
            source = path.read_text(encoding="utf-8")
            tree = ast.parse(source, filename=str(path))
        except (OSError, SyntaxError):
            continue
        rel = path.relative_to(REPO_ROOT).as_posix()
        for node in ast.walk(tree):
            if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
                continue
            scanned_functions += 1
            approved = (
                rel == "backend/app/finance_reconciliation/canonical_sink.py"
                and node.name in {"render_governed_external", "execute_governed_sink"}
            )
            if approved:
                continue
            for child in ast.walk(node):
                if not isinstance(child, ast.Return) or not isinstance(
                    child.value, ast.Dict
                ):
                    continue
                marker, finance = _x_dict_has_canonical_claim(child.value)
                if marker and finance:
                    violations.append(
                        "canonical_detached_authority_emission:"
                        f"{rel}:{node.name}"
                    )
                    break
            else:
                # Serialization promotion: a canonical-referencing function
                # that returns a generic serialization of a value it was
                # given can launder a detached object into canonical-looking
                # external form without a Dict literal. Serialization itself
                # is lawful everywhere; the canonical reference is the
                # authority claim that makes neutral emission RED.
                if _x_function_references_canonical(node):
                    for child in ast.walk(node):
                        if not isinstance(child, ast.Return):
                            continue
                        value = child.value
                        if isinstance(value, ast.Call) and isinstance(
                            value.func, (ast.Name, ast.Attribute)
                        ):
                            called = (
                                value.func.id
                                if isinstance(value.func, ast.Name)
                                else value.func.attr
                            )
                            if _x_is_serializer_call(called):
                                violations.append(
                                    "canonical_serialization_promotion:"
                                    f"{rel}:{node.name}"
                                )
                                break
                        elif isinstance(value, ast.Attribute) and value.attr in {
                            "__dict__",
                        }:
                            violations.append(
                                "canonical_serialization_promotion:"
                                f"{rel}:{node.name}"
                            )
                            break
    details["corrective_x_functions_scanned"] = scanned_functions


# ---------------------------------------------------------------------------
# Corrective XI — executable external semantic contract + governed canonical
# egress capability. Independent pins (value-blind, hard-coded HERE in the
# proof plane): the lawful external mapping, per-key source/transform data,
# transform execution vectors, refusal vectors, renderer/issuer structure,
# capability census, egress registry census, and admission liveness.
# ---------------------------------------------------------------------------

_XI_EXPECTED_SOURCE_ATTRS = {
    "authority": "authority",
    "sink_id": "sink_id",
    "contract_version": "contract_version",
    "tenant_id_hash": "tenant_id_hash",
    "currency_code": "currency_code",
    "window_start": "window_start",
    "window_end": "window_end",
    "supported_platforms": "supported_platforms",
    "matched_minor": "matched_minor",
    "connected_minor": "connected_minor",
    "coverage_percent": "coverage_percent",
    "zero_denominator": "zero_denominator",
    "provenance_mode": "provenance_mode",
    "sovereign_producer": "sovereign_producer",
}

_XI_EXPECTED_TRANSFORM_IDS = {
    "authority": "governed_label_identity",
    "sink_id": "str_identity",
    "contract_version": "str_identity",
    "tenant_id_hash": "one_way_hash_identity",
    "currency_code": "str_identity",
    "window_start": "instant_iso8601",
    "window_end": "instant_iso8601",
    "supported_platforms": "frozen_tuple_exact_materialization",
    "matched_minor": "integer_minor_identity",
    "connected_minor": "integer_minor_identity",
    "coverage_percent": "decimal_2dp_exact_string",
    "zero_denominator": "bool_identity",
    "provenance_mode": "governed_label_identity",
    "sovereign_producer": "governed_label_identity",
}

_XI_EXPECTED_EGRESS_SURFACES = {"render_governed_external"}

# The proof plane's own statement of the lawful external representation:
# every value is hard-coded evidence data, never derived from the modules it
# adjudicates (value-blind: a wrong source that happens to carry an equal
# value cannot pass a source-identity pin that compares data, not values).
_XI_LAWFUL_FIELDS = {
    "authority": "canonical_B2.6_financial_truth",
    "sink_id": "future_finance_projection",
    "contract_version": "b2.6-p1-semantic-authority-v6",
    "tenant_id_hash": "sha256:" + "ab" * 32,
    "currency_code": "USD",
    "window_start": "2026-01-01T00:00:00+00:00",
    "window_end": "2026-02-01T12:30:05+02:00",
    "supported_platforms": ["paypal", "stripe"],
    "matched_minor": 76000,
    "connected_minor": 80000,
    "coverage_percent": "95.00",
    "zero_denominator": False,
    "provenance_mode": "RE_DERIVE_ON_READ",
    "sovereign_producer": (
        "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute"
    ),
}

# Per-field semantic corruptions: every member is a real representative of
# class XI-A (meaning drift) that the executable law must refuse.
_XI_FIELD_CORRUPTIONS = (
    ("window_start", "2026-01-01"),
    ("window_start", "2026-01-01T00:00:00"),
    ("window_end", "2026-02-01"),
    ("matched_minor", "76000"),
    ("matched_minor", 76000.0),
    ("matched_minor", -76000),
    ("matched_minor", True),
    ("connected_minor", True),
    ("coverage_percent", "9.500"),
    ("coverage_percent", "95.0"),
    ("coverage_percent", 95.00),
    ("supported_platforms", ("paypal", "stripe")),
    ("supported_platforms", ["paypal", 1]),
    ("supported_platforms", "paypal"),
    ("tenant_id_hash", "ab" * 31),
    ("tenant_id_hash", "ab" * 32),
    ("tenant_id_hash", ("sha256:" + "ab" * 32).upper()),
    ("currency_code", "usd"),
    ("authority", "canonical_B2.6_financial_truth "),
    ("zero_denominator", 0),
    ("zero_denominator", "false"),
    ("provenance_mode", "DURABLE_SOURCE_BINDING"),
    ("sovereign_producer", "app.services.revenue_reconciliation"),
    ("contract_version", "b2.6-p1-semantic-authority-v5"),
    ("sink_id", ""),
)


def _validate_corrective_xi_authority(
    violations: list[str], details: dict[str, Any]
) -> None:
    """Executable Corrective-XI authority: frozen transforms + sealed egress.

    Theorem XI-A (GOVERNED EXTERNAL TRANSFORM): every external value equals
    the execution of its frozen transform over its declared sovereign source
    attribute -- pinned here four independent ways: (1) the semantic
    contract pins the transform module's AST identity (re-verified at
    canonical-sink import, fail-closed in any image); (2) the validator's
    own value-blind key->source/transform data pins lineage without reading
    the module's maps; (3) hard-coded execution vectors and refusal vectors
    exercise every transform; (4) the renderer contains no per-field
    expressions at all (structural law).

    Theorem XI-B (GOVERNED CANONICAL EGRESS CAPABILITY): canonical external
    authority is an exact-type sealed capability issued only inside the
    governed egress module; admission accepts only that type; the egress
    surfaces form a registered closed set census-pinned here; and forging
    the capability anywhere else in backend/app is merge-blocking.
    """
    sys.path.insert(0, str(BACKEND))
    sink_path = REPO_ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
    semantics_path = (
        REPO_ROOT / "backend/app/finance_reconciliation/external_semantics.py"
    )
    try:
        from app.finance_reconciliation.external_semantics import (  # noqa: PLC0415
            EXTERNAL_SEMANTICS,
            ExternalSemanticsError,
            external_semantics_ast_sha256,
            project_external_fields,
        )
        from app.finance_reconciliation.semantic_contract import (  # noqa: PLC0415
            load_b26_p1_semantic_contract,
        )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_xi_contract_unresolvable:{exc}")
        return

    # XI-1: the frozen contract pins the transform module's AST identity.
    try:
        document = load_b26_p1_semantic_contract()
        section = document["external_semantics_authority"]
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_xi_contract_unresolvable:{exc}")
        return
    live_ast = external_semantics_ast_sha256()
    if live_ast != section.get("ast_sha256"):
        violations.append("canonical_external_semantics_not_pinned")
    if set(section.get("governed_external_keys", [])) != set(EXTERNAL_SEMANTICS):
        violations.append("canonical_external_semantics_census_drift")

    # XI-2: value-blind lineage pin (independent of module maps).
    for key, expected_attr in _XI_EXPECTED_SOURCE_ATTRS.items():
        spec = EXTERNAL_SEMANTICS.get(key)
        if spec is None or spec.source_attr != expected_attr:
            violations.append(
                f"canonical_external_value_source_not_sovereign:{key}"
            )
    for key, expected_id in _XI_EXPECTED_TRANSFORM_IDS.items():
        spec = EXTERNAL_SEMANTICS.get(key)
        if spec is None or spec.transform_id != expected_id:
            violations.append(
                f"canonical_external_transform_id_not_governed:{key}"
            )
    try:
        from app.finance_reconciliation.authoritative_fields import (  # noqa: PLC0415
            EXTERNAL_FIELD_RENDER_ATTRS,
        )

        for key, expected_attr in _XI_EXPECTED_SOURCE_ATTRS.items():
            if EXTERNAL_FIELD_RENDER_ATTRS.get(key) != expected_attr:
                violations.append(
                    "canonical_external_value_source_not_sovereign:"
                    f"lineage_map:{key}"
                )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"corrective_xi_lineage_map_unresolvable:{exc}")

    # XI-3: the governed egress module loads only under the frozen pin.
    try:
        from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
            GOVERNED_EGRESS_SURFACES,
            _EGRESS_ISSUANCE,
            _issue_canonical_external,
            admit_canonical_external,
            assert_canonical_external_semantics,
            render_governed_external,
            verify_external_semantics_contract_pin,
        )
        from app.finance_reconciliation.canonical_sink import (  # noqa: PLC0415
            CanonicalExternalTruth,
        )
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_egress_module_refused_load:{exc}")
        return

    # XI-4: executable law on the complete lawful mapping (liveness), then
    # every class-XI-A corruption must refuse (RED-capable checker).
    try:
        assert_canonical_external_semantics(_XI_LAWFUL_FIELDS)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_semantic_law_dead:lawful:{exc}")
    for key, bad in _XI_FIELD_CORRUPTIONS:
        probe = dict(_XI_LAWFUL_FIELDS)
        probe[key] = bad
        try:
            assert_canonical_external_semantics(probe)
        except ValueError:
            pass
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append(
                f"canonical_external_semantic_law_dead:corruption:{key}"
            )

    # XI-5: projection equivalence -- the renderer's serializer produces
    # exactly the pinned lawful mapping from the sovereign source shapes.
    from datetime import timedelta, timezone as _tz  # noqa: PLC0415
    from types import SimpleNamespace  # noqa: PLC0415

    sovereign_shaped = SimpleNamespace(
        authority="canonical_B2.6_financial_truth",
        sink_id="future_finance_projection",
        contract_version="b2.6-p1-semantic-authority-v6",
        tenant_id_hash="sha256:" + "ab" * 32,
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=_tz.utc),
        window_end=datetime(2026, 2, 1, 12, 30, 5, tzinfo=_tz(timedelta(hours=2))),
        supported_platforms=("paypal", "stripe"),
        matched_minor=76000,
        connected_minor=80000,
        coverage_percent=Decimal("95.00"),
        zero_denominator=False,
        provenance_mode="RE_DERIVE_ON_READ",
        sovereign_producer=_XI_LAWFUL_FIELDS["sovereign_producer"],
    )
    try:
        projected = project_external_fields(sovereign_shaped)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_projection_failed:{exc}")
    else:
        if projected != _XI_LAWFUL_FIELDS:
            violations.append("canonical_external_projection_not_equivalent")
    # Transform refusal vectors (fail-closed family law).
    refusal_vectors = (
        ("window_start", datetime(2026, 1, 1)),
        ("window_end", "2026-02-01"),
        ("matched_minor", True),
        ("matched_minor", -5),
        ("matched_minor", 76000.0),
        ("connected_minor", "80000"),
        ("coverage_percent", Decimal("95.005")),
        ("coverage_percent", "95.00"),
        ("supported_platforms", ["paypal", "stripe"]),
        ("supported_platforms", "paypal"),
        ("zero_denominator", 1),
        ("authority", ""),
        ("sink_id", None),
    )
    for key, source in refusal_vectors:
        try:
            EXTERNAL_SEMANTICS[key].transform(source)
        except ExternalSemanticsError:
            pass
        except Exception:  # noqa: BLE001
            pass
        else:
            violations.append(f"canonical_external_transform_refusal_dead:{key}")

    # XI-6: renderer and issuer structure -- no per-field transform surface.
    try:
        sink_source = sink_path.read_text(encoding="utf-8")
        sink_tree = ast.parse(sink_source)
    except (OSError, SyntaxError) as exc:
        violations.append(f"corrective_xi_sink_source_unreadable:{exc}")
        sink_tree = None
    if sink_tree is not None:
        renderer = next(
            (
                node
                for node in ast.walk(sink_tree)
                if isinstance(node, ast.AsyncFunctionDef)
                and node.name == "render_governed_external"
            ),
            None,
        )
        issuer = next(
            (
                node
                for node in ast.walk(sink_tree)
                if isinstance(node, ast.FunctionDef)
                and node.name == "_issue_canonical_external"
            ),
            None,
        )
        if renderer is None or issuer is None:
            violations.append("canonical_execution_bound_renderer_missing")
        else:
            for scope_name, scope in (("renderer", renderer), ("issuer", issuer)):
                for node in ast.walk(scope):
                    if isinstance(node, ast.Dict):
                        violations.append(
                            "canonical_renderer_bypasses_transform_contract:"
                            f"{scope_name}:dict_literal"
                        )
                    if isinstance(node, ast.DictComp):
                        violations.append(
                            "canonical_renderer_bypasses_transform_contract:"
                            f"{scope_name}:dict_comp"
                        )
                    if (
                        isinstance(node, ast.Call)
                        and isinstance(node.func, ast.Name)
                        and node.func.id == "dict"
                    ):
                        violations.append(
                            "canonical_renderer_bypasses_transform_contract:"
                            f"{scope_name}:dict_call"
                        )
            # Renderer: exactly one return, and it is the sealed issuance.
            renderer_segment = ast.get_source_segment(sink_source, renderer)
            if renderer_segment is None or "await execute_governed_sink(" not in renderer_segment:
                violations.append("canonical_external_renderer_not_execution_bound")
            returns = [
                node.value
                for node in ast.walk(renderer)
                if isinstance(node, ast.Return) and node.value is not None
            ]
            if len(returns) != 1 or not (
                isinstance(returns[0], ast.Call)
                and isinstance(returns[0].func, ast.Name)
                and returns[0].func.id == "_issue_canonical_external"
            ):
                violations.append(
                    "canonical_external_key_closure_not_statically_provable:"
                    "renderer_return_not_issuance"
                )
            # Renderer never touches per-field output attributes.
            for node in ast.walk(renderer):
                if (
                    isinstance(node, ast.Attribute)
                    and isinstance(node.value, ast.Name)
                    and node.value.id == "output"
                ):
                    violations.append(
                        "canonical_renderer_bypasses_transform_contract:"
                        "output_attribute_access"
                    )
            # Issuer: fields from the contract projection, sealed issuance
            # of exactly those fields, nothing else.
            issuer_text = ast.get_source_segment(sink_source, issuer) or ""
            if "project_external_fields(" not in issuer_text:
                violations.append(
                    "canonical_renderer_bypasses_transform_contract:"
                    "issuer_not_contract_projection"
                )
            if "CanonicalExternalTruth(fields, _EGRESS_ISSUANCE)" not in issuer_text:
                violations.append(
                    "canonical_external_key_closure_not_statically_provable:"
                    "issuer_not_sealed_issuance"
                )
            for node in ast.walk(issuer):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
                    if node.func.id not in {
                        "project_external_fields",
                        "CanonicalExternalTruth",
                    }:
                        violations.append(
                            "canonical_external_key_closure_not_statically_provable:"
                            f"issuer_call:{node.func.id}"
                        )

    # XI-7: capability census -- nobody outside the governed egress module
    # may construct, subclass, or reference the capability or its issuance.
    app_root = BACKEND / "app"
    governed_rel = "backend/app/finance_reconciliation/canonical_sink.py"
    for path in sorted(app_root.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel == governed_rel:
            continue
        try:
            tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        except (OSError, SyntaxError):
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Name) and node.id in {
                "CanonicalExternalTruth",
                "_EGRESS_ISSUANCE",
                "_issue_canonical_external",
            }:
                violations.append(f"canonical_egress_capability_forged:{rel}:{node.id}")
            if isinstance(node, ast.Attribute) and node.attr in {
                "CanonicalExternalTruth",
                "_EGRESS_ISSUANCE",
                "_issue_canonical_external",
            }:
                violations.append(f"canonical_egress_capability_forged:{rel}:{node.attr}")
            # Aliased imports (``from ...canonical_sink import
            # CanonicalExternalTruth as _C``) bind the capability without
            # ever naming it: governing the ImportFrom binding itself is
            # spelling-independent (any use requires the import).
            if isinstance(node, ast.ImportFrom) and (node.module or "").endswith(
                "finance_reconciliation.canonical_sink"
            ):
                for alias in node.names:
                    if alias.name in {
                        "CanonicalExternalTruth",
                        "_EGRESS_ISSUANCE",
                        "_issue_canonical_external",
                    }:
                        violations.append(
                            "canonical_egress_capability_forged:"
                            f"{rel}:import:{alias.name}"
                        )
            # Attribute-name assembly with constants (``getattr(sink,
            # "_EGRESS_ISSUANCE")``) binds the capability without an
            # import statement; govern the constant too.
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Name)
                and node.func.id == "getattr"
                and len(node.args) >= 2
                and isinstance(node.args[1], ast.Constant)
                and isinstance(node.args[1].value, str)
                and node.args[1].value in {
                    "CanonicalExternalTruth",
                    "_EGRESS_ISSUANCE",
                    "_issue_canonical_external",
                }
            ):
                violations.append(
                    "canonical_egress_capability_forged:"
                    f"{rel}:getattr:{node.args[1].value}"
                )

    # XI-8: egress registry census -- the closed set of canonical surfaces.
    if set(GOVERNED_EGRESS_SURFACES) != _XI_EXPECTED_EGRESS_SURFACES:
        violations.append("canonical_egress_registry_census_mismatch")
    else:
        surface = GOVERNED_EGRESS_SURFACES["render_governed_external"]
        if (
            surface.callable_path
            != "app.finance_reconciliation.canonical_sink.render_governed_external"
            or surface.serializer
            != "app.finance_reconciliation.external_semantics.project_external_fields"
            or surface.capability_type
            != "app.finance_reconciliation.canonical_sink.CanonicalExternalTruth"
            or surface.admission
            != "app.finance_reconciliation.canonical_sink.admit_canonical_external"
        ):
            violations.append("canonical_egress_registry_binding_drift")

    # XI-9: admission liveness -- lookalikes never acquire authority, the
    # sealed capability path works, and immutability holds.
    from types import MappingProxyType  # noqa: PLC0415

    lookalikes = (
        dict(_XI_LAWFUL_FIELDS),
        MappingProxyType(dict(_XI_LAWFUL_FIELDS)),
        type("Lookalike", (dict,), {})(dict(_XI_LAWFUL_FIELDS)),
    )
    for index, lookalike in enumerate(lookalikes):
        try:
            admit_canonical_external(lookalike)
        except ValueError:
            pass
        except Exception as exc:  # noqa: BLE001
            violations.append(
                f"canonical_external_admission_dead:lookalike:{index}:{exc}"
            )
        else:
            violations.append(
                f"canonical_external_admission_dead:lookalike:{index}"
            )
    try:
        forged_subclass = object.__new__(
            type("Forged", (CanonicalExternalTruth,), {})
        )
        admit_canonical_external(forged_subclass)
    except ValueError:
        pass
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_external_admission_dead:subclass:{exc}")
    else:
        violations.append("canonical_external_admission_dead:subclass_forgery")
    try:
        CanonicalExternalTruth(dict(_XI_LAWFUL_FIELDS), object())
    except ValueError:
        pass
    else:
        violations.append("canonical_egress_capability_proof_dead")
    try:
        capability = CanonicalExternalTruth(dict(_XI_LAWFUL_FIELDS), _EGRESS_ISSUANCE)
        assert admit_canonical_external(capability) is capability
        try:
            capability["matched_minor"] = 0
        except TypeError:
            pass
        else:
            violations.append("canonical_external_fields_mutable")
        try:
            capability._fields["matched_minor"] = 0  # noqa: SLF001
        except TypeError:
            pass
        else:
            violations.append("canonical_external_fields_mutable:storage")
        if capability.issued_by != "render_governed_external":
            violations.append("canonical_egress_surface_identity_drift")
    except Exception as exc:  # noqa: BLE001
        violations.append(f"canonical_egress_issuance_dead:{exc}")

    # The import-time pin must actually execute at egress load: a module
    # that skips verification ships unpinned semantics without ever
    # comparing them to the frozen contract.
    _sink_module = importlib.import_module(
        "app.finance_reconciliation.canonical_sink"
    )

    if getattr(_sink_module, "_XI_CONTRACT_PIN_AST_SHA256", None) != live_ast:
        violations.append("canonical_egress_contract_pin_not_executed")

    details["corrective_xi_transform_contract_ast_sha256"] = live_ast
    details["corrective_xi_governed_egress_surfaces"] = sorted(GOVERNED_EGRESS_SURFACES)
    details["corrective_xi_sensors"] = sorted(
        [
            "canonical_external_semantics_not_pinned",
            "canonical_external_semantics_census_drift",
            "canonical_external_value_source_not_sovereign",
            "canonical_external_transform_id_not_governed",
            "canonical_egress_module_refused_load",
            "canonical_external_semantic_law_dead",
            "canonical_external_projection_not_equivalent",
            "canonical_external_transform_refusal_dead",
            "canonical_renderer_bypasses_transform_contract",
            "canonical_external_key_closure_not_statically_provable",
            "canonical_egress_capability_forged",
            "canonical_egress_registry_census_mismatch",
            "canonical_egress_registry_binding_drift",
            "canonical_external_admission_dead",
            "canonical_egress_capability_proof_dead",
            "canonical_external_fields_mutable",
        ]
    )


def validate() -> tuple[list[str], dict[str, Any]]:
    violations: list[str] = []
    details: dict[str, Any] = {}
    _validate_contract_and_b23_binding(violations, details)
    _validate_corrective_v_authority(violations, details)
    _validate_corrective_vii_authority(violations, details)
    _validate_corrective_viii_authority(violations, details)
    _validate_corrective_ix_authority(violations, details)
    _validate_corrective_x_authority(violations, details)
    _validate_corrective_x_detached_sensors(violations, details)
    _validate_corrective_xi_authority(violations, details)
    enforce_machinery = not _successor_authorizes_machinery()
    _validate_b26_namespace(
        violations, details, enforce_product_machinery=enforce_machinery
    )
    _validate_repo_wide_false_authority(
        violations, details, enforce_product_machinery=enforce_machinery
    )
    _validate_governance(violations, details)
    dockerfile = PRODUCTION_DOCKERFILE.read_text(encoding="utf-8")
    if "COPY contracts/reconciliation /app/contracts/reconciliation" not in dockerfile:
        violations.append("b26_contract_not_shipped_in_production_image")
    return violations, details


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-dir", type=Path)
    args = parser.parse_args()
    violations, details = validate()
    if violations:
        print("B26_P1_AUTHORITY_FAIL")
        for violation in violations:
            print(violation)
        return 1
    if args.evidence_dir:
        from scripts.ci.b26_p1_evidence import write_evidence_cell  # noqa: PLC0415

        write_evidence_cell(
            args.evidence_dir / "semantic-authority.json",
            gate_id="B26-P1-G4-SEMANTIC-AUTHORITY",
            producer="b26-p1-static-authority",
            scenario_id="semantic-authority-pristine",
            falsifier_id="B26-P1-NC-01-through-04",
            details=details,
        )
        write_evidence_cell(
            args.evidence_dir / "execution-identity.json",
            gate_id="B26-P1-G8-EXECUTION-IDENTITY",
            producer="b26-p1-static-authority",
            scenario_id="governing-workflow-pristine",
            falsifier_id="B26-P1-NC-05",
            details={
                "workflow_events": details["workflow_events"],
                "aggregate_producers": details["aggregate_producers"],
                "governing_context": GOVERNING_CONTEXT,
                "diagnostic_context": DIAGNOSTIC_CONTEXT,
            },
        )
    print("B26_P1_AUTHORITY_PASS")
    print(json.dumps(details, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
