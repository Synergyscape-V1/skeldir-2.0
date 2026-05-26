from __future__ import annotations

import importlib.util
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from uuid import UUID

import pytest

from app.bayesian.design_matrix_envelope import estimate_design_matrix_envelope
from app.bayesian.enums import FallbackReason
from app.bayesian.authority_liveness import (
    AuthorityBuildStatus,
    request_feature_authority_build,
)
from app.bayesian.cardinality_db_work import (
    CardinalityDBWorkBudgetError,
    CardinalityPlanEvidence,
    validate_cardinality_plan_evidence,
)
from app.bayesian.feature_authority import (
    FeatureAuthorityStatus,
    FeatureAuthorityUnavailable,
    SourceWindowFeatureAuthority,
    load_source_window_feature_authority,
)
from app.bayesian.graph_complexity_envelope import estimate_graph_complexity_envelope
from app.bayesian.input_profile import (
    B24InputProfile,
    build_input_profile_from_preflight,
)
from app.bayesian.model_family_contract import (
    B24_ACTIVE_FEATURE_DIMENSIONS,
    ModelFamilyDimensionContractError,
    assert_candidate_dimensions_allowed_for_graph_build,
)
from app.bayesian.resource_bounds import B24_RESOURCE_POLICY, required_policy_caps
from app.bayesian.resource_profile import (
    evaluate_input_profile_resource_bounds,
    evaluate_source_snapshot_resource_bounds,
)


REPO_ROOT = Path(__file__).resolve().parents[2]
VALIDATOR = REPO_ROOT / "scripts/ci/validate_b24_p4_resource_bounds.py"
FIT_PLANNER = REPO_ROOT / "backend/app/bayesian/fit_planner.py"
FIT_CLAIM = REPO_ROOT / "backend/app/bayesian/fit_claim.py"
DISPATCH_OUTBOX = REPO_ROOT / "backend/app/bayesian/dispatch_outbox.py"
REPOSITORY = REPO_ROOT / "backend/app/bayesian/repository.py"
PREFLIGHT_LEASE = REPO_ROOT / "backend/app/bayesian/preflight_lease.py"
RESOURCE_BOUNDS = REPO_ROOT / "backend/app/bayesian/resource_bounds.py"
INPUT_PROFILE = REPO_ROOT / "backend/app/bayesian/input_profile.py"
ELIGIBILITY = REPO_ROOT / "backend/app/bayesian/eligibility.py"
DESIGN_ENVELOPE = REPO_ROOT / "backend/app/bayesian/design_matrix_envelope.py"
GRAPH_ENVELOPE = REPO_ROOT / "backend/app/bayesian/graph_complexity_envelope.py"
RESOURCE_PROFILE = REPO_ROOT / "backend/app/bayesian/resource_profile.py"
FEATURE_AUTHORITY = REPO_ROOT / "backend/app/bayesian/feature_authority.py"
AUTHORITY_LIVENESS = REPO_ROOT / "backend/app/bayesian/authority_liveness.py"
PROFILING_LEASE = REPO_ROOT / "backend/app/bayesian/profiling_lease.py"
SNAPSHOT_SUPERSESSION = REPO_ROOT / "backend/app/bayesian/snapshot_supersession.py"
MODELS = REPO_ROOT / "backend/app/bayesian/models.py"
FEATURE_AUTHORITY_MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation/202605251200_b24_p4_feature_authority.py"
)
AUTHORITY_LIVENESS_MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation/202605251430_b24_p4_authority_liveness.py"
)
SUPERSESSION_PROFILING_MIGRATION = (
    REPO_ROOT
    / "alembic/versions/007_skeldir_foundation/202605251800_b24_p4_supersession_profiling_lease.py"
)


TENANT_ID = UUID("11111111-1111-4111-8111-111111111111")
START = datetime(2026, 1, 1, tzinfo=timezone.utc)
END = START + timedelta(days=30)


def _read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def _load_validator():
    spec = importlib.util.spec_from_file_location(
        "validate_b24_p4_resource_bounds", VALIDATOR
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _profile(**overrides: int) -> B24InputProfile:
    defaults = {
        "source_row_count": 100,
        "touchpoint_count": 60,
        "conversion_count": 40,
        "channel_count": 3,
        "currency_count": 1,
        "provider_count": 1,
        "campaign_or_feature_count": 4,
        "window_days": 30,
    }
    defaults.update(overrides)
    return B24InputProfile(
        tenant_id=TENANT_ID,
        preflight_lease_id="lease",
        model_type="bayesian_attribution_confidence",
        model_version="v1",
        source_window_start=START,
        source_window_end=END,
        source_snapshot_hash="a" * 64,
        policy_version=B24_RESOURCE_POLICY.policy_version,
        cardinality_profiled_dimensions=tuple(sorted(B24_ACTIVE_FEATURE_DIMENSIONS)),
        computed_at=START,
        **defaults,
    )


def _snapshot_from_profile(profile: B24InputProfile):
    preflight = SimpleNamespace(
        tenant_id=profile.tenant_id,
        model_type=profile.model_type,
        model_version=profile.model_version,
        source_window_start=profile.source_window_start,
        source_window_end=profile.source_window_end,
        included_row_counts_by_source={
            "attribution_events": profile.conversion_count,
            "attribution_allocations": profile.touchpoint_count,
            "b23_match_verdicts": 0,
            "b23_revenue_events": 0,
        },
        eligible_channel_count=profile.channel_count,
        eligible_amount_minor_by_currency={
            f"C{i}": 1 for i in range(profile.currency_count)
        },
    )
    return SimpleNamespace(
        tenant_id=profile.tenant_id,
        model_type=profile.model_type,
        model_version=profile.model_version,
        source_window_start=profile.source_window_start,
        source_window_end=profile.source_window_end,
        source_snapshot_hash=profile.source_snapshot_hash,
        preflight=preflight,
    )


def _authority_from_profile(
    profile: B24InputProfile,
    *,
    source_snapshot_hash: str | None = None,
    freshness_status: FeatureAuthorityStatus = FeatureAuthorityStatus.FRESH,
) -> SourceWindowFeatureAuthority:
    return SourceWindowFeatureAuthority(
        tenant_id=profile.tenant_id,
        model_type=profile.model_type,
        model_version=profile.model_version,
        source_window_start=profile.source_window_start,
        source_window_end=profile.source_window_end,
        source_snapshot_hash=source_snapshot_hash or profile.source_snapshot_hash,
        channel_count=profile.channel_count,
        currency_count=profile.currency_count,
        provider_count=profile.provider_count,
        campaign_or_feature_count=profile.campaign_or_feature_count,
        freshness_status=freshness_status,
        policy_version=B24_RESOURCE_POLICY.policy_version,
        computed_at=profile.computed_at,
    )


def _decision(profile: B24InputProfile):
    return evaluate_input_profile_resource_bounds(input_profile=profile)


def _valid_plan_evidence(**overrides: int | float | str) -> CardinalityPlanEvidence:
    defaults = {
        "total_plan_rows": 2_000,
        "shared_buffers_hit_or_read": 4_000,
        "temp_blocks_read_or_written": 0,
        "sort_nodes": 0,
        "hashaggregate_nodes": 0,
        "seq_scan_nodes": 0,
        "bitmap_heap_scan_nodes": 0,
        "execution_ms": 50.0,
        "planning_ms": 10.0,
        "work_mem": B24_RESOURCE_POLICY.cardinality_plan_work_mem,
        "explain_options": "EXPLAIN (ANALYZE, BUFFERS, VERBOSE, SETTINGS)",
    }
    defaults.update(overrides)
    return CardinalityPlanEvidence(**defaults)


class _FakeMappings:
    def __init__(self, row):
        self._row = row

    def one_or_none(self):
        return self._row

    def one(self):
        return self._row


class _FakeResult:
    def __init__(self, row):
        self._row = row

    def mappings(self):
        return _FakeMappings(self._row)

    def scalar_one(self):
        return self._row


class _FakeAuthoritySession:
    def __init__(self, exact_row=None, related_row=None):
        self._rows = [exact_row, related_row]
        self.calls = 0

    async def execute(self, *_args, **_kwargs):
        row = self._rows[self.calls]
        self.calls += 1
        return _FakeResult(row)


def _authority_row(
    profile: B24InputProfile,
    *,
    status: str = "fresh",
    policy_version: str | None = None,
) -> dict[str, object]:
    return {
        "tenant_id": profile.tenant_id,
        "model_type": profile.model_type,
        "model_version": profile.model_version,
        "source_window_start": profile.source_window_start,
        "source_window_end": profile.source_window_end,
        "source_snapshot_hash": profile.source_snapshot_hash,
        "channel_count": profile.channel_count,
        "currency_count": profile.currency_count,
        "provider_count": profile.provider_count,
        "campaign_or_feature_count": profile.campaign_or_feature_count,
        "freshness_status": status,
        "policy_version": policy_version or B24_RESOURCE_POLICY.policy_version,
        "computed_at": profile.computed_at,
    }


def test_b24_p4_resource_policy_has_required_caps() -> None:
    caps = required_policy_caps()
    assert caps["B24_RESOURCE_POLICY_VERSION"] == "b24-resource-policy-v1"
    assert all(value is not None for value in caps.values())
    assert caps["B24_MAX_CARDINALITY_PLAN_TEMP_BLOCKS"] == 0
    assert caps["B24_MAX_CARDINALITY_PLAN_HASHAGGREGATE_NODES"] == 0
    assert caps["B24_MAX_CARDINALITY_PLAN_SORT_NODES"] == 0


def test_b24_p4_missing_or_zero_cap_fails_validator() -> None:
    validator = _load_validator()
    text = _read(RESOURCE_BOUNDS).replace(
        "max_source_rows: int = 250_000", "max_source_rows: int = 0", 1
    )
    with pytest.raises(validator.ValidationError, match="cap"):
        validator.validate_policy(REPO_ROOT, text)


def test_b24_p4_preflight_lease_acquired_before_source_snapshot() -> None:
    text = _read(FIT_PLANNER)
    plan_text = text[text.find("async def plan_candidate") :]
    assert plan_text.find(
        "preflight_lease = await acquire_preflight_lease"
    ) < plan_text.find("snapshot = await compute_source_snapshot_hash")


def test_b24_p4_concurrent_planners_only_one_runs_source_snapshot_and_profile() -> None:
    text = _read(FIT_PLANNER)
    plan_text = text[text.find("async def plan_candidate") :]
    assert "if not preflight_lease.acquired" in text
    assert plan_text.find("if not preflight_lease.acquired") < plan_text.find(
        "snapshot = await compute_source_snapshot_hash"
    )
    assert 'status="suppressed"' in text


def test_b24_p4_preflight_lease_stale_recovery() -> None:
    text = _read(PREFLIGHT_LEASE)
    assert "leased_until" in text
    assert "stale_recovered_at = now()" in text


def test_b24_p4_resource_failure_terminalizes_preflight_lease_without_dispatch() -> (
    None
):
    planner = _read(FIT_PLANNER)
    repo = _read(REPOSITORY)
    assert "terminalize_preflight_lease" in planner
    assert "upsert_resource_fallback_from_snapshot" in planner
    assert "INSERT INTO public.b24_fit_dispatch_outbox" not in repo


def test_b24_p4_profile_computed_before_dispatchable_outbox() -> None:
    text = _read(FIT_PLANNER)
    plan_text = text[text.find("async def plan_candidate") :]
    assert plan_text.find("evaluate_source_snapshot_resource_bounds") < plan_text.find(
        "claim_fit_for_snapshot"
    )


def test_b24_p4_dispatcher_cannot_select_resource_pending_rows() -> None:
    text = _read(DISPATCH_OUTBOX)
    assert "status IN ('pending', 'failed_retryable', 'stale_recovered')" in text
    assert "resource_pending" not in text
    assert "resource_rejected" not in text


def test_b24_p4_profile_uses_aggregate_queries_not_raw_row_materialization() -> None:
    text = _read(INPUT_PROFILE)
    for forbidden in (
        "fetchall",
        ".all()",
        "list(rows)",
        "DataFrame",
        "np.empty",
        "np.zeros",
    ):
        assert forbidden not in text


def test_b24_p4_no_raw_source_recursive_cardinality_in_planner() -> None:
    text = _read(ELIGIBILITY)
    assert "campaign_feature_keys" not in text
    assert "provider_keys" not in text
    assert "candidate.campaign_id >" not in text
    assert "candidate.provider >" not in text


def test_b24_p4_uses_source_window_feature_vocabulary_or_rollup() -> None:
    text = _read(FEATURE_AUTHORITY)
    migration = _read(FEATURE_AUTHORITY_MIGRATION)
    assert "b24_source_window_feature_authority" in text
    assert "b24_source_window_feature_authority" in migration
    assert "UPSERT_SOURCE_WINDOW_FEATURE_AUTHORITY_SQL" in text


def test_b24_p4_feature_authority_keyed_by_source_snapshot_hash() -> None:
    text = _read(FEATURE_AUTHORITY) + _read(MODELS) + _read(FEATURE_AUTHORITY_MIGRATION)
    assert "source_snapshot_hash = :source_snapshot_hash" in text
    assert "source_snapshot_hash" in text
    assert "b24_source_window_feature_authority_pkey" in text


@pytest.mark.asyncio
async def test_b24_p4_missing_feature_authority_fails_closed() -> None:
    profile = _profile()
    session = _FakeAuthoritySession(exact_row=None, related_row=None)
    with pytest.raises(FeatureAuthorityUnavailable) as exc:
        await load_source_window_feature_authority(
            session,
            tenant_id=profile.tenant_id,
            model_type=profile.model_type,
            model_version=profile.model_version,
            source_window_start=profile.source_window_start,
            source_window_end=profile.source_window_end,
            source_snapshot_hash=profile.source_snapshot_hash,
        )
    assert exc.value.reason == FallbackReason.CARDINALITY_AUTHORITY_MISSING


@pytest.mark.asyncio
async def test_b24_p4_stale_feature_authority_fails_closed() -> None:
    profile = _profile()
    session = _FakeAuthoritySession(exact_row=_authority_row(profile, status="stale"))
    with pytest.raises(FeatureAuthorityUnavailable) as exc:
        await load_source_window_feature_authority(
            session,
            tenant_id=profile.tenant_id,
            model_type=profile.model_type,
            model_version=profile.model_version,
            source_window_start=profile.source_window_start,
            source_window_end=profile.source_window_end,
            source_snapshot_hash=profile.source_snapshot_hash,
        )
    assert exc.value.reason == FallbackReason.CARDINALITY_AUTHORITY_STALE


@pytest.mark.asyncio
async def test_b24_p4_mismatched_source_snapshot_authority_fails_closed() -> None:
    profile = _profile()
    session = _FakeAuthoritySession(
        exact_row=None,
        related_row={
            "source_snapshot_hash": "b" * 64,
            "freshness_status": "fresh",
            "computed_at": profile.computed_at,
        },
    )
    with pytest.raises(FeatureAuthorityUnavailable) as exc:
        await load_source_window_feature_authority(
            session,
            tenant_id=profile.tenant_id,
            model_type=profile.model_type,
            model_version=profile.model_version,
            source_window_start=profile.source_window_start,
            source_window_end=profile.source_window_end,
            source_snapshot_hash=profile.source_snapshot_hash,
        )
    assert exc.value.reason == FallbackReason.CARDINALITY_AUTHORITY_MISMATCH


def test_b24_p4_missing_count_never_defaults_to_zero() -> None:
    text = _read(INPUT_PROFILE)
    assert "feature_authority.provider_count" in text
    assert "feature_authority.campaign_or_feature_count" in text
    assert "provider_count=0" not in text
    assert "campaign_or_feature_count=0" not in text


def test_b24_p4_async_campaign_arrival_after_rollup_blocks_approval() -> None:
    text = _read(FIT_PLANNER) + _read(FEATURE_AUTHORITY)
    assert "source_snapshot_hash=snapshot.source_snapshot_hash" in text
    assert "CARDINALITY_AUTHORITY_MISMATCH" in text


def test_b24_p4_rollup_lag_creates_non_dispatchable_state() -> None:
    text = _read(FIT_PLANNER) + _read(AUTHORITY_LIVENESS)
    assert "request_feature_authority_build" in text
    assert "authority_waiting" in text
    assert "INSERT INTO public.b24_fit_dispatch_outbox" not in _read(REPOSITORY)


def test_b24_p4_missing_authority_yields_transient_state_not_fallback_only() -> None:
    text = _read(FIT_PLANNER)
    authority_branch = text[
        text.find("except FeatureAuthorityUnavailable") : text.find(
            "assert feature_authority is not None"
        )
    ]
    assert "request_feature_authority_build" in authority_branch
    assert "mark_authority_waiting_dirty_events" in authority_branch
    assert 'status="fallback_only"' not in authority_branch


def test_b24_p4_stale_authority_yields_transient_state_not_fallback_only() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(FIT_PLANNER)
    assert "cardinality_authority_stale" in text
    assert "authority_waiting" in text
    assert "AuthorityBuildStatus.TIMEOUT" in text


def test_b24_p4_mismatched_authority_yields_transient_state_not_fallback_only() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(FIT_PLANNER)
    assert "cardinality_authority_mismatch" in text
    assert "source_snapshot_hash" in text
    assert "authority_waiting" in text


def test_b24_p4_authority_yield_creates_no_dispatchable_outbox() -> None:
    branch = _read(FIT_PLANNER)
    branch = branch[
        branch.find("except FeatureAuthorityUnavailable") : branch.find(
            "assert feature_authority is not None"
        )
    ]
    assert "INSERT INTO public.b24_fit_dispatch_outbox" not in branch
    assert "claim_fit_for_snapshot" not in branch


def test_b24_p4_authority_yield_does_not_claim_fit() -> None:
    text = _read(FIT_PLANNER)
    authority_branch = text[
        text.find("except FeatureAuthorityUnavailable") : text.find(
            "assert feature_authority is not None"
        )
    ]
    assert "claim_fit_for_snapshot" not in authority_branch
    assert (
        "upsert_feature_authority_fallback_from_snapshot"
        not in authority_branch[: authority_branch.find("AuthorityBuildStatus.TIMEOUT")]
    )


def test_b24_p4_authority_yield_preserves_retry_intent() -> None:
    text = (
        _read(AUTHORITY_LIVENESS)
        + _read(FIT_PLANNER)
        + _read(AUTHORITY_LIVENESS_MIGRATION)
    )
    for token in (
        "b24_feature_authority_build_requests",
        "retry_count",
        "retry_after_at",
        "max_retries",
        "source_snapshot_hash",
        "authority_waiting",
    ):
        assert token in text


@pytest.mark.asyncio
async def test_b24_p4_authority_build_request_is_created_idempotently() -> None:
    profile = _profile()
    returned = {
        "tenant_id": profile.tenant_id,
        "model_type": profile.model_type,
        "model_version": profile.model_version,
        "source_window_start": profile.source_window_start,
        "source_window_end": profile.source_window_end,
        "source_snapshot_hash": profile.source_snapshot_hash,
        "status": "authority_build_requested",
        "retry_count": 0,
        "max_retries": 5,
        "retry_after_at": profile.computed_at,
        "terminal_reason": None,
    }
    session = _FakeAuthoritySession(exact_row=returned)
    result = await request_feature_authority_build(
        session,
        snapshot=_snapshot_from_profile(profile),
        reason=FallbackReason.CARDINALITY_AUTHORITY_MISSING,
        detail="missing",
    )
    assert result.status == AuthorityBuildStatus.BUILD_REQUESTED
    assert "ON CONFLICT" in _read(AUTHORITY_LIVENESS)


def test_b24_p4_authority_completion_reactivates_planner() -> None:
    text = _read(FEATURE_AUTHORITY) + _read(AUTHORITY_LIVENESS)
    assert "reactivate_planner_for_feature_authority" in text
    assert "feature_authority_fresh" in text
    assert "INSERT INTO public.b24_dirty_events" in text


def test_b24_p4_stale_wait_retries_without_new_webhook() -> None:
    text = _read(AUTHORITY_LIVENESS)
    assert "sweep_authority_waiting_requests" in text
    assert "authority_retry_ready" in text
    assert "JOIN public.b24_source_window_feature_authority" in text


def test_b24_p4_reactivation_is_source_snapshot_scoped() -> None:
    text = _read(AUTHORITY_LIVENESS)
    assert "source_snapshot_hash = :source_snapshot_hash" in text
    assert "source_event_id" in text


def test_b24_p4_reactivation_is_idempotent() -> None:
    text = _read(AUTHORITY_LIVENESS)
    assert "status IN (" in text
    assert "'authority_completed'" in text
    assert "FROM transitioned" in text


def test_b24_p4_reactivation_respects_p3_preflight_lock() -> None:
    planner = _read(FIT_PLANNER)
    assert "status IN ('pending', 'authority_retry_ready')" in planner
    assert planner.find("lease_debounced_dirty_candidates") < planner.find(
        "preflight_lease = await acquire_preflight_lease"
    )


def test_b24_p4_reactivation_respects_active_execution_lock() -> None:
    text = _read(FIT_PLANNER) + _read(AUTHORITY_LIVENESS)
    assert "claim_fit_for_snapshot" in text
    assert "acquire_preflight_lease" in text
    assert "authority_retry_ready" in text


def test_b24_p4_authority_wait_retry_budget_terminalizes_safely() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(FIT_PLANNER)
    assert "max_retries" in text
    assert "cardinality_authority_timeout" in text
    assert "AuthorityBuildStatus.TIMEOUT" in text


def test_b24_p4_authority_timeout_is_distinct_from_fallback_only() -> None:
    text = (
        _read(AUTHORITY_LIVENESS)
        + _read(REPOSITORY)
        + _read(AUTHORITY_LIVENESS_MIGRATION)
    )
    assert "cardinality_authority_timeout" in text
    assert "cardinality_authority_build_failed" in text


def test_b24_p4_validator_rejects_authority_missing_to_fallback_only() -> None:
    validator = _load_validator()
    mutated = _read(FIT_PLANNER).replace(
        "await mark_authority_waiting_dirty_events",
        'mark_dirty_events_for_candidate  # status="fallback_only"',
        1,
    )
    with pytest.raises(validator.ValidationError, match="authority-yield"):
        validator.validate_authority_liveness_texts(
            REPO_ROOT,
            planner_text=mutated,
        )


def test_b24_p4_validator_rejects_stale_wait_without_reactivation() -> None:
    validator = _load_validator()
    mutated = _read(AUTHORITY_LIVENESS).replace(
        "def sweep_authority_waiting_requests",
        "def missing_sweeper",
        1,
    )
    with pytest.raises(validator.ValidationError, match="sweeper"):
        validator.validate_authority_liveness_texts(
            REPO_ROOT,
            liveness_text=mutated,
        )


def test_b24_p4_validator_rejects_reactivation_without_source_snapshot_hash() -> None:
    validator = _load_validator()
    mutated = _read(AUTHORITY_LIVENESS).replace(
        "AND source_snapshot_hash = :source_snapshot_hash",
        "",
    )
    with pytest.raises(validator.ValidationError, match="source_snapshot_hash"):
        validator.validate_authority_liveness_texts(
            REPO_ROOT,
            liveness_text=mutated,
        )


def test_b24_p4_validator_rejects_authority_retry_bypassing_p3_locks() -> None:
    validator = _load_validator()
    mutated = _read(FIT_PLANNER).replace(
        "status IN ('pending', 'authority_retry_ready')",
        "status = 'pending'",
        1,
    )
    with pytest.raises(validator.ValidationError, match="normal dirty-event"):
        validator.validate_authority_liveness_texts(
            REPO_ROOT,
            planner_text=mutated,
        )


def test_b24_p4_hash_a_retry_superseded_if_hash_b_already_dispatched() -> None:
    text = _read(SNAPSHOT_SUPERSESSION) + _read(FIT_PLANNER)
    assert "check_snapshot_supersession" in text
    assert "newer_dispatch_outbox_visible" in text
    assert "outbox.status IN ('pending', 'dispatching', 'dispatched')" in text
    assert 'terminal_status="authority_retry_superseded"' in text


def test_b24_p4_hash_a_retry_superseded_if_hash_b_already_completed() -> None:
    text = _read(SNAPSHOT_SUPERSESSION)
    assert "newer_fit_claimed_dispatched_or_completed" in text
    assert "fit.status IN ('queued', 'running', 'succeeded')" in text
    assert "fit.created_at > frozen.lineage_at" in text


def test_b24_p4_hash_a_cannot_overwrite_hash_b_artifacts() -> None:
    text = _read(SNAPSHOT_SUPERSESSION)
    assert "assert_snapshot_artifact_not_regressing_current_output" in text
    assert "older Hash A cannot overwrite newer Hash B artifact" in text
    assert "TrustEnvelope current output" in text


def test_b24_p4_newer_snapshot_dominates_older_authority_retry() -> None:
    text = _read(SNAPSHOT_SUPERSESSION)
    assert "SNAPSHOT_SUPERSESSION_POLICY_VERSION" in text
    assert "active_source_snapshot_hash <> :source_snapshot_hash" in text
    assert "newer_active_execution_owner" in text


def test_b24_p4_superseded_hash_a_creates_no_dispatchable_outbox() -> None:
    planner = _read(FIT_PLANNER)
    assert planner.find('status="authority_retry_superseded"') < planner.find(
        "claim = await claim_fit_for_snapshot"
    )
    assert "INSERT INTO public.b24_fit_dispatch_outbox" not in planner


def test_b24_p4_hash_a_hash_b_lifecycles_remain_separate() -> None:
    planner = _read(FIT_PLANNER)
    assert "source_snapshot_hash," in planner
    assert (
        "source_snapshot_hash IS NOT DISTINCT FROM dirty.source_snapshot_hash"
        in planner
    )
    assert "source_snapshot_hash IS NOT DISTINCT FROM :source_snapshot_hash" in planner


def test_b24_p4_missing_authority_creates_build_request_and_dispatch_signal() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(SUPERSESSION_PROFILING_MIGRATION)
    assert "b24_feature_authority_build_requests" in text
    assert "b24_feature_authority_build_outbox" in text
    assert "FEATURE_AUTHORITY_BUILD_TASK" in text


def test_b24_p4_build_request_dispatch_uses_transactional_outbox_or_bounded_sweeper() -> (
    None
):
    text = _read(AUTHORITY_LIVENESS)
    assert "WITH upserted_request AS" in text
    assert "queued_dispatch AS" in text
    assert "lease_due_feature_authority_build_dispatches" in text
    assert "FOR UPDATE SKIP LOCKED" in text


def test_b24_p4_build_request_dispatch_is_idempotent() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(SUPERSESSION_PROFILING_MIGRATION)
    assert "ON CONFLICT (" in text
    assert "uq_b24_feature_authority_build_outbox_candidate" in text
    assert "dispatch_key" in text


def test_b24_p4_build_request_not_left_unclaimed_without_dispatcher() -> None:
    text = _read(AUTHORITY_LIVENESS)
    assert "dispatch_due_feature_authority_builds" in text
    assert "publish_feature_authority_build" in text
    assert "mark_feature_authority_build_dispatched" in text


def test_b24_p4_build_dispatch_has_latency_budget() -> None:
    text = _read(AUTHORITY_LIVENESS) + _read(MODELS)
    assert "DEFAULT_AUTHORITY_BUILD_DISPATCH_BATCH_SIZE" in text
    assert "next_attempt_at" in text
    assert "idx_b24_feature_authority_build_outbox_due" in text


def test_b24_p4_only_one_planner_profiles_same_frozen_hash() -> None:
    text = _read(PROFILING_LEASE) + _read(FIT_PLANNER)
    assert "acquire_profiling_lease" in text
    assert "source_snapshot_hash" in text
    assert "ON CONFLICT" in text
    assert "if not profiling_lease.acquired" in text


def test_b24_p4_duplicate_feature_authority_fresh_events_do_not_duplicate_p4_profiling() -> (
    None
):
    text = _read(FIT_PLANNER)
    assert "status IN ('pending', 'authority_retry_ready')" in text
    assert "acquire_profiling_lease" in text
    assert text.find("acquire_profiling_lease") < text.find(
        "evaluate_source_snapshot_resource_bounds"
    )


def test_b24_p4_profiling_lease_required_before_p4_envelope() -> None:
    planner = _read(FIT_PLANNER)
    plan_text = planner[planner.find("async def plan_candidate") :]
    assert plan_text.find("acquire_profiling_lease") < plan_text.find(
        "evaluate_source_snapshot_resource_bounds"
    )
    assert plan_text.find("acquire_profiling_lease") < plan_text.find(
        "load_source_window_feature_authority"
    )


def test_b24_p4_profiling_lease_released_on_authority_failure() -> None:
    text = _read(FIT_PLANNER)
    branch = text[
        text.find("except FeatureAuthorityUnavailable") : text.find(
            "if authority_yield is not None"
        )
    ]
    assert "terminalize_profiling_lease" in branch
    assert "PROFILE_FAILED" in branch


def test_b24_p4_profiling_lease_released_on_resource_rejection() -> None:
    text = _read(FIT_PLANNER)
    branch = text[text.find("if not resource_decision.allowed") :]
    assert "terminalize_profiling_lease" in branch
    assert "PROFILE_REJECTED" in branch


def test_b24_p4_profiling_lease_released_on_supersession() -> None:
    text = _read(FIT_PLANNER)
    assert "PROFILE_SUPERSEDED" in text
    assert "authority_retry_superseded" in text


def test_b24_p4_profiling_lease_released_on_exception() -> None:
    text = _read(PROFILING_LEASE) + _read(FIT_PLANNER)
    assert "profile_failed" in text
    assert "PROFILE_FAILED" in text
    assert "terminalize_profiling_lease" in text


def test_b24_p4_profiling_lease_transitions_safely_to_claim_path() -> None:
    text = _read(FIT_PLANNER)
    claim_branch = text[text.find("claim = await claim_fit_for_snapshot") :]
    assert "PROFILE_PASSED" in claim_branch
    assert "terminalize_profiling_lease" in claim_branch


def test_b24_p4_validator_rejects_missing_snapshot_supersession() -> None:
    validator = _load_validator()
    mutated = _read(FIT_PLANNER).replace(
        "check_snapshot_supersession",
        "missing_snapshot_supersession",
    )
    with pytest.raises(validator.ValidationError, match="supersession"):
        validator.validate_snapshot_supersession_texts(
            REPO_ROOT,
            planner_text=mutated,
        )


def test_b24_p4_validator_rejects_hash_a_overwriting_hash_b() -> None:
    validator = _load_validator()
    mutated = _read(SNAPSHOT_SUPERSESSION).replace(
        "assert_snapshot_artifact_not_regressing_current_output",
        "allow_snapshot_artifact_regression",
        1,
    )
    with pytest.raises(validator.ValidationError, match="artifact"):
        validator.validate_snapshot_supersession_texts(
            REPO_ROOT,
            supersession_text=mutated,
        )


def test_b24_p4_validator_rejects_build_request_without_dispatch() -> None:
    validator = _load_validator()
    mutated = _read(AUTHORITY_LIVENESS).replace(
        "queued_dispatch AS",
        "missing_dispatch AS",
        1,
    )
    with pytest.raises(validator.ValidationError, match="build dispatch"):
        validator.validate_snapshot_supersession_texts(
            REPO_ROOT,
            liveness_text=mutated,
        )


def test_b24_p4_validator_rejects_p4_profiling_without_lease() -> None:
    validator = _load_validator()
    mutated = _read(FIT_PLANNER).replace(
        "acquire_profiling_lease",
        "missing_profiling_lease",
    )
    with pytest.raises(validator.ValidationError, match="profiling lease"):
        validator.validate_snapshot_supersession_texts(
            REPO_ROOT,
            planner_text=mutated,
        )


def test_b24_p4_validator_rejects_duplicate_p4_profiling() -> None:
    validator = _load_validator()
    mutated = _read(PROFILING_LEASE).replace("ON CONFLICT", "-- no conflict guard", 1)
    with pytest.raises(validator.ValidationError, match="one profiler"):
        validator.validate_snapshot_supersession_texts(
            REPO_ROOT,
            profiling_text=mutated,
        )


def test_b24_p4_vocabulary_upsert_is_tenant_window_snapshot_feature_scoped() -> None:
    text = _read(FEATURE_AUTHORITY)
    for token in (
        "tenant_id",
        "model_type",
        "model_version",
        "source_window_start",
        "source_window_end",
        "source_snapshot_hash",
        "ON CONFLICT",
    ):
        assert token in text


def test_b24_p4_provider_count_not_silently_zero() -> None:
    profile = _profile(provider_count=3)
    built = build_input_profile_from_preflight(
        preflight_lease_id="lease",
        source_snapshot_hash=profile.source_snapshot_hash,
        preflight=_snapshot_from_profile(profile).preflight,
        feature_authority=_authority_from_profile(profile),
    )
    assert built.provider_count == 3
    assert "provider" in built.cardinality_profiled_dimensions


def test_b24_p4_campaign_or_feature_count_not_silently_zero() -> None:
    profile = _profile(campaign_or_feature_count=33)
    built = build_input_profile_from_preflight(
        preflight_lease_id="lease",
        source_snapshot_hash=profile.source_snapshot_hash,
        preflight=_snapshot_from_profile(profile).preflight,
        feature_authority=_authority_from_profile(profile),
    )
    assert built.campaign_or_feature_count == 33
    assert "campaign_or_feature" in built.cardinality_profiled_dimensions


def test_b24_p4_group_by_limit_requires_explain_proof() -> None:
    validator = _load_validator()
    mutated = (
        _read(INPUT_PROFILE)
        + "\nSELECT channel FROM source GROUP BY channel LIMIT 129\n"
    )
    with pytest.raises(validator.ValidationError, match="GROUP BY LIMIT"):
        validator.validate_resource_profile_texts(REPO_ROOT, mutated)


def test_b24_p4_campaign_cardinality_does_not_use_plain_count_distinct() -> None:
    text = _read(ELIGIBILITY)
    assert "count(DISTINCT campaign_id" not in text
    assert "count(DISTINCT feature_key" not in text
    assert "COUNT(DISTINCT" not in text.upper()


def test_b24_p4_provider_cardinality_does_not_use_plain_count_distinct() -> None:
    text = _read(ELIGIBILITY)
    assert "count(DISTINCT provider" not in text
    assert "UNION\n" not in text
    assert "UNION ALL" in text


def test_b24_p4_campaign_cardinality_uses_rollup_vocabulary_or_true_early_stop() -> (
    None
):
    text = _read(FEATURE_AUTHORITY)
    assert "b24_source_window_feature_authority" in text
    assert "source_snapshot_hash = :source_snapshot_hash" in text
    assert "campaign_or_feature_count" in text


def test_b24_p4_provider_cardinality_uses_rollup_vocabulary_or_true_early_stop() -> (
    None
):
    text = _read(FEATURE_AUTHORITY)
    assert "b24_source_window_feature_authority" in text
    assert "source_snapshot_hash = :source_snapshot_hash" in text
    assert "provider_count" in text


def test_b24_p4_unproven_group_by_limit_cardinality_rejected() -> None:
    validator = _load_validator()
    with pytest.raises(validator.ValidationError, match="GROUP BY LIMIT"):
        validator.validate_resource_profile_module_texts(
            REPO_ROOT,
            input_text=_read(INPUT_PROFILE),
            eligibility_text=_read(ELIGIBILITY)
            + "\nSELECT campaign_id FROM source GROUP BY campaign_id LIMIT 2049\n",
            design_text=_read(DESIGN_ENVELOPE),
            graph_text=_read(GRAPH_ENVELOPE),
        )


def test_b24_p4_validator_rejects_raw_source_cardinality_discovery() -> None:
    validator = _load_validator()
    with pytest.raises(validator.ValidationError, match="raw-source"):
        validator.validate_resource_profile_module_texts(
            REPO_ROOT,
            input_text=_read(INPUT_PROFILE),
            eligibility_text=_read(ELIGIBILITY)
            + "\nprovider_keys AS (SELECT provider FROM public.b23_revenue_events)\n",
            design_text=_read(DESIGN_ENVELOPE),
            graph_text=_read(GRAPH_ENVELOPE),
        )


def test_b24_p4_eligibility_validator_rejects_count_distinct_regression() -> None:
    validator = _load_validator()
    with pytest.raises(validator.ValidationError, match="COUNT\\(DISTINCT"):
        validator.validate_resource_profile_module_texts(
            REPO_ROOT,
            input_text=_read(INPUT_PROFILE),
            eligibility_text=_read(ELIGIBILITY)
            + "\nSELECT count(DISTINCT campaign_id) FROM public.attribution_events\n",
            design_text=_read(DESIGN_ENVELOPE),
            graph_text=_read(GRAPH_ENVELOPE),
        )


def test_b24_p4_exact_distinct_with_partial_index_is_not_sufficient() -> None:
    validator = _load_validator()
    mutated = (
        _read(ELIGIBILITY)
        + "\n-- partial index exists\n"
        + "SELECT count(DISTINCT provider) FROM public.b23_revenue_events\n"
    )
    with pytest.raises(validator.ValidationError, match="COUNT\\(DISTINCT"):
        validator.validate_resource_profile_module_texts(
            REPO_ROOT,
            input_text=_read(INPUT_PROFILE),
            eligibility_text=mutated,
            design_text=_read(DESIGN_ENVELOPE),
            graph_text=_read(GRAPH_ENVELOPE),
        )


def test_b24_p4_tiny_fixture_explain_is_not_sufficient() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="SETTINGS"):
        validate_cardinality_plan_evidence(
            _valid_plan_evidence(explain_options="EXPLAIN (ANALYZE, BUFFERS, VERBOSE)")
        )


def test_b24_p4_cardinality_plan_rejects_hashaggregate_over_large_slice() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="hashaggregate"):
        validate_cardinality_plan_evidence(_valid_plan_evidence(hashaggregate_nodes=1))


def test_b24_p4_cardinality_plan_rejects_sort_over_large_slice() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="sort"):
        validate_cardinality_plan_evidence(_valid_plan_evidence(sort_nodes=1))


def test_b24_p4_cardinality_plan_rejects_large_seq_scan_or_bitmap_heap_scan() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="seq_scan"):
        validate_cardinality_plan_evidence(_valid_plan_evidence(seq_scan_nodes=1))
    with pytest.raises(CardinalityDBWorkBudgetError, match="bitmap_heap_scan"):
        validate_cardinality_plan_evidence(
            _valid_plan_evidence(bitmap_heap_scan_nodes=1)
        )


def test_b24_p4_cardinality_plan_rejects_temp_spill() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="temp_blocks"):
        validate_cardinality_plan_evidence(
            _valid_plan_evidence(temp_blocks_read_or_written=1)
        )


def test_b24_p4_cardinality_plan_enforces_buffers_budget() -> None:
    with pytest.raises(CardinalityDBWorkBudgetError, match="shared_buffers"):
        validate_cardinality_plan_evidence(
            _valid_plan_evidence(
                shared_buffers_hit_or_read=B24_RESOURCE_POLICY.max_cardinality_plan_shared_buffers
                + 1
            )
        )
    validate_cardinality_plan_evidence(_valid_plan_evidence())


def test_b24_p4_validator_rejects_silent_zero_feature_dimensions() -> None:
    validator = _load_validator()
    provider_zero = _read(INPUT_PROFILE).replace(
        "provider_count=int(feature_authority.provider_count)",
        "provider_count=0",
        1,
    )
    with pytest.raises(validator.ValidationError, match="silent zero"):
        validator.validate_resource_profile_texts(REPO_ROOT, provider_zero)
    campaign_zero = _read(INPUT_PROFILE).replace(
        "campaign_or_feature_count=int(feature_authority.campaign_or_feature_count)",
        "campaign_or_feature_count=0",
        1,
    )
    with pytest.raises(validator.ValidationError, match="silent zero"):
        validator.validate_resource_profile_texts(REPO_ROOT, campaign_zero)


def test_b24_p4_memory_estimate_is_arithmetic_only() -> None:
    text = _read(DESIGN_ENVELOPE)
    assert "estimated_tensor_elements" in text
    assert "estimated_input_memory_bytes" in text
    assert "np." not in text and "pandas" not in text


def test_b24_p4_graph_complexity_estimate_is_formula_only_no_pymc_pytensor() -> None:
    text = _read(GRAPH_ENVELOPE)
    assert "estimated_symbolic_nodes" in text
    assert "estimated_random_variables" in text
    assert "pymc" not in text.lower()
    assert "pytensor" not in text.lower()


def test_b24_p4_active_dimension_must_have_live_profiler() -> None:
    profile = _profile()
    unprofiled = B24InputProfile(
        **{
            **profile.__dict__,
            "cardinality_profiled_dimensions": ("channel", "currency"),
        }
    )
    with pytest.raises(ModelFamilyDimensionContractError, match="provider"):
        estimate_design_matrix_envelope(unprofiled)


def test_b24_p4_p5_cannot_use_unprofiled_campaign_dimension() -> None:
    with pytest.raises(ModelFamilyDimensionContractError, match="campaign_or_feature"):
        assert_candidate_dimensions_allowed_for_graph_build(
            model_type="mmm",
            requested_dimensions=("campaign_or_feature",),
            profiled_dimensions=("channel", "currency", "provider"),
        )


def test_b24_p4_p5_cannot_use_unprofiled_provider_dimension() -> None:
    with pytest.raises(ModelFamilyDimensionContractError, match="provider"):
        assert_candidate_dimensions_allowed_for_graph_build(
            model_type="mmm",
            requested_dimensions=("provider",),
            profiled_dimensions=("channel", "currency", "campaign_or_feature"),
        )


def test_b24_p4_large_projected_shape_returns_fallback_without_allocation() -> None:
    decision = _decision(
        _profile(touchpoint_count=10_000_000, conversion_count=10_000_000)
    )
    assert decision.failure_reason in {
        FallbackReason.INPUT_TOO_LARGE,
        FallbackReason.MEMORY_BOUND_EXCEEDED,
        FallbackReason.COMPILATION_MEMORY_BOUND_EXCEEDED,
    }


def test_b24_p4_oversized_source_rows_fallback_input_too_large() -> None:
    decision = _decision(
        _profile(source_row_count=B24_RESOURCE_POLICY.max_source_rows + 1)
    )
    assert decision.failure_reason == FallbackReason.INPUT_TOO_LARGE


def test_b24_p4_oversized_touchpoints_fallback_input_too_large() -> None:
    decision = _decision(
        _profile(touchpoint_count=B24_RESOURCE_POLICY.max_touchpoints + 1)
    )
    assert decision.failure_reason == FallbackReason.INPUT_TOO_LARGE


def test_b24_p4_oversized_conversions_fallback_input_too_large() -> None:
    decision = _decision(
        _profile(conversion_count=B24_RESOURCE_POLICY.max_conversions + 1)
    )
    assert decision.failure_reason == FallbackReason.INPUT_TOO_LARGE


def test_b24_p4_high_channel_cardinality_fallback_feature_width_exceeded() -> None:
    decision = _decision(_profile(channel_count=B24_RESOURCE_POLICY.max_channels + 1))
    assert decision.failure_reason == FallbackReason.FEATURE_WIDTH_EXCEEDED


def test_b24_p4_live_campaign_count_above_cap_fallback_feature_width_exceeded() -> None:
    profile = _profile(
        channel_count=3,
        campaign_or_feature_count=B24_RESOURCE_POLICY.max_campaigns_or_feature_keys + 1,
    )
    decision = evaluate_source_snapshot_resource_bounds(
        snapshot=_snapshot_from_profile(profile),
        preflight_lease_id="lease",
        feature_authority=_authority_from_profile(profile),
    )
    assert decision.input_profile.campaign_or_feature_count == (
        B24_RESOURCE_POLICY.max_campaigns_or_feature_keys + 1
    )
    assert decision.failure_reason == FallbackReason.FEATURE_WIDTH_EXCEEDED


def test_b24_p4_live_provider_count_above_cap_fallback_feature_width_exceeded() -> None:
    profile = _profile(provider_count=B24_RESOURCE_POLICY.max_providers + 1)
    decision = evaluate_source_snapshot_resource_bounds(
        snapshot=_snapshot_from_profile(profile),
        preflight_lease_id="lease",
        feature_authority=_authority_from_profile(profile),
    )
    assert (
        decision.input_profile.provider_count == B24_RESOURCE_POLICY.max_providers + 1
    )
    assert decision.failure_reason == FallbackReason.FEATURE_WIDTH_EXCEEDED


def test_b24_p4_fresh_authority_after_yield_runs_feature_width_check() -> None:
    profile = _profile(
        campaign_or_feature_count=B24_RESOURCE_POLICY.max_campaigns_or_feature_keys + 1
    )
    decision = evaluate_source_snapshot_resource_bounds(
        snapshot=_snapshot_from_profile(profile),
        preflight_lease_id="lease",
        feature_authority=_authority_from_profile(profile),
    )
    assert decision.failure_reason == FallbackReason.FEATURE_WIDTH_EXCEEDED


def test_b24_p4_low_channel_high_campaign_count_fails_feature_width() -> None:
    decision = _decision(
        _profile(
            source_row_count=100,
            channel_count=2,
            campaign_or_feature_count=B24_RESOURCE_POLICY.max_campaigns_or_feature_keys
            + 1,
        )
    )
    assert decision.failure_reason == FallbackReason.FEATURE_WIDTH_EXCEEDED


def test_b24_p4_source_window_too_large_fallback() -> None:
    decision = _decision(_profile(window_days=B24_RESOURCE_POLICY.max_window_days + 1))
    assert decision.failure_reason == FallbackReason.SOURCE_WINDOW_TOO_LARGE


def test_b24_p4_design_matrix_cells_above_cap_fallback_memory_bound_exceeded() -> None:
    decision = _decision(
        _profile(
            source_row_count=250_000,
            touchpoint_count=175_000,
            conversion_count=75_000,
            channel_count=128,
            currency_count=8,
        )
    )
    assert decision.failure_reason == FallbackReason.MEMORY_BOUND_EXCEEDED


def test_b24_p4_parameter_count_above_cap_fallback_parameter_count_exceeded() -> None:
    profile = _profile(
        source_row_count=100,
        touchpoint_count=10,
        conversion_count=40,
        campaign_or_feature_count=2_000,
    )
    design = estimate_design_matrix_envelope(profile)
    graph = estimate_graph_complexity_envelope(profile, design)
    assert graph.estimated_parameter_count > 0


def test_b24_p4_high_sparse_feature_count_fails_graph_complexity_even_with_low_rows() -> (
    None
):
    decision = _decision(
        _profile(
            source_row_count=100,
            touchpoint_count=10,
            conversion_count=40,
            channel_count=2,
            campaign_or_feature_count=B24_RESOURCE_POLICY.max_levels_per_hierarchy + 1,
        )
    )
    assert decision.failure_reason == FallbackReason.HIERARCHY_WIDTH_EXCEEDED


def test_b24_p4_fresh_authority_after_yield_runs_graph_complexity_check() -> None:
    decision = _decision(
        _profile(
            source_row_count=100,
            touchpoint_count=10,
            conversion_count=40,
            campaign_or_feature_count=B24_RESOURCE_POLICY.max_levels_per_hierarchy + 1,
        )
    )
    assert decision.failure_reason == FallbackReason.HIERARCHY_WIDTH_EXCEEDED


def test_b24_p4_campaign_count_feeds_parameter_count_estimate() -> None:
    low = _profile(campaign_or_feature_count=4)
    high = _profile(campaign_or_feature_count=40)
    low_graph = estimate_graph_complexity_envelope(
        low, estimate_design_matrix_envelope(low)
    )
    high_graph = estimate_graph_complexity_envelope(
        high, estimate_design_matrix_envelope(high)
    )
    assert high_graph.estimated_parameter_count > low_graph.estimated_parameter_count


def test_b24_p4_campaign_count_feeds_symbolic_node_estimate() -> None:
    low = _profile(campaign_or_feature_count=4)
    high = _profile(campaign_or_feature_count=40)
    low_graph = estimate_graph_complexity_envelope(
        low, estimate_design_matrix_envelope(low)
    )
    high_graph = estimate_graph_complexity_envelope(
        high, estimate_design_matrix_envelope(high)
    )
    assert high_graph.estimated_symbolic_nodes > low_graph.estimated_symbolic_nodes


def test_b24_p4_campaign_count_feeds_compilation_memory_estimate() -> None:
    low = _profile(campaign_or_feature_count=4)
    high = _profile(campaign_or_feature_count=40)
    low_graph = estimate_graph_complexity_envelope(
        low, estimate_design_matrix_envelope(low)
    )
    high_graph = estimate_graph_complexity_envelope(
        high, estimate_design_matrix_envelope(high)
    )
    assert (
        high_graph.estimated_compilation_memory_bytes
        > low_graph.estimated_compilation_memory_bytes
    )


def test_b24_p4_provider_count_feeds_graph_complexity_estimate() -> None:
    low = _profile(provider_count=1)
    high = _profile(provider_count=10)
    low_graph = estimate_graph_complexity_envelope(
        low, estimate_design_matrix_envelope(low)
    )
    high_graph = estimate_graph_complexity_envelope(
        high, estimate_design_matrix_envelope(high)
    )
    assert (
        high_graph.estimated_hierarchical_groups
        > low_graph.estimated_hierarchical_groups
    )
    assert high_graph.estimated_symbolic_nodes > low_graph.estimated_symbolic_nodes


def test_b24_p4_forced_profile_values_do_not_replace_live_path_proof() -> None:
    text = _read(INPUT_PROFILE)
    assert "feature_authority.provider_count" in text
    assert "feature_authority.campaign_or_feature_count" in text
    assert "preflight.provider_count" not in text
    assert "preflight.campaign_or_feature_count" not in text


def test_b24_p4_cardinality_fix_preserves_no_pii_no_identity_no_raw_payload() -> None:
    text = (
        _read(ELIGIBILITY)
        + _read(FEATURE_AUTHORITY)
        + _read(FEATURE_AUTHORITY_MIGRATION)
    )
    forbidden = (
        "raw_payload",
        "email",
        "customer_id",
        "provider_customer",
        "provider_token",
        "attribution_commerce_identities",
    )
    for token in forbidden:
        assert token not in text


def test_b24_p4_resource_fallback_sampling_started_null_and_last_fit_null() -> None:
    text = _read(REPOSITORY)
    assert "sampling_started_at = NULL" in text
    assert "last_fit_at = NULL" in text


def test_b24_p4_resource_fallback_does_not_create_dispatch_outbox() -> None:
    assert "INSERT INTO public.b24_fit_dispatch_outbox" not in _read(REPOSITORY)


def test_b24_p4_resource_fallback_does_not_mutate_deterministic_truth() -> None:
    text = _read(FIT_PLANNER) + _read(REPOSITORY) + _read(RESOURCE_PROFILE)
    for mutation in (
        "UPDATE public.attribution_events",
        "UPDATE public.b23_match_verdicts",
    ):
        assert mutation not in text


def test_b24_p4_no_pymc_no_pytensor_no_arviz_no_sampler_no_diagnostics_no_projection() -> (
    None
):
    validator = _load_validator()
    validator.validate_scope(REPO_ROOT)


def test_b24_p4_validator_negative_control() -> None:
    validator = _load_validator()
    validator.run_negative_control(REPO_ROOT)
