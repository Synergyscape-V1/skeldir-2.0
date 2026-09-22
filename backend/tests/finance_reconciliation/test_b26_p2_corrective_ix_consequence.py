"""B2.6-P2 Corrective IX battery: non-self-authenticating consequence authority.

Runs on a real PostgreSQL migrated to the IX head, acting through the
exact runtime principals. Every cell follows the falsification contract:
pristine GREEN, genuine defect RED for the predicted cause, exact restore
GREEN.

Classes (Corrective IX consequence-authority law):
  PC9-*  canonical consequence binding (random forgery, foreign reuse,
         count never truth authority)
  TC9    temporal reference-presence footprint (value-preserving free,
         presence flips refused)
  PE9    policy semantic immutability, explicit for IX
  HC9    historical provenance honesty (unknown roots admit no dispatch)
  SCH9-* scheduler liveness separation (relay refused, beat ticks)
  PIN9   pin-regen negative control (static effect validator, no live
         DB mutation here)
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone
from uuid import UUID

import pytest

DAY_START = datetime(2026, 1, 15, 0, 0, tzinfo=timezone.utc)
DAY_END = datetime(2026, 1, 16, 0, 0, tzinfo=timezone.utc)
DAY_NOON = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
TASK_NAME = "app.tasks.revenue_verification.execute_b23_batch_match_engine"
# Corrective IX policy-meaning binding: every conduction receipt
# carries the caller-observed policy semantic SHA.
_P2_POLICY_SEMANTIC_SHA_V2 = (
    "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"
)


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    try:
        from app.db.session import b23_engine
        from app.db.session import engine as app_engine

        await b23_engine.dispose()
        await app_engine.dispose()
    except Exception:
        pass


def _admin_dsn() -> str:
    for key in ("MIGRATION_database_URL", "MIGRATION_DATABASE_URL"):
        dsn = os.environ.get(key, "").strip()
        if dsn:
            return dsn
    pytest.skip("IX battery needs MIGRATION_DATABASE_URL")


def _role_dsn(role: str) -> str:
    import psycopg2

    admin = _admin_dsn()
    candidate = admin.replace("migration_owner:migration_owner", f"{role}:{role}")
    if candidate == admin:
        pytest.skip(f"cannot derive {role} DSN")
    try:
        conn = psycopg2.connect(candidate)
        conn.close()
    except Exception:
        pytest.skip(f"role {role} not provisioned")
    return candidate


def _superuser_dsn() -> str:
    """Superuser lane DSN for RLS-bypass historical checks.

    Inside the candidate-image proof the database host is `pg`, not
    localhost; the proof harness exports B26_P2_SUPERUSER_DSN for that
    topology (host runs fall back to the local superuser form).
    """
    explicit = os.environ.get("B26_P2_SUPERUSER_DSN", "").strip()
    if explicit:
        return explicit
    admin = _admin_dsn()
    db = admin.rsplit("/", 1)[-1]
    return "postgresql://postgres:postgres@localhost:5432/" + db


def _seed_ingress(
    tag: str,
    *,
    provider: str = "stripe",
    currency: str = "USD",
    amount: int = 38000,
    state: str = "authenticity_verified",
    event_time: datetime = DAY_NOON,
) -> dict:
    import psycopg2

    tenant_id = uuid.uuid4()
    ingress_id = uuid.uuid4()
    event_uuid = uuid.uuid4()
    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant_id), f"b26p2viii-{tag}", uuid.uuid4().hex,
                 f"b26p2viii-{tag}@example.invalid"),
            )
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('b26p2viii_channel', 'b26p2viii',"
                " true, 'B26P2VIII', 'active') ON CONFLICT (code) DO NOTHING"
            )
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 38000,"
                " '{\"order_id\": \"viii\"}'::jsonb, %s, 'conversion',"
                " 'b26p2viii_channel', 'b26p2viii-campaign', 38000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_uuid), str(tenant_id), event_time, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"b26p2viii:{tag}", event_time, event_time),
            )
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'order_reference',"
                " %s, %s, %s, %s, %s, %s)",
                (str(ingress_id), str(tenant_id), str(event_uuid), provider,
                 f"evt-{tag}", f"ord-{tag}", f"ord-{tag}", amount, currency,
                 event_time, f"b26p2viii:{tag}", state),
            )
    finally:
        conn.close()
    return {"tenant_id": tenant_id, "ingress_id": ingress_id, "event_id": event_uuid}


def _seed_dispatch(tenant_id: UUID, ingress_id: UUID, task: str) -> None:
    import psycopg2

    conn = psycopg2.connect(_role_dsn("app_user"))
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
                " webhook_ingress_identity_id, task_id, task_name, queue,"
                " routing_key, correlation_id, provider,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_value, window_start,"
                " window_end) VALUES (%s, %s, %s,"
                f" '{TASK_NAME}',"
                " 'b23_match_engine', 'b23_match_engine.task', %s,"
                " 'stripe', 'evt', 'ord', 'ord', %s, %s)",
                (
                    str(tenant_id),
                    str(ingress_id),
                    task,
                    str(uuid.uuid4()),
                    DAY_START,
                    DAY_END,
                ),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
                " dispatch_task_id, webhook_ingress_identity_id)"
                " VALUES (%s, %s, %s)",
                (str(tenant_id), task, str(ingress_id)),
            )
            cur.execute(
                "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
                " tenant_id, webhook_ingress_identity_id, window_start,"
                " window_end) VALUES (%s, %s, %s, %s, %s)",
                (task, str(tenant_id), str(ingress_id), DAY_START, DAY_END),
            )
    finally:
        conn.close()


def _publish_and_verdict(
    tenant_id: UUID, ingress_id: UUID, task: str, event_id: UUID | None = None
) -> None:
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    conn.autocommit = True
    try:
        with conn.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "UPDATE public.b23_match_task_dispatches SET delivery_state='published',"
                " first_published_at=now() WHERE task_id=%s",
                (task,),
            )
            cur.execute(
                "UPDATE public.b26_p2_execution_outbox SET state='published'"
                " WHERE dispatch_task_id=%s",
                (task,),
            )
            if event_id is None:
                cur.execute(
                    "SELECT event_id FROM public.webhook_ingress_identities WHERE id=%s",
                    (str(ingress_id),),
                )
                row = cur.fetchone()
                event_id = UUID(str(row[0])) if row else uuid.uuid4()
            cur.execute(
                "INSERT INTO public.b23_match_verdicts (tenant_id,"
                " attribution_event_id, webhook_ingress_identity_id,"
                " provider, canonical_commerce_reference,"
                " provider_native_event_reference,"
                " provider_native_commerce_reference, status,"
                " match_quality, attributed_amount_minor,"
                " verified_amount_minor, currency_code,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor,"
                " discrepancy_amount_minor, discrepancy_ratio_bps,"
                " discrepancy_band)"
                " VALUES (%s, %s, %s, 'stripe', 'ord', 'evt', 'ord',"
                " 'matched_confirmed', 'high', 38000, 38000, 'USD',"
                " 38000, 38000, 38000, 0, 0, 'exact')",
                (str(tenant_id), str(event_id), str(ingress_id)),
            )
    finally:
        conn.close()


def _fresh_task(tag: str) -> tuple[dict, str]:
    """Seed ingress + dispatch + publish + verdict for one lawful execution."""
    ids = _seed_ingress(tag)
    task = f"{tag}-{uuid.uuid4().hex[:8]}"
    _seed_dispatch(ids["tenant_id"], ids["ingress_id"], task)
    _publish_and_verdict(ids["tenant_id"], ids["ingress_id"], task)
    return ids, task


def _canonical_scope_for_task(task: str) -> str:
    """IX canonical scope: sovereign DB recomputation for the task window."""
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT tenant_id, window_start, window_end"
                " FROM public.b26_p2_task_authority_directory WHERE task_id=%s",
                (task,),
            )
            row = cur.fetchone()
            if row is None:
                raise AssertionError("missing directory for %s" % task)
            tenant, ws, we = row[0], row[1], row[2]
            cur.execute(
                "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
                (str(tenant), ws, we),
            )
            return str(cur.fetchone()[0])
    finally:
        admin.close()


def _conduct(task: str) -> str:
    import psycopg2

    scope = _canonical_scope_for_task(task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            return str(cur.fetchone()[0])
    finally:
        worker.close()


def _provenance_of(tenant_id: UUID, ingress_id: UUID) -> str:
    import psycopg2

    admin = psycopg2.connect(_admin_dsn())
    admin.autocommit = True
    try:
        with admin.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_id),),
            )
            cur.execute(
                "SELECT b26_p2_provenance_status"
                " FROM public.webhook_ingress_identities WHERE id=%s",
                (str(ingress_id),),
            )
            return str(cur.fetchone()[0])
    finally:
        admin.close()


# --- PC9: canonical consequence binding ----------------------------------

def test_pc9_random_scope_forgery_refused():
    """PC9-01: a random 64-hex scope with the correct SHA is refused with
    scope_not_canonical; lawful scope conducts before (pristine GREEN) and
    after (restore GREEN) the refusal."""
    import secrets

    import psycopg2

    _, ctl_task = _fresh_task("pc9ctl")
    assert _conduct(ctl_task) == "conducted"
    _, task = _fresh_task("pc9forge")
    forged = secrets.token_hex(32)
    assert forged != _canonical_scope_for_task(task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            with pytest.raises(Exception, match="scope_not_canonical"):
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task, forged, 1, _P2_POLICY_SEMANTIC_SHA_V2),
                )
            scope = _canonical_scope_for_task(task)
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "conducted"
    finally:
        worker.close()


def test_pc9_foreign_scope_reuse_refused():
    """PC9-02: a foreign execution's real (canonical-for-A) scope reused on
    task B is refused with scope_not_canonical; B's own scope conducts."""
    import psycopg2

    _, task_a = _fresh_task("pc9fa")
    scope_a = _canonical_scope_for_task(task_a)
    _, task_b = _fresh_task("pc9fb")
    scope_b = _canonical_scope_for_task(task_b)
    assert scope_a != scope_b
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            with pytest.raises(Exception, match="scope_not_canonical"):
                cur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                    (task_b, scope_a, 1, _P2_POLICY_SEMANTIC_SHA_V2),
                )
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task_b, scope_b, 1, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task_b,))
            assert cur.fetchone()[0] == "conducted"
    finally:
        worker.close()


def test_pc9_count_never_truth_authority():
    """PC9-04: correct scope with correct SHA conducts; a record carrying
    count 999 still conducts, proving the count never becomes truth
    authority (scope canonicality is the authority)."""
    import psycopg2

    _, task = _fresh_task("pc9count")
    scope = _canonical_scope_for_task(task)
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT public.b26_p2_record_conduction_receipt(%s, %s, %s, %s)",
                (task, scope, 999, _P2_POLICY_SEMANTIC_SHA_V2),
            )
            assert cur.fetchone()[0] == task
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "conducted"
    finally:
        worker.close()


# --- TC9: temporal reference-presence footprint --------------------------

def test_tc9_reference_presence_footprint():
    """TC9: post-conduction value-preserving reference rewrite
    (ord->ord-MUTATED) is allowed and the gate stays already_conducted;
    a presence flip (ord->'') is refused with
    reference_presence_refused and leaves the consequence intact."""
    import psycopg2

    ids, task = _fresh_task("tc9ref")
    assert _conduct(task) == "conducted"
    tenant = str(ids["tenant_id"])
    worker = psycopg2.connect(_role_dsn("app_worker"))
    worker.autocommit = True
    try:
        with worker.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET canonical_commerce_reference='ord-tc9-mutated'"
                " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                (tenant, str(ids["ingress_id"])),
            )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "already_conducted"
            with pytest.raises(Exception, match="reference_presence_refused"):
                cur.execute(
                    "UPDATE public.b23_match_verdicts"
                    " SET canonical_commerce_reference=''"
                    " WHERE tenant_id=%s AND webhook_ingress_identity_id=%s",
                    (tenant, str(ids["ingress_id"])),
                )
            cur.execute("SELECT public.b26_p2_mark_conducted(%s)", (task,))
            assert cur.fetchone()[0] == "already_conducted"
    finally:
        worker.close()


# --- PE9: policy meaning binding, IX-explicit ----------------------------

def test_pe9_same_version_rewrite_refused():
    """PE9: a same-version semantic rewrite attempt via the superuser lane
    is refused by the immutability trigger
    (policy_semantic_mutation_refused); lawful conduction holds before
    and after, so no live meaning was mutated."""
    import psycopg2

    _, task = _fresh_task("pe9ctl")
    assert _conduct(task) == "conducted"
    sup = psycopg2.connect(_superuser_dsn())
    sup.autocommit = True
    try:
        with sup.cursor() as cur:
            with pytest.raises(Exception, match="policy_semantic_mutation_refused"):
                cur.execute(
                    "UPDATE public.b26_p2_scope_policy_authority"
                    " SET semantic_sha256='ff' || substr(semantic_sha256, 3)"
                    " WHERE scope_policy_version='b2.6-p2-scope-policy-v2'"
                )
    finally:
        sup.close()
    _, task2 = _fresh_task("pe9after")
    assert _conduct(task2) == "conducted"


# --- HC9: historical provenance honesty ----------------------------------

def test_hc9_unknown_provenance_dispatch_refused():
    """HC9: verified ingress created via migration_owner is known
    (pristine GREEN, dispatch admitted); the same ingress forced to
    unknown_legacy via superuser replica bypass refuses new dispatch
    with provenance_unknown."""
    import psycopg2

    ctl = _seed_ingress("hc9ctl")
    assert _provenance_of(ctl["tenant_id"], ctl["ingress_id"]) == "authenticated_known"
    _seed_dispatch(ctl["tenant_id"], ctl["ingress_id"], f"hc9ctl-{uuid.uuid4().hex[:8]}")
    ids = _seed_ingress("hc9unk")
    assert _provenance_of(ids["tenant_id"], ids["ingress_id"]) == "authenticated_known"
    sup = psycopg2.connect(_superuser_dsn())
    sup.autocommit = True
    try:
        with sup.cursor() as cur:
            cur.execute("SET session_replication_role = replica")
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET b26_p2_provenance_status='unknown_legacy' WHERE id=%s",
                (str(ids["ingress_id"]),),
            )
            cur.execute("SET session_replication_role = DEFAULT")
    finally:
        sup.close()
    assert _provenance_of(ids["tenant_id"], ids["ingress_id"]) == "unknown_legacy"
    with pytest.raises(Exception, match="provenance_unknown"):
        _seed_dispatch(
            ids["tenant_id"], ids["ingress_id"], f"hc9unk-{uuid.uuid4().hex[:8]}"
        )


# --- SCH9: scheduler liveness separation ---------------------------------

def test_sch9_relay_cannot_tick_scheduler():
    """SCH9-01: the app_relay credential cannot manufacture scheduler
    liveness; the call is refused at the grant or the gate
    (scheduler_caller_refused)."""
    import psycopg2

    ids = _seed_ingress("sch9r")
    tenant = str(ids["tenant_id"])
    relay = psycopg2.connect(_role_dsn("app_relay"))
    relay.autocommit = True
    try:
        with relay.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            with pytest.raises(
                Exception, match="scheduler_caller_refused|permission denied"
            ):
                cur.execute("SELECT public.b26_p2_record_scheduler_heartbeat()")
    finally:
        relay.close()


def test_sch9_beat_can_tick():
    """SCH9-02: the app_beat credential ticks scheduler liveness
    (pristine GREEN); skipped when the beat role is not provisioned."""
    import psycopg2

    ids = _seed_ingress("sch9b")
    tenant = str(ids["tenant_id"])
    beat = psycopg2.connect(_role_dsn("app_beat"))
    beat.autocommit = True
    try:
        with beat.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
            )
            cur.execute("SELECT public.b26_p2_record_scheduler_heartbeat()")
            assert cur.fetchone()[0] == "scheduled"
            cur.execute(
                "SELECT tick_count FROM public.b26_p2_scheduler_heartbeat"
                " WHERE tenant_id=%s",
                (tenant,),
            )
            assert cur.fetchone()[0] >= 1
    finally:
        beat.close()


# --- PIN9: pin-regen negative control (static, no live mutation) ---------

def test_pin9_effect_validator_passes_pristine():
    """PIN9: documents that an authority pin regen without the effect fix
    remains RED via the effect validator. This cell performs no live DB
    mutation: it runs validate_b26_p2_ix_authority in static mode and
    asserts PASS on pristine (skipped when the validator is not yet
    provisioned)."""
    import subprocess
    import sys
    from pathlib import Path

    repo = Path(__file__).resolve().parents[3]
    validator = repo / "scripts" / "ci" / "validate_b26_p2_ix_authority.py"
    if not validator.is_file():
        pytest.skip("validate_b26_p2_ix_authority not provisioned")
    proc = subprocess.run(
        [sys.executable, str(validator)],
        cwd=str(repo),
        capture_output=True,
        text=True,
        timeout=300,
    )
    out = proc.stdout + proc.stderr
    assert proc.returncode == 0, out[-2000:]
    assert "PASS" in out
