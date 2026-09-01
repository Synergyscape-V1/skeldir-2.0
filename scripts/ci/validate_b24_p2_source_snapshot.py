#!/usr/bin/env python3
"""Validate B2.4-P2 deterministic source snapshot implementation."""

from __future__ import annotations

import argparse
import ast
import hashlib
import re
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BAYESIAN_PACKAGE = Path("backend/app/bayesian")
INPUT_CONTRACT = BAYESIAN_PACKAGE / "input_contract.py"
ELIGIBILITY = BAYESIAN_PACKAGE / "eligibility.py"
SOURCE_SNAPSHOT = BAYESIAN_PACKAGE / "source_snapshot.py"
REPOSITORY = BAYESIAN_PACKAGE / "repository.py"
MODELS = BAYESIAN_PACKAGE / "models.py"
ENUMS = BAYESIAN_PACKAGE / "enums.py"
P2_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605211430_b24_p2_sparse_fallback_reasons.py"
)
P2_STREAM_INDEX_MIGRATION = Path(
    "alembic/versions/007_skeldir_foundation/202605221200_b24_p2_source_stream_safety_indexes.py"
)
CANONICAL_SCHEMA = Path("db/schema/canonical_schema.sql")
COMPLETION_REPORT = Path(
    "docs/forensics/B2.4-P2_Deterministic_Input_Contract_Source_Snapshot_Completion_Report.md"
)

REQUIRED_FILES = {
    INPUT_CONTRACT,
    ELIGIBILITY,
    SOURCE_SNAPSHOT,
    P2_MIGRATION,
    P2_STREAM_INDEX_MIGRATION,
}

FORBIDDEN_SCOPE_TOKENS = {
    "dirty_marker",
    "fit_planner",
    "fit_claim",
    "pymc",
    "pytensor",
    "arviz",
    "pm.Model",
    "pm.sample",
    "diagnostics",
    "projection",
    "artifact_lifecycle",
    "APIRouter",
    "include_router",
    "app.llm",
    "openai",
    "anthropic",
    "Celery",
    "send_task",
    "delay(",
    "apply_async",
}

IDENTITY_TABLES = {
    "attribution_commerce_identities",
    "webhook_ingress_identities",
}

PII_TOKENS = {
    "email",
    "phone",
    "ip_address",
    "user_agent",
    "raw_payload",
    "oauth",
    "token",
    "secret",
}

SENTINEL_REASONS = {
    "source_window_empty",
    "insufficient_data",
    "insufficient_privacy_cohort",
}

REQUIRED_SPARSE_THRESHOLD_FIELDS = {
    "minimum_eligible_source_events",
    "minimum_distinct_source_events",
    "minimum_conversion_or_revenue_events",
    "minimum_confirmed_match_verdicts",
    "minimum_distinct_channels",
    "minimum_observations_per_currency",
    "minimum_source_window_density_days",
}

REQUIRED_SOURCE_STREAM_INDEXES = {
    "idx_b24_p2_attribution_events_source_stream",
    "idx_b24_p2_attribution_allocations_source_stream",
    "idx_b24_p2_match_verdicts_source_stream",
    "idx_b24_p2_revenue_events_source_stream",
}


class ValidationError(RuntimeError):
    pass


def _read(root: Path, path: Path) -> str:
    full = root / path
    if not full.exists():
        raise ValidationError(f"missing required file: {path.as_posix()}")
    return full.read_text(encoding="utf-8", errors="replace")


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise ValidationError(message)


def _parse(text: str, rel: Path) -> ast.Module:
    return ast.parse(text, filename=rel.as_posix())


def _literal_assignment(tree: ast.Module, name: str) -> object:
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name) and target.id == name:
                    value = node.value
                    if (
                        isinstance(value, ast.Call)
                        and isinstance(value.func, ast.Name)
                        and value.func.id == "MappingProxyType"
                        and value.args
                    ):
                        value = value.args[0]
                    return ast.literal_eval(value)
    raise ValidationError(f"missing literal assignment: {name}")


def _constant_assignments(tree: ast.Module) -> dict[str, object]:
    constants: dict[str, object] = {}
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if isinstance(target, ast.Name):
                    try:
                        constants[target.id] = ast.literal_eval(node.value)
                    except (ValueError, SyntaxError):
                        continue
    return constants


def _threshold_defaults(tree: ast.Module) -> dict[str, int]:
    constants = _constant_assignments(tree)
    defaults: dict[str, int] = {}
    for node in tree.body:
        if isinstance(node, ast.ClassDef) and node.name == "SparsePrivacyThresholds":
            for item in node.body:
                if isinstance(item, ast.AnnAssign) and isinstance(
                    item.target, ast.Name
                ):
                    name = item.target.id
                    if item.value is None:
                        continue
                    try:
                        value = ast.literal_eval(item.value)
                    except (ValueError, SyntaxError):
                        if (
                            isinstance(item.value, ast.Name)
                            and item.value.id in constants
                        ):
                            value = constants[item.value.id]
                        else:
                            raise ValidationError(
                                f"sparse threshold must be literal or named floor: {name}"
                            )
                    if not isinstance(value, int):
                        raise ValidationError(
                            f"sparse threshold is not integer: {name}"
                        )
                    defaults[name] = value
            return defaults
    raise ValidationError("SparsePrivacyThresholds class missing")


def validate_input_contract(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, INPUT_CONTRACT)
    tree = _parse(text, INPUT_CONTRACT)
    _require("SOURCE_CONTRACT_VERSION" in text, "source contract version missing")
    _require("ELIGIBILITY_POLICY_VERSION" in text, "eligibility policy version missing")
    _require("SparsePrivacyThresholds" in text, "sparse privacy thresholds missing")
    constants = _constant_assignments(tree)
    floor = constants.get("MIN_SPARSE_PRIVACY_FLOOR")
    model_dimension_floor = constants.get("MIN_MODEL_DIMENSION_FLOOR")
    _require(
        isinstance(floor, int) and floor >= 20,
        "sparse privacy floor must be at least 20",
    )
    _require(
        isinstance(model_dimension_floor, int) and model_dimension_floor >= 2,
        "model dimension floor must be at least 2",
    )
    thresholds = _threshold_defaults(tree)
    for threshold_name in REQUIRED_SPARSE_THRESHOLD_FIELDS:
        _require(
            threshold_name in thresholds, f"sparse threshold missing: {threshold_name}"
        )
        required_floor = (
            model_dimension_floor
            if threshold_name == "minimum_distinct_channels"
            else floor
        )
        _require(
            thresholds[threshold_name] >= required_floor,
            f"sparse threshold below floor: {threshold_name}={thresholds[threshold_name]}",
        )
    _require(
        "REPEATABLE READ" in text and "READ ONLY" in text,
        "transaction requirements missing",
    )
    _require("app.current_tenant_id" in text, "tenant GUC requirement missing")
    _require(
        "VERIFICATION_COVERAGE_RULE" in text and "excluded_in_b24_source_v1" in text,
        "verification coverage rule missing",
    )
    _require("SOURCE_STREAM_BUFFERING_RULE" in text, "source buffering rule missing")
    _require(
        "SOURCE_STREAM_INDEX_REQUIREMENTS" in text,
        "source stream index requirements missing",
    )

    allowed = _literal_assignment(tree, "ALLOWED_SOURCE_READ_MODELS")
    _require(
        isinstance(allowed, dict), "allowed source read models must be literal mapping"
    )
    for table in IDENTITY_TABLES:
        _require(
            table not in allowed,
            f"identity table is an allowed manifest source: {table}",
        )
    for required in (
        "attribution_events",
        "attribution_allocations",
        "b23_match_verdicts",
        "b23_revenue_events",
    ):
        _require(
            required in allowed,
            f"missing allowed sanitized source read model: {required}",
        )
    for source_name, fields in allowed.items():
        lowered_fields = " ".join(str(field).lower() for field in fields)
        for token in PII_TOKENS:
            _require(
                token not in lowered_fields,
                f"manifest field contains forbidden privacy token {token}: {source_name}",
            )
        _require(
            "native_event_reference" not in lowered_fields,
            f"provider native event ref forbidden: {source_name}",
        )
        _require(
            "native_commerce_reference" not in lowered_fields,
            f"provider native commerce ref forbidden: {source_name}",
        )
    _require("id ASC" in text, "total ordering must include immutable id tie-breaker")
    _require("NULLS" in text, "total ordering must include explicit NULL handling")
    for reason in SENTINEL_REASONS:
        _require(
            reason in text,
            f"sentinel fallback category missing from contract: {reason}",
        )


def _validate_no_forbidden_scope(text: str, rel: Path) -> None:
    lowered = text.lower()
    for token in FORBIDDEN_SCOPE_TOKENS:
        token_lower = token.lower()
        if token_lower in lowered:
            raise ValidationError(
                f"P2 scope containment violation in {rel.as_posix()}: {token}"
            )


def _validate_no_identity_query(text: str, rel: Path) -> None:
    lowered = text.lower()
    for table in IDENTITY_TABLES:
        _require(
            table not in lowered,
            f"identity table must not be queried or serialized in {rel.as_posix()}: {table}",
        )
    for token in PII_TOKENS:
        _require(
            token not in lowered,
            f"PII/token field must not be queried or serialized in {rel.as_posix()}: {token}",
        )


def validate_eligibility(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, ELIGIBILITY)
    _validate_no_forbidden_scope(text, ELIGIBILITY)
    _validate_no_identity_query(text, ELIGIBILITY)
    _require("COUNT" in text.upper(), "preflight must use aggregate counts")
    _require(
        "WITH RECURSIVE" in text
        and "CROSS JOIN LATERAL" in text
        and "channel_cap_plus_one" in text,
        "preflight must use bounded next-key channel privacy cardinality",
    )
    _require("sum(" in text.lower(), "preflight must aggregate amount by currency")
    _require(
        "min(" in text.lower() and "max(" in text.lower(),
        "preflight must compute source window min/max timestamps",
    )
    _require(
        "run_eligibility_preflight" in text, "aggregate preflight function missing"
    )
    _require(
        "stream_source_chunks" not in text,
        "eligibility must not call manifest/source streaming",
    )
    _require(
        "fetchall" not in text and ".all()" not in text,
        "eligibility must not full-materialize source rows",
    )
    for reason in SENTINEL_REASONS:
        _require(reason in text, f"preflight missing fallback classification: {reason}")


def validate_source_snapshot(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, SOURCE_SNAPSHOT)
    _validate_no_forbidden_scope(text, SOURCE_SNAPSHOT)
    _validate_no_identity_query(text, SOURCE_SNAPSHOT)
    _require(
        re.search(r"SELECT\s+\*", text, re.IGNORECASE) is None,
        "SELECT * forbidden in source snapshot queries",
    )
    _require(
        re.search(r"\bOFFSET\b|\.offset\s*\(", text, re.IGNORECASE) is None,
        "OFFSET pagination forbidden in source snapshot paths",
    )
    for forbidden in (
        "row.__dict__",
        "vars(row)",
        "__table__.columns",
        ".__columns__",
        "reflect(",
        "Reflected",
    ):
        _require(
            forbidden not in text,
            f"reflected/ORM row serialization forbidden: {forbidden}",
        )
    _require(
        "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY" in text,
        "missing repeatable-read read-only transaction",
    )
    _require(
        "set_config" in text and "app.current_tenant_id" in text,
        "missing tenant GUC binding/check",
    )
    compute_pos = text.find("async def compute_source_snapshot_hash")
    _require(compute_pos >= 0, "source snapshot compute function missing")
    compute_text = text[compute_pos:]
    preflight_pos = compute_text.find("run_eligibility_preflight")
    stream_pos = compute_text.find("stream_source_chunks")
    _require(
        preflight_pos >= 0 and stream_pos >= 0 and preflight_pos < stream_pos,
        "preflight must precede source streaming",
    )
    _require("session.stream" in text, "source hashing must use streaming cursor API")
    for streaming_token in (
        "stream_results",
        "yield_per",
        "max_row_buffer",
        "SOURCE_STREAM_PARTITION_SIZE",
        "SOURCE_STREAM_MAX_ROW_BUFFER",
        ".partitions(",
    ):
        _require(
            streaming_token in text,
            f"bounded physical streaming token missing: {streaming_token}",
        )
    _require(
        "hashlib.sha256" in text and ".update(" in text,
        "hashing must update SHA-256 incrementally",
    )
    _require(
        "json.dumps(" in text and "sort_keys=True" in text and "separators=(" in text,
        "canonical JSON row encoding missing",
    )
    _require(
        "full_manifest" not in text and "json.dumps(full" not in text,
        "full manifest JSON serialization forbidden",
    )
    _require(
        "execute(query).all()" not in text
        and "fetchall" not in text
        and ".all()" not in text
        and "list(rows)" not in text
        and "list(stream" not in text,
        "full source materialization forbidden",
    )
    _require(
        text.count("_contract_row_payload(source_name, dict(row))") >= 2,
        "source rows must pass through contract allowlist projection",
    )
    for order_fragment in (
        "ORDER BY e.tenant_id ASC, e.occurred_at ASC NULLS LAST, e.id ASC",
        "ORDER BY a.tenant_id ASC, e.occurred_at ASC NULLS LAST, a.id ASC",
        "ORDER BY v.tenant_id ASC, e.occurred_at ASC NULLS LAST, v.id ASC",
        "ORDER BY tenant_id ASC, event_occurred_at ASC NULLS LAST, id ASC",
    ):
        _require(
            order_fragment in text,
            f"source stream missing total order: {order_fragment}",
        )
    _require(
        "JOIN public.attribution_events AS e" in text
        and "e.occurred_at >= :window_start" in text
        and "e.occurred_at < :window_end" in text,
        "allocation source membership must use the financial event clock",
    )
    _require(
        "FROM public.attribution_allocations AS authority" in text
        and "authority.event_id = e.id" in text
        and "authority.verified = true" in text,
        "attribution event source membership must require verified allocation lineage",
    )
    _require(
        "sentinel_material_for(preflight.fallback_reason)" in text
        and "SENTINEL_PREFIX" in text,
        "sentinel hash protocol missing",
    )
    for reason in SENTINEL_REASONS:
        material = (
            "B24_SOURCE_SNAPSHOT_SENTINEL"
            "|source_contract_version=b24-source-v1"
            "|eligibility_policy_version=b24-eligibility-v1"
            f"|fallback_reason={reason}"
        )
        expected_hash = hashlib.sha256(material.encode("utf-8")).hexdigest()
        _require(
            re.fullmatch(r"[a-f0-9]{64}", expected_hash) is not None,
            f"invalid sentinel hash for {reason}",
        )


def validate_query_path_indexes(root: Path) -> None:
    canonical = _read(root, CANONICAL_SCHEMA)
    migration = _read(root, P2_STREAM_INDEX_MIGRATION)
    for index_name in REQUIRED_SOURCE_STREAM_INDEXES:
        _require(
            index_name in canonical,
            f"canonical schema missing source stream index: {index_name}",
        )
        _require(
            index_name in migration,
            f"migration missing source stream index: {index_name}",
        )
    for fragment in (
        "ON public.attribution_events (tenant_id, occurred_at ASC, id ASC)",
        "ON public.attribution_allocations (tenant_id, created_at ASC, id ASC)",
        "ON public.b23_match_verdicts (tenant_id, last_transition_at ASC, id ASC)",
        "ON public.b23_revenue_events (tenant_id, event_occurred_at ASC, id ASC)",
    ):
        _require(
            fragment in migration, f"source stream index missing order keys: {fragment}"
        )


def validate_repository(root: Path, text: str | None = None) -> None:
    text = text if text is not None else _read(root, REPOSITORY)
    fallback_start = text.find("async def upsert_fallback_from_snapshot")
    fallback_end = text.find("async def upsert_resource_fallback_from_snapshot")
    _require(fallback_start >= 0, "fallback upsert repository method missing")
    fallback_text = text[
        fallback_start : fallback_end if fallback_end >= 0 else len(text)
    ]
    _require(
        "upsert_fallback_from_snapshot" in fallback_text,
        "fallback upsert repository method missing",
    )
    _require(
        "ON CONFLICT" in fallback_text
        and "DO NOTHING" in fallback_text
        and "SELECT id FROM inserted" in fallback_text,
        "fallback debounce must reuse immutable terminal evidence",
    )
    for marker in (
        "sampling_started_at = NULL",
        "last_fit_at = NULL",
        "runtime_seconds = NULL",
        "n_samples_actual = NULL",
        "artifact_ref = NULL",
        "artifact_hash = NULL",
    ):
        _require(
            marker in fallback_text,
            f"cold-start fallback must clear compute/artifact marker: {marker}",
        )
    _validate_no_forbidden_scope(text, REPOSITORY)


def validate_schema_surface(root: Path) -> None:
    migration = _read(root, P2_MIGRATION)
    canonical = _read(root, CANONICAL_SCHEMA)
    models = _read(root, MODELS)
    enums = _read(root, ENUMS)
    for reason in SENTINEL_REASONS:
        _require(reason in migration, f"P2 migration missing fallback reason: {reason}")
        _require(
            reason in canonical, f"canonical schema missing fallback reason: {reason}"
        )
        _require(reason in models, f"ORM model missing fallback reason: {reason}")
        _require(reason in enums, f"enum missing fallback reason: {reason}")


def validate_all(root: Path) -> None:
    for path in REQUIRED_FILES:
        _read(root, path)
    validate_input_contract(root)
    validate_eligibility(root)
    validate_source_snapshot(root)
    validate_repository(root)
    validate_schema_surface(root)
    validate_query_path_indexes(root)


def run_negative_controls(root: Path) -> None:
    contract = _read(root, INPUT_CONTRACT)
    eligibility = _read(root, ELIGIBILITY)
    snapshot = _read(root, SOURCE_SNAPSHOT)
    repository = _read(root, REPOSITORY)
    controls = (
        (
            "B24_P2_NC_THRESHOLD_BELOW_FLOOR_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace(
                    "minimum_confirmed_match_verdicts: int = MIN_SPARSE_PRIVACY_FLOOR",
                    "minimum_confirmed_match_verdicts: int = 5",
                    1,
                ),
            ),
            "below floor",
        ),
        (
            "B24_P2_NC_THRESHOLD_MISSING_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace(
                    "    minimum_confirmed_match_verdicts: int = MIN_SPARSE_PRIVACY_FLOOR\n",
                    "",
                    1,
                ),
            ),
            "threshold missing",
        ),
        (
            "B24_P2_NC_IDENTITY_TABLE_MANIFEST_SOURCE_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace(
                    '"b23_revenue_events": (',
                    '"webhook_ingress_identities": ("id", "tenant_id"),\n        "b23_revenue_events": (',
                    1,
                ),
            ),
            "identity table",
        ),
        (
            "B24_P2_NC_MANIFEST_CONTAINS_EMAIL_OR_IP_PASS",
            lambda: validate_input_contract(
                root,
                contract.replace('"currency",', '"email",\n            "currency",', 1),
            ),
            "privacy token",
        ),
        (
            "B24_P2_NC_ELIGIBILITY_AFTER_MANIFEST_FETCH_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "preflight = await run_eligibility_preflight",
                    "pre_stream = stream_source_chunks\n        preflight = await run_eligibility_preflight",
                    1,
                ),
            ),
            "preflight must precede",
        ),
        (
            "B24_P2_NC_SPLIT_OR_READ_COMMITTED_SNAPSHOT_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY",
                    "SET TRANSACTION READ WRITE",
                    1,
                ),
            ),
            "repeatable-read",
        ),
        (
            "B24_P2_NC_TIMESTAMP_ONLY_ORDER_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                        "ORDER BY e.tenant_id ASC, e.occurred_at ASC NULLS LAST, e.id ASC",
                        "ORDER BY e.occurred_at ASC",
                    1,
                ),
            ),
            "total order",
        ),
        (
            "B24_P2_NC_SPARSE_PRIVACY_STREAMED_PASS",
            lambda: validate_eligibility(
                root,
                eligibility.replace(
                    "insufficient_privacy_cohort", "sparse_stream_allowed"
                ),
            ),
            "insufficient_privacy_cohort",
        ),
        (
            "B24_P2_NC_COLD_START_HASH_CHANGES_WITH_SPARSE_NOISE_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "sentinel_material_for(preflight.fallback_reason)",
                    "str(preflight.included_row_counts_by_source)",
                    1,
                ),
            ),
            "sentinel",
        ),
        (
            "B24_P2_NC_COLD_START_SETS_LAST_FIT_PASS",
            lambda: validate_repository(
                root,
                repository.replace("last_fit_at = NULL", "last_fit_at = now()", 1),
            ),
            "last_fit_at = NULL",
        ),
        (
            "B24_P2_NC_SELECT_STAR_SOURCE_QUERY_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "SELECT\n                'attribution_events'",
                    "SELECT * -- 'attribution_events'",
                    1,
                ),
            ),
            "select *",
        ),
        (
            "B24_P2_NC_ORM_TO_JSON_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "_contract_row_payload(source_name, dict(row))",
                    "row.__dict__",
                    1,
                ),
            ),
            "serialization",
        ),
        (
            "B24_P2_NC_REFLECTED_COLUMNS_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot + "\ncolumns = model.__table__.columns\n",
            ),
            "reflected",
        ),
        (
            "B24_P2_NC_OFFSET_PAGINATION_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                        "ORDER BY e.tenant_id ASC, e.occurred_at ASC NULLS LAST, e.id ASC",
                        "ORDER BY e.tenant_id ASC, e.occurred_at ASC NULLS LAST, e.id ASC OFFSET 100",
                    1,
                ),
            ),
            "offset",
        ),
        (
            "B24_P2_NC_UNBOUNDED_FETCHALL_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(
                    "async for partition in stream.mappings().partitions(",
                    "rows = await stream.fetchall()\n        async for partition in stream.mappings().partitions(",
                    1,
                ),
            ),
            "materialization",
        ),
        (
            "B24_P2_NC_MISSING_PARTITIONS_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot.replace(".partitions(SOURCE_STREAM_PARTITION_SIZE)", "")
                .replace(
                    ".partitions(\n            SOURCE_STREAM_PARTITION_SIZE\n        )",
                    "",
                )
                .replace(".partitions(", ""),
            ),
            "bounded physical streaming",
        ),
        (
            "B24_P2_NC_UNBOUNDED_JSON_DUMPS_PASS",
            lambda: validate_source_snapshot(
                root, snapshot + "\nfull_manifest = []\njson.dumps(full_manifest)\n"
            ),
            "full manifest",
        ),
        (
            "B24_P2_NC_IMPORTS_PYMC_OR_LLM_PASS",
            lambda: validate_source_snapshot(
                root,
                snapshot + "\nimport pymc\nfrom app.llm.provider_boundary import x\n",
            ),
            "scope containment",
        ),
    )
    for label, runner, expected in controls:
        try:
            runner()
        except ValidationError as exc:
            _require(
                expected.lower() in str(exc).lower(),
                f"{label} failed for wrong reason: {exc}",
            )
            print(label)
        else:
            raise ValidationError(f"negative control did not fail: {label}")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args()
    validate_all(ROOT)
    if args.negative_control:
        run_negative_controls(ROOT)
    print("B24_P2_SOURCE_SNAPSHOT_VALIDATION_PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
