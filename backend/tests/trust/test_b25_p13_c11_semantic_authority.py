"""C11 semantic identity, capability separation, and lineage falsifiers."""

from __future__ import annotations

import os
import json
from copy import deepcopy
from types import SimpleNamespace
from uuid import uuid4

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.pool import NullPool

from pathlib import Path

from app.bayesian.compiledir_reaper import create_compiledir_lease
from app.bayesian.runtime_policy import resolved_runtime_authority_from_env

#: Repository backend root, resolved from this file rather than the
#: environment: tests/trust/<file> -> backend.
_BACKEND_ROOT = Path(__file__).resolve().parents[2]
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    run_supervised_sampler,
    sampler_child_command,
)
from app.inference_policy_registry import (
    CONFIDENCE_POLICY_VERSION,
    CONFIDENCE_SEMANTICS_VERSION,
    CURRENT_POLICY_BUNDLE_HASH,
    PolicyRegistryError,
    current_manifest,
    current_policy_tuple,
    semantic_digest,
    validate_policy_provenance,
)
from app.trust.builder import _inference_provenance
from tests.test_b24_p9_postgres_runtime import (
    END,
    START,
    _claim_test_dispatch_lease,
    _set_tenant_context,
)


def _provenance(**overrides: object) -> dict[str, object]:
    value: dict[str, object] = {
        "policy_bundle_hash": CURRENT_POLICY_BUNDLE_HASH,
        **current_policy_tuple(),
    }
    value.update(overrides)
    return value


def test_c11_policy_identity_is_sensitive_to_each_governed_semantic_family() -> None:
    original = current_manifest()
    mutations = (
        ("sampling_policy", "draws_per_chain", 999),
        ("diagnostic_policy", "r_hat_max_threshold", 1.02),
        ("runtime_policy", "celery_hard_time_limit_seconds", 301),
    )
    for component, field, hostile in mutations:
        mutated = deepcopy(original)
        mutated["components"][component]["semantics"][field] = hostile
        assert semantic_digest(mutated) != CURRENT_POLICY_BUNDLE_HASH


def test_c11_tuple_hash_and_registry_rewrites_fail_closed_before_trust() -> None:
    with pytest.raises(PolicyRegistryError, match="tuple_mismatch"):
        validate_policy_provenance(
            _provenance(runtime_policy_version="b24-p5-runtime-policy-hostile")
        )
    with pytest.raises(PolicyRegistryError, match="unknown_or_semantically_rewritten"):
        validate_policy_provenance(_provenance(policy_bundle_hash="f" * 64))

    projection = SimpleNamespace(
        policy_bundle_hash="f" * 64,
        inference_profile_version=current_policy_tuple()["inference_profile_version"],
        runtime_policy_version=current_policy_tuple()["runtime_policy_version"],
        sampling_policy_version=current_policy_tuple()["sampling_policy_version"],
        diagnostic_policy_version=current_policy_tuple()["diagnostic_policy_version"],
        authorized_chains=4,
        observed_chains=4,
        authorized_posterior_draws_total=4000,
        observed_posterior_draws_total=4000,
        decision=SimpleNamespace(
            confidence_policy_version=CONFIDENCE_POLICY_VERSION,
            confidence_semantics_version=CONFIDENCE_SEMANTICS_VERSION,
        ),
    )
    assert _inference_provenance(projection) is None


def test_c11_worker_and_sampler_runtime_record_covers_all_authority_dimensions() -> (
    None
):
    source = {
        "B24_BAYESIAN_WORKER_CONCURRENCY": "1",
        "B24_PYMC_CHAINS": "4",
        "B24_PYMC_CORES": "1",
        "B24_BLAS_TOTAL_THREADS": "1",
        "B24_SAMPLER_SUPERVISOR_DEADLINE_S": "240",
        "BAYESIAN_TASK_SOFT_TIME_LIMIT_S": "270",
        "BAYESIAN_TASK_TIME_LIMIT_S": "300",
    }
    record = resolved_runtime_authority_from_env(source)
    assert set(record) == {
        "runtime_policy_version",
        "chains",
        "cores",
        "blas_cores",
        "worker_concurrency",
        "sampler_supervisor_deadline_seconds",
        "celery_soft_time_limit_seconds",
        "celery_hard_time_limit_seconds",
    }
    hostile = {**source, "BAYESIAN_TASK_TIME_LIMIT_S": "301"}
    assert resolved_runtime_authority_from_env(hostile) != record


def test_c11_sampler_child_refuses_worker_runtime_drift_before_sampling(
    tmp_path,
) -> None:
    input_path = tmp_path / "input.json"
    output_path = tmp_path / "output.json"
    marker_path = tmp_path / "markers.jsonl"
    worker_authority = resolved_runtime_authority_from_env()
    worker_authority["celery_hard_time_limit_seconds"] = 301
    input_path.write_text(
        json.dumps(
            {
                "execution_id": "c11-runtime-drift",
                "fit_id": str(uuid4()),
                "tenant_id": str(uuid4()),
                "source_snapshot_hash": "a" * 64,
                "worker_runtime_authority": worker_authority,
            }
        ),
        encoding="utf-8",
    )
    lease = create_compiledir_lease(
        execution_id="c11-runtime-drift", worker_id="c11-test-worker"
    )
    env = build_child_env_for_lease(
        lease,
        source_env={
            **os.environ,
            # Explicit rather than ambient, matching every other child-spawning
            # proof in this repository. The bootstrap runs as a script, so
            # sys.path[0] is the bayesian package directory and the `app`
            # package is only importable via PYTHONPATH; inheriting whatever a
            # given CI job happened to export made this proof depend on the
            # harness instead of on the system it is testing.
            "PYTHONPATH": str(_BACKEND_ROOT),
            "B24_STAGE_MARKER_PATH": str(marker_path),
        },
    )
    result = run_supervised_sampler(
        sampler_child_command(
            mode="real-fit", input_path=input_path, output=output_path
        ),
        deadline_seconds=20,
        env=env,
        compiledir_lease=lease,
    )
    assert result.returncode != 0
    assert not output_path.exists()
    # A missing marker file means the child died before it could record why.
    # Reporting the child's own stderr here is the difference between "the
    # refusal did not happen" and "we cannot tell what happened", and only the
    # first of those is a finding about the system under test.
    assert marker_path.exists(), (
        "sampler child emitted no stage markers; it exited "
        f"{result.returncode} before reaching the authority check. "
        f"stderr={getattr(result.stderr, 'text', result.stderr)!r} "
        f"stdout={getattr(result.stdout, 'text', result.stdout)!r}"
    )
    stages = [
        json.loads(line)["stage"]
        for line in marker_path.read_text(encoding="utf-8").splitlines()
    ]
    assert stages == ["input_loaded", "runtime_authority_rejected"]
    assert "sampling_started" not in stages


db_proof = pytest.mark.skipif(
    os.getenv("SKELDIR_B25_P13_C11_DB_PROOF") != "1",
    reason="B2.5-P13 C11 PostgreSQL proof is opt-in locally",
)


def _engine(url: str):
    return create_engine(url, poolclass=NullPool, future=True)


def _runtime_urls() -> tuple[str, str, str]:
    worker = os.environ["DATABASE_URL"]
    publisher = os.environ["B24_DISPATCH_PUBLISHER_DATABASE_URL"]
    migration = os.environ["MIGRATION_DATABASE_URL"]
    return worker, publisher, migration


def _seed_fit(conn, *, tenant_id, fit_id, bundle_hash: str, suffix: str) -> None:
    _set_tenant_context(conn, tenant_id)
    conn.execute(
        text(
            """
            INSERT INTO public.bayesian_model_fits (
                tenant_id, id, model_type, model_version,
                source_window_start, source_window_end, source_snapshot_hash,
                source_read_started_at, source_read_completed_at,
                status, eligibility_status, data_completeness_status,
                fallback_applied, max_runtime_seconds, max_samples, max_cores,
                inference_profile_version, runtime_policy_version,
                sampling_policy_version, diagnostic_policy_version,
                policy_bundle_hash, authorized_chains,
                authorized_posterior_draws_total
            ) VALUES (
                :tenant_id, :fit_id, 'bayesian_attribution_confidence',
                'b24-p6-real-fit-v1', :start, :end, :snapshot,
                now(), now(), 'queued', 'eligible', 'complete', false,
                240, 8000, 1, :profile, :runtime, :sampling, :diagnostic,
                :bundle, 4, 4000
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "fit_id": str(fit_id),
            "start": START,
            "end": END,
            "snapshot": semantic_digest({"fit": str(fit_id), "suffix": suffix}),
            "profile": f"profile-{suffix}",
            "runtime": f"runtime-{suffix}",
            "sampling": f"sampling-{suffix}",
            "diagnostic": f"diagnostic-{suffix}",
            "bundle": bundle_hash,
        },
    )


def _seed_dispatch(conn, *, tenant_id, fit_id) -> None:
    _set_tenant_context(conn, tenant_id)
    conn.execute(
        text(
            """
            INSERT INTO public.b24_fit_dispatch_outbox (
                tenant_id, id, fit_id, dispatch_key, task_name, attempt_id,
                payload_hash, status, next_attempt_at, next_recovery_at
            ) VALUES (
                :tenant_id, :id, :fit_id, :key,
                'app.tasks.bayesian.execute_fit_intent', :attempt,
                :payload, 'pending', now(), now() + interval '1 hour'
            )
            """
        ),
        {
            "tenant_id": str(tenant_id),
            "id": str(uuid4()),
            "fit_id": str(fit_id),
            "key": f"c11:{tenant_id}:{fit_id}",
            "attempt": str(uuid4()),
            "payload": "a" * 64,
        },
    )


@pytest.mark.integration
@db_proof
def test_c11_publisher_identity_is_separate_and_least_privilege(
    test_tenant_pair,
) -> None:
    worker_url, publisher_url, _ = _runtime_urls()
    tenant_a, tenant_b = test_tenant_pair
    worker = _engine(worker_url)
    publisher = _engine(publisher_url)
    fit_a, fit_b = uuid4(), uuid4()
    try:
        with worker.begin() as conn:
            _seed_fit(
                conn, tenant_id=tenant_a, fit_id=fit_a, bundle_hash="1" * 64, suffix="A"
            )
            _seed_dispatch(conn, tenant_id=tenant_a, fit_id=fit_a)
        with worker.begin() as conn:
            _seed_fit(
                conn, tenant_id=tenant_b, fit_id=fit_b, bundle_hash="2" * 64, suffix="B"
            )
            _seed_dispatch(conn, tenant_id=tenant_b, fit_id=fit_b)

        with worker.begin() as conn:
            _set_tenant_context(conn, tenant_a)
            conn.execute(
                text(
                    "SELECT set_config('app.b24_initial_dispatch_publisher','on',true)"
                )
            )
            assert (
                conn.execute(
                    text("SELECT count(*) FROM public.b24_fit_dispatch_outbox")
                ).scalar_one()
                == 1
            )
            with pytest.raises(ProgrammingError):
                conn.execute(text("SELECT public.b24_assert_dispatch_publisher()"))
        with worker.begin() as conn:
            with pytest.raises(ProgrammingError):
                conn.execute(
                    text(
                        "UPDATE public.b24_inference_policy_registry "
                        "SET identity_scheme='hostile'"
                    )
                )
        with worker.begin() as conn:
            conn.execute(
                text(
                    "SELECT set_config('app.b24_initial_dispatch_publisher','on',true)"
                )
            )
            assert (
                conn.execute(
                    text("SELECT count(*) FROM public.b24_fit_dispatch_outbox")
                ).scalar_one()
                == 0
            )

        with publisher.begin() as conn:
            assert (
                conn.execute(
                    text("SELECT public.b24_assert_dispatch_publisher()")
                ).scalar_one()
                == "app_dispatch_publisher"
            )
            assert (
                conn.execute(
                    text("SELECT count(*) FROM public.b24_fit_dispatch_outbox")
                ).scalar_one()
                >= 2
            )
            with pytest.raises(ProgrammingError):
                with conn.begin_nested():
                    conn.execute(
                        text("SELECT count(*) FROM public.bayesian_model_fits")
                    )
            with pytest.raises(ProgrammingError):
                with conn.begin_nested():
                    conn.execute(text("DELETE FROM public.b24_fit_dispatch_outbox"))
    finally:
        publisher.dispose()
        worker.dispose()


@pytest.mark.integration
@db_proof
def test_c11_available_tuple_hash_mismatch_is_rejected(test_tenant_pair) -> None:
    worker_url, _, _ = _runtime_urls()
    tenant_id, _ = test_tenant_pair
    worker = _engine(worker_url)
    fit_id = uuid4()
    try:
        with worker.begin() as conn:
            _seed_fit(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                bundle_hash="f" * 64,
                suffix="wrong",
            )
            _claim_test_dispatch_lease(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                generation_id=f"c11-mismatch-{uuid4().hex[:16]}",
                assignment_reason="c11_mismatch",
            )
            with pytest.raises(
                DBAPIError, match="b24_available_policy_provenance_unresolvable"
            ):
                conn.execute(
                    text(
                        """
                        UPDATE public.bayesian_model_fits
                        SET confidence_bucket = 'high',
                            confidence_policy_version = :confidence_policy,
                            confidence_semantics_version = :confidence_semantics
                        WHERE tenant_id = :tenant_id AND id = :fit_id
                        """
                    ),
                    {
                        "tenant_id": str(tenant_id),
                        "fit_id": str(fit_id),
                        "confidence_policy": CONFIDENCE_POLICY_VERSION,
                        "confidence_semantics": CONFIDENCE_SEMANTICS_VERSION,
                    },
                )
    finally:
        worker.dispose()


@pytest.mark.integration
@db_proof
def test_c11_replan_lineage_is_complete_atomic_and_runtime_immutable(
    test_tenant_pair,
) -> None:
    worker_url, _, migration_url = _runtime_urls()
    tenant_id, _ = test_tenant_pair
    worker = _engine(worker_url)
    migration = _engine(migration_url)
    fit_id = uuid4()
    bundles = [
        semantic_digest({"c11_test_bundle": n, "fit": str(fit_id)}) for n in range(1, 5)
    ]
    try:
        with migration.begin() as conn:
            for number, bundle in enumerate(bundles, 1):
                conn.execute(
                    text(
                        """
                        INSERT INTO public.b24_inference_policy_registry (
                            policy_bundle_hash, inference_profile_version,
                            runtime_policy_version, sampling_policy_version,
                            diagnostic_policy_version, confidence_policy_version,
                            confidence_semantics_version, semantic_manifest,
                            component_digests
                        ) VALUES (
                            :bundle, :profile, :runtime, :sampling, :diagnostic,
                            :confidence_policy, :confidence_semantics,
                            CAST(:manifest AS jsonb), '{}'::jsonb
                        )
                        """
                    ),
                    {
                        "bundle": bundle,
                        "profile": f"profile-P{number}",
                        "runtime": f"runtime-P{number}",
                        "sampling": f"sampling-P{number}",
                        "diagnostic": f"diagnostic-P{number}",
                        "confidence_policy": CONFIDENCE_POLICY_VERSION,
                        "confidence_semantics": CONFIDENCE_SEMANTICS_VERSION,
                        "manifest": json.dumps({"test_transition": number}),
                    },
                )

        with worker.begin() as conn:
            _seed_fit(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                bundle_hash=bundles[0],
                suffix="P1",
            )
            lease = _claim_test_dispatch_lease(
                conn,
                tenant_id=tenant_id,
                fit_id=fit_id,
                generation_id=f"c11-lineage-{uuid4().hex[:16]}",
                assignment_reason="c11_lineage",
            )
            assert lease.fit_id == fit_id
            for number in range(2, 5):
                conn.execute(
                    text(
                        """
                        UPDATE public.bayesian_model_fits
                        SET superseded_policy_bundle_hash = policy_bundle_hash,
                            policy_bundle_hash = :bundle,
                            inference_profile_version = :profile,
                            runtime_policy_version = :runtime,
                            sampling_policy_version = :sampling,
                            diagnostic_policy_version = :diagnostic,
                            policy_replanned_at = now(),
                            policy_replan_count = policy_replan_count + 1
                        WHERE tenant_id = :tenant_id AND id = :fit_id
                        """
                    ),
                    {
                        "bundle": bundles[number - 1],
                        "profile": f"profile-P{number}",
                        "runtime": f"runtime-P{number}",
                        "sampling": f"sampling-P{number}",
                        "diagnostic": f"diagnostic-P{number}",
                        "tenant_id": str(tenant_id),
                        "fit_id": str(fit_id),
                    },
                )

            # A fit mutation cannot commit without exactly one corresponding
            # transition.  The nested transaction proves both sides roll back.
            with pytest.raises(
                DBAPIError, match="b24_policy_replan_evidence_incomplete"
            ):
                with conn.begin_nested():
                    conn.execute(
                        text(
                            """
                            UPDATE public.bayesian_model_fits
                            SET superseded_policy_bundle_hash = policy_bundle_hash,
                                policy_bundle_hash = :bundle,
                                inference_profile_version = :profile,
                                runtime_policy_version = :runtime,
                                sampling_policy_version = :sampling,
                                diagnostic_policy_version = :diagnostic,
                                policy_replanned_at = now(),
                                policy_replan_count = policy_replan_count + 2
                            WHERE tenant_id = :tenant_id AND id = :fit_id
                            """
                        ),
                        {
                            "bundle": CURRENT_POLICY_BUNDLE_HASH,
                            "profile": current_policy_tuple()[
                                "inference_profile_version"
                            ],
                            "runtime": current_policy_tuple()["runtime_policy_version"],
                            "sampling": current_policy_tuple()[
                                "sampling_policy_version"
                            ],
                            "diagnostic": current_policy_tuple()[
                                "diagnostic_policy_version"
                            ],
                            "tenant_id": str(tenant_id),
                            "fit_id": str(fit_id),
                        },
                    )

        with worker.begin() as conn:
            _set_tenant_context(conn, tenant_id)
            rows = conn.execute(
                text(
                    """
                    SELECT transition_sequence, from_policy_bundle_hash,
                           to_policy_bundle_hash
                    FROM public.b24_fit_policy_replan_lineage
                    WHERE tenant_id = :tenant_id AND fit_id = :fit_id
                    ORDER BY transition_sequence
                    """
                ),
                {"tenant_id": str(tenant_id), "fit_id": str(fit_id)},
            ).all()
            assert rows == [
                (1, bundles[0], bundles[1]),
                (2, bundles[1], bundles[2]),
                (3, bundles[2], bundles[3]),
            ]
            assert (
                conn.execute(
                    text("SELECT public.b24_policy_lineage_complete(:tenant,:fit)"),
                    {"tenant": str(tenant_id), "fit": str(fit_id)},
                ).scalar_one()
                is True
            )
            with pytest.raises(ProgrammingError):
                conn.execute(
                    text(
                        "DELETE FROM public.b24_fit_policy_replan_lineage "
                        "WHERE tenant_id=:tenant AND fit_id=:fit AND transition_sequence=2"
                    ),
                    {"tenant": str(tenant_id), "fit": str(fit_id)},
                )
    finally:
        migration.dispose()
        worker.dispose()
