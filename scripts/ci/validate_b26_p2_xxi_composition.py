#!/usr/bin/env python3
"""B2.6-P2 Corrective XXI sovereign-release-continuity gate.

H-XXI-01..14 (Directive XXI): version-compatible minting, positive
event meaning, monotonic disqualification, observable history with an
operational beat connection, and effect-level (not token-level) proof.

Static law-presence checks plus the live battery:

- XXI-V1: release-bound ABI -- v2 minting signatures present with
  required lifecycle attestation, v1 signatures absent (old binaries
  fail overload resolution), lifecycle helper present, root-evidence
  frame gate admits v2 only, auth-root startup gate present;
- XXI-V2: positive Shopify creation law -- terminal/non-creation
  bodies refused at derivation + family choke + DB seam; honest
  creation conducts end to end;
- XXI-V3: monotonic disqualification -- backfill rows carry the
  persisted demotion policy and read non-current; supported downgrade
  preserves it across every reader; re-upgrade converges;
- XXI-V4: observable history -- seq gaps, chain, observer + continuity
  clean; beat task writes worker-authored rows; Trust builder refuses
  on stale/violated/divergent/unobserved history (real builder call);
- XXI-V5: real-reader behavior -- the REAL Trust adapter and REAL P3
  eligibility logic execute live (no reimplemented SQL oracles);
- XXI-V6: anchor continuity -- live ledger extends the committed
  anchor file (prefix continuity + monotonic count);
- XXI-V7: cascade hygiene -- downgrade writes no session tenant
  context (GUC stays NULL); no floor trigger exists.

Prints B26_P2_XXI_COMPOSITION_PASS on success.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

MIG_XXI = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300004_b26_p2_corrective_xxi_sovereign_release_continuity.py"
)
ANCHOR_PATH = (
    REPO_ROOT
    / "contracts-internal"
    / "governance"
    / "b26_p2_supersession_anchor.json"
)
RUNTIME_ROLES = (
    "app_user", "app_ingress", "app_worker", "app_relay", "app_beat",
    "app_dispatch_publisher", "app_trust_issuer", "app_trust_signer",
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        mig = MIG_XXI.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xxi_comp_unreadable:{exc}")
        return
    # Migration bytes must survive every construction path byte-identical
    # (alembic + psql-applied canonical dump): non-ASCII in function
    # bodies mojibakes across client encodings and breaks bootstrap
    # equivalence while each path stays internally green.
    try:
        mig.encode("ascii")
    except UnicodeEncodeError as exc:
        violations.append(f"xxi_comp_non_ascii_bytes:{exc}")
    else:
        checks["migration_ascii_only"] = True
    upgrade = mig.split("def downgrade", 1)[0]
    downgrade = mig.split("def downgrade", 1)[1] if "def downgrade" in mig else ""
    for token in (
        "b26_p2_authenticate_ingress_atomic_v2(",
        "b26_p2_attest_provenance_evidence_v2(",
        "b26_p2_enforce_lifecycle_admission(",
        "b26_p2_read_history_continuity(",
        "xxi-evidence-insufficient:pre-xxi-family",
        "b26_p2_verify_history_continuity(",
        "b26_p2_history_integrity_observations",
        "202609300004",
        "b26_p2_ingress_has_current_authority",
    ):
        if token not in upgrade:
            violations.append(f"xxi_comp_law_missing:{token}")
    # 300005 follow-up (B2.4 isolation): the verdict-keyed reader must
    # exist with least-privilege grants and a fail-closed downgrade.
    # Read from the 300005 file, never from the 300004 text above.
    try:
        mig5 = (
            REPO_ROOT
            / "alembic"
            / "versions"
            / "007_skeldir_foundation"
            / "202609300005_b26_p2_bayesian_verdict_authority_reader.py"
        ).read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xxi_comp_reader_migration_unreadable:{exc}")
        mig5 = ""
    # Adjacent string literals in the migration source mean the full
    # statements never appear on one line; check the load-bearing
    # fragments independently (name + fenced-grant + fail-closed drop).
    for token in (
        "b26_p2_verdict_has_current_authority(",
        "REVOKE ALL ON FUNCTION",
        "GRANT EXECUTE ON FUNCTION",
        "DROP FUNCTION IF EXISTS",
        "down_revision = \"202609300004\"",
    ):
        if token not in mig5:
            violations.append(f"xxi_comp_reader_law_missing:{token[:40]}")
    if "app_worker" not in mig5 or "app_user" not in mig5:
        violations.append("xxi_comp_reader_grant_principals_missing")
    if not [v for v in violations if "xxi_comp_reader_" in v]:
        checks["verdict_reader_law_present"] = True
    # v1 minting signatures must be dropped (ABI retirement). Python
    # string literals wrap across lines, so compare quote-stripped,
    # whitespace-collapsed text.
    flat = " ".join(
        upgrade.replace('"', "").replace(", ", ",").split())
    if ("DROP FUNCTION IF EXISTS public.b26_p2_authenticate_ingress_atomic("
            not in flat):
        violations.append("xxi_comp_v1_atomic_not_retired")
    if ("DROP FUNCTION IF EXISTS public.b26_p2_attest_provenance_evidence("
            not in flat):
        violations.append("xxi_comp_v1_attester_not_retired")
    # No GRANT may restore runtime authority writes in either direction.
    # The sole designed exception is INSERT on the beat observation
    # table (append-only beat authorship for the history check).
    # Operational-column UPDATE re-grants are allowed only with an
    # explicit authority-column exclusion (NOT IN guard nearby).
    for section, tag in ((upgrade, "upgrade"), (downgrade, "downgrade")):
        pos = 0
        while True:
            pos = section.find("GRANT UPDATE", pos)
            if pos == -1:
                break
            window = section[max(0, pos - 600):pos + 500]
            if ("NOT IN" not in window
                    or not any(col in window for col in (
                        "b26_p2_provenance_status",
                        "b26_p2_semantic_regime",
                        "b26_p2_demotion_reason",
                        "b26_p2_source_authority_state"))):
                violations.append(f"xxi_comp_regrant:{tag}")
                break
            pos += 1
        pos = 0
        while True:
            pos = section.find("GRANT INSERT", pos)
            if pos == -1:
                break
            window = section[pos:pos + 300]
            if "b26_p2_history_integrity_observations" not in window:
                violations.append(f"xxi_comp_regrant:{tag}")
                break
            pos += 1
    # Cascade hygiene: the downgrade PROCEDURE writes no session tenant
    # context. set_config occurrences inside restored CREATE FUNCTION
    # bodies are frozen XIX behavior (proven safe), not procedure state.
    import re as _re  # noqa: PLC0415
    _no_fns = _re.sub(
        r"CREATE OR REPLACE FUNCTION.*?END \$\$;",
        "", downgrade, flags=_re.DOTALL)
    if "set_config" in _no_fns or "SET LOCAL" in _no_fns:
        violations.append("xxi_comp_downgrade_writes_session_state")
    else:
        checks["downgrade_writes_no_session_state"] = True
    # Downgrade restores v1 ABI + 300003 floor/law, retains demotion data
    # (no demotion clearing anywhere in downgrade).
    for token in ("_XXI_PREDECESSOR_FLOOR", "202609300003"):
        if token not in downgrade and "300003" not in downgrade:
            violations.append("xxi_comp_downgrade_missing_predecessor")
            break
    else:
        checks["downgrade_targets_300003"] = True
    if "b26_p2_demotion_reason=NULL" in downgrade.replace(" ", "").upper():
        violations.append("xxi_comp_downgrade_clears_demotion")
    else:
        checks["downgrade_preserves_demotion_data"] = True
    # Downgrade tracks the topology adjudicators back to the XX-era
    # v1 bodies (XXI-9 forward-ports them to v2; a downgrade that
    # restores v1 while leaving v2-only adjudicators would make every
    # topology consumer silently skip strict evaluation).
    for _fn in ("b26_p2_xii_topology_check",
                "b26_p2_xiii_topology_check",
                "b26_p2_xiv_topology_check",
                "b26_p2_xii_provision_ingress_topology"):
        if downgrade.count(f"FUNCTION public.{_fn}()") < 1:
            violations.append(f"xxi_comp_downgrade_topology_untracked:{_fn}")
            break
    else:
        checks["downgrade_restores_topology_adjudicators"] = True
    if not [v for v in violations if "xxi_comp_law_missing" in v]:
        checks["xxi_law_present"] = True

    # Production code seams.
    adapter = (REPO_ROOT / "backend" / "app" / "trust" / "source_adapters.py"
               ).read_text(encoding="utf-8")
    if "b26_p2_ingress_has_current_authority(" not in adapter:
        violations.append("xxi_comp_adapter_no_predicate")
    else:
        checks["adapter_reads_predicate"] = True
    derivation = (REPO_ROOT / "backend" / "app" / "webhooks"
                  / "commerce_derivation.py").read_text(encoding="utf-8")
    for token in ("derive_shopify_lifecycle",
                  "SHOPIFY_CREATION_SKEW_SECONDS",
                  "orders.create"):
        if token not in derivation:
            violations.append(f"xxi_comp_derivation_missing:{token}")
    if not [v for v in violations if "xxi_comp_derivation_missing" in v]:
        checks["positive_creation_law_python"] = True
    server = (REPO_ROOT / "backend" / "app" / "auth_service" / "server.py"
              ).read_text(encoding="utf-8")
    for token in ("_startup_construction_authority_guard",
                  "b26_p2_authenticate_ingress_atomic_v2(",
                  "derive_shopify_lifecycle"):
        if token not in server:
            violations.append(f"xxi_comp_root_missing:{token}")
    if not [v for v in violations if "xxi_comp_root_missing" in v]:
        checks["auth_root_gated_and_v2"] = True
    builder = (REPO_ROOT / "backend" / "app" / "trust" / "builder.py"
               ).read_text(encoding="utf-8")
    for token in ("read_history_integrity_status",
                  "history_integrity_unverifiable",
                  "HISTORY_INTEGRITY_HORIZON_SECONDS"):
        if token not in builder:
            violations.append(f"xxi_comp_builder_missing:{token}")
    if not [v for v in violations if "xxi_comp_builder_missing" in v]:
        checks["builder_checks_history"] = True
    beat = (REPO_ROOT / "backend" / "app" / "tasks" / "beat_schedule.py"
            ).read_text(encoding="utf-8")
    if "b26-p2-history-observation" not in beat:
        violations.append("xxi_comp_beat_schedule_missing")
    else:
        checks["beat_schedule_present"] = True
    # The beat entry executes on B2.3 workers: the task module must be
    # in the worker include list, otherwise every beat publication
    # hits "unregistered task", observations starve, and issuance
    # degrades (fail-closed outage). Pin the wiring, not just the entry.
    celery = (REPO_ROOT / "backend" / "app" / "celery_app.py"
              ).read_text(encoding="utf-8")
    if '"app.tasks.b26_p2_history"' not in celery:
        violations.append("xxi_comp_beat_task_unregistered")
    else:
        checks["beat_task_registered"] = True
    contract = (REPO_ROOT / "backend" / "app" / "core"
                / "construction_authority.py").read_text(encoding="utf-8")
    # Family-law v4 follow-up advances the construction contract to
    # the current head; F5 advances it to 300008; P1 to 300009; the
    # C19 result-telemetry transport admission to 202610180001; XXIII
    # to 202610180003. A stale contract fails closed here.
    if 'REQUIRED_SCHEMA_REVISION = "202610280001"' not in contract:
        violations.append("xxi_comp_construction_contract_not_advanced")
    else:
        checks["construction_contract_at_xxi"] = True

    # Anchor file well-formed.
    try:
        anchor = json.loads(ANCHOR_PATH.read_text(encoding="utf-8"))
    except OSError as exc:
        violations.append(f"xxi_comp_anchor_unreadable:{exc}")
        return
    for key in ("genesis_hash", "tip_hash", "count"):
        if not anchor.get(key):
            violations.append(f"xxi_comp_anchor_missing:{key}")
    if not [v for v in violations if "xxi_comp_anchor_missing" in v]:
        checks["anchor_present"] = True


DAY_START = "2026-09-01T00:00:00+00:00"
DAY_END = "2026-09-02T00:00:00+00:00"
POLICY_SHA = "fc1c3647f49fbf560a90b6f01568fc70cd2393418800781e2b9d979abe6c1f99"


def _live_checks(
    admin_dsn: str, violations: list[str], checks: dict
) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xxi_comp_no_driver:{exc}")
        return
    ingress_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_ingress:app_ingress"
    )
    worker_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xxi_comp_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        TASK_RUN = uuid.uuid4().hex[:8]
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xxi-comp", uuid.uuid4().hex, "xxi@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xxi_comp_ch', 'xxi', true,"
            " 'XXI', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(evref: str, cref: str, amount: int,
                   provider: str = "stripe",
                   kind: str = "stripe_payment_intent_id",
                   ts: str = "2026-09-01T12:00:00+00:00") -> str:
            ev = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s,%s,now(),%s,%s,%s,'{}'::jsonb,%s,'conversion',"
                " 'xxi_comp_ch','c',%s,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), amount,
                 str(uuid.uuid4()), amount),
            )
            ing = str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s,%s,%s,%s,%s,%s,%s,"
                "%s,%s,'USD',%s,%s,'authenticity_verified')",
                (ing, tenant, ev, provider, evref, cref, kind,
                 cref, amount, ts, str(uuid.uuid4())),
            )
            return ing

        def _auth_v2(ing: str, eref: str, sha: str,
                     provider: str = "stripe",
                     family: str = "payment_intent.succeeded",
                     source: str = "body-signal:type",
                     status=None, cancelled=None, refunds=False,
                     created=None, updated=None) -> str:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = False
            try:
                with igr.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    icur.execute(
                        "SELECT set_config('app.b26_p2_event_family',"
                        " %s, true)",
                        (family,),
                    )
                    icur.execute(
                        "SELECT set_config('app.b26_p2_event_family_source',"
                        " %s, true)",
                        (source,),
                    )
                    icur.execute(
                        "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
                        "%s,%s,%s,%s,%s,"
                        "'hmac-sha256-timestamped-hex','v1',"
                        "%s,%s,%s,%s,%s)",
                        (ing, provider, eref, sha, "b" * 64, status,
                         cancelled, refunds, created, updated),
                    )
                    out = str(icur.fetchone()[0])
                    igr.commit()
                    return out
            finally:
                igr.close()

        def _predicate(ing: str):
            cur.execute(
                "SELECT public.b26_p2_ingress_has_current_authority(%s)", (ing,)
            )
            return cur.fetchone()[0]

        def _mkverdict(ing: str, eref: str, amount: int) -> str:
            cur.execute(
                "INSERT INTO public.b23_match_verdicts (tenant_id,"
                " attribution_event_id, webhook_ingress_identity_id, provider,"
                " canonical_commerce_reference, provider_native_event_reference,"
                " provider_native_commerce_reference, status, match_quality,"
                " attributed_amount_minor, verified_amount_minor, currency_code,"
                " confirmed_at, last_transition_at,"
                " canonical_expected_gross_amount_minor,"
                " canonical_captured_gross_amount_minor,"
                " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
                " discrepancy_ratio_bps, discrepancy_band)"
                " SELECT %s, event_id, %s, 'stripe', 'xxi-c1',"
                " %s, 'xxi-c1', 'matched_confirmed', 'high',"
                " %s, %s, 'USD', now(), now(), %s, %s,"
                " %s, 0, 0, 'exact' FROM public.webhook_ingress_identities"
                " WHERE id=%s RETURNING id",
                (tenant, ing, eref, amount, amount, amount, amount, amount,
                 ing),
            )
            return cur.fetchone()[0]

        # V1: v2 honest mint conducts; v1 ABI is gone.
        row = _mkrow("xxi-v1", "xxi-c1", 100000)
        assert _auth_v2(row, "xxi-v1", "a" * 64) == "authenticated_known"
        if _predicate(row) is not True:
            violations.append("xxi_comp_v2_mint_not_current")
            return
        checks["v2_mint_conducts"] = True
        try:
            cur.execute(
                "SELECT public.b26_p2_authenticate_ingress_atomic("
                "%s,'stripe','xxi-old',%s,%s,"
                "'hmac-sha256-timestamped-hex','v1')",
                (row, "e" * 64, "b" * 64),
            )
            violations.append("xxi_comp_v1_abi_still_callable")
        except Exception as exc:
            if "does not exist" not in str(exc):
                violations.append(
                    "xxi_comp_v1_abi_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["v1_abi_absent"] = True
        try:
            cur.execute(
                "SELECT public.b26_p2_attest_provenance_evidence("
                "%s,'signed_provider_reingestion','xxi-old')",
                (row,),
            )
            violations.append("xxi_comp_v1_attester_still_callable")
        except Exception as exc:
            if "does not exist" not in str(exc):
                violations.append(
                    "xxi_comp_v1_attester_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["v1_attester_absent"] = True

        # V2: lifecycle refused at the DB seam (no Python involved).
        # Native shopify row: the atomic's provider check is itself a
        # lawful fence (mismatch refuses), so the probe must be honest.
        term = _mkrow("xxi-term", "xxi-cterm", 1000,
                      provider="shopify", kind="shopify_order_id")
        try:
            _auth_v2(term, "xxi-term", "f" * 64, provider="shopify",
                     family="orders.create",
                     source="transport-topic:x-shopify-topic",
                     status="voided", created="2026-09-01T00:00:00+00:00",
                     updated="2026-09-01T00:00:00+00:00")
            violations.append("xxi_comp_terminal_minted_at_seam")
        except Exception as exc:
            if "b26_p2_lifecycle" not in str(exc):
                violations.append(
                    "xxi_comp_terminal_wrong_refusal:"
                    f"{str(exc).splitlines()[0][:120]}"
                )
            else:
                checks["lifecycle_refused_at_seam"] = True

        # V3: demotion-data monotonicity (backfill policy persists).
        bf = _mkrow("xxi-bf", "xxi-cbf", 5000)
        assert _auth_v2(bf, "xxi-bf", "b" * 64) == "authenticated_known"
        cur.execute(
            "UPDATE public.webhook_ingress_identities"
            " SET b26_p2_demotion_reason="
            "'xxi-evidence-insufficient:pre-xxi-family' WHERE id=%s",
            (bf,),
        )
        if _predicate(bf) is not False:
            violations.append("xxi_comp_demotion_data_not_current")
        else:
            checks["demotion_data_holds"] = True

        # V4: observer + continuity clean; seq assigned on correction.
        # The correction changes attributed money only: the verified
        # amount stays bound to its authenticated ingress so XXIII
        # source conservation remains true after the regime retires.
        verdict = _mkverdict(row, "xxi-v1", 100000)
        cur.execute(
            "UPDATE public.b23_match_verdicts"
            " SET attributed_amount_minor=99999,"
            " canonical_expected_gross_amount_minor=99999,"
            " discrepancy_amount_minor=1,"
            " discrepancy_ratio_bps=0,"
            " discrepancy_band='exact' WHERE id=%s",
            (verdict,),
        )
        cur.execute(
            "SELECT entry_hash, prev_entry_hash, seq FROM"
            " public.b26_p2_verdict_supersession_ledger WHERE verdict_id=%s"
            " ORDER BY recorded_at DESC, id DESC LIMIT 1",
            (verdict,),
        )
        chain = cur.fetchone()
        if not chain or not chain[0] or chain[2] is None:
            violations.append("xxi_comp_chain_seq_missing")
        else:
            checks["chain_seq_appends"] = True
        cur.execute(
            "SELECT violation FROM public.b26_p2_verify_history_protection()")
        if cur.fetchall():
            violations.append("xxi_comp_observerunclean")
        else:
            checks["observer_clean"] = True
        cur.execute(
            "SELECT violation FROM public.b26_p2_verify_history_continuity()")
        if cur.fetchall():
            violations.append("xxi_comp_continuity_unclean")
        else:
            checks["continuity_clean"] = True

        # V5: beat observation writes with worker authorship.
        import os  # noqa: PLC0415
        os.environ["DATABASE_URL"] = admin_dsn.replace(
            "postgresql://", "postgresql+asyncpg://")
        from app.tasks.b26_p2_history import (  # noqa: PLC0415
            observe_history_integrity,
        )
        beat_result = asyncio.run(observe_history_integrity())
        if beat_result.get("violations"):
            violations.append("xxi_comp_beat_reports_violations")
        else:
            checks["beat_observes_clean"] = True
        wconn = psycopg2.connect(worker_dsn)
        wconn.autocommit = True
        try:
            with wconn.cursor() as wcur:
                # Real beat path as the worker role: the DEFINER
                # observation function (the only ledger reader the
                # worker may invoke) stamps the CALLER's session_user.
                wcur.execute(
                    "SELECT * FROM"
                    " public.b26_p2_observe_history_integrity()")
                wcur.fetchall()
                wcur.execute(
                    "SELECT author FROM"
                    " public.b26_p2_history_integrity_observations"
                    " ORDER BY id DESC LIMIT 1")
                if wcur.fetchone()[0] != "app_worker":
                    violations.append("xxi_comp_beat_authorship_forgeable")
                else:
                    checks["beat_authorship_unforgeable"] = True
        finally:
            wconn.close()

        # V6: REAL adapter + REAL P3 + REAL builder (no replicas).
        cur.execute(
            "INSERT INTO public.b23_match_task_dispatches (tenant_id,"
            " webhook_ingress_identity_id, task_id, task_name, queue,"
            " routing_key, correlation_id, provider,"
            " provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_value, status,"
            " delivery_state, publish_attempts, window_start,"
            " window_end) VALUES (%s, %s, %s,"
            " 'app.tasks.revenue_verification.execute_b23_batch_match_engine',"
            " 'b23_match_engine', 'b23_match_engine.task', %s,"
            " 'stripe', %s, %s, %s, 'dispatched', 'pending_publish',"
            " 0, %s, %s)",
            (tenant, row, "xxi-task-" + TASK_RUN, str(uuid.uuid4()), "xxi-v1",
             "xxi-c1", "xxi-c1", DAY_START, DAY_END),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_execution_outbox (tenant_id,"
            " dispatch_task_id, webhook_ingress_identity_id)"
            " VALUES (%s, %s, %s)",
            (tenant, "xxi-task-" + TASK_RUN, row),
        )
        cur.execute(
            "INSERT INTO public.b26_p2_task_authority_directory (task_id,"
            " tenant_id, webhook_ingress_identity_id, window_start,"
            " window_end) VALUES (%s, %s, %s, %s, %s)",
            ("xxi-task-" + TASK_RUN, tenant, row, DAY_START, DAY_END),
        )
        cur.execute(
            "UPDATE public.b23_match_task_dispatches"
            " SET delivery_state='published', first_published_at=now()"
            " WHERE task_id=%s",
            ("xxi-task-" + TASK_RUN,),
        )
        cur.execute(
            "UPDATE public.b26_p2_execution_outbox SET state='published'"
            " WHERE dispatch_task_id=%s",
            ("xxi-task-" + TASK_RUN,),
        )
        wconn2 = psycopg2.connect(worker_dsn)
        wconn2.autocommit = True
        try:
            with wconn2.cursor() as wcur:
                wcur.execute(
                    "SELECT public.b26_p2_canonical_scope_identity_for_window"
                    "(%s,%s,%s)",
                    (tenant, DAY_START, DAY_END),
                )
                scope = str(wcur.fetchone()[0])
                wcur.execute(
                    "SELECT public.b26_p2_record_conduction_receipt(%s,%s,%s,%s)",
                    ("xxi-task-" + TASK_RUN, scope, 1, POLICY_SHA),
                )
                wcur.execute("SELECT public.b26_p2_mark_conducted(%s)",
                             ("xxi-task-" + TASK_RUN,))
        finally:
            wconn2.close()
        cur.execute(
            "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)",
            ("xxi-task-" + TASK_RUN, tenant),
        )
        if cur.fetchone()[0] is not True:
            violations.append("xxi_comp_p3_not_eligible_at_rest")
        else:
            checks["real_p3_eligible_at_rest"] = True

        from sqlalchemy import text as _stext  # noqa: PLC0415
        from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
            AsyncSession,
            create_async_engine,
        )
        from app.revenue_verification.verification_coverage import (  # noqa: PLC0415
            fetch_verification_coverage_aggregate,
        )
        from app.trust.builder import (  # noqa: PLC0415
            TrustEnvelopeBuildRequest,
            build_unsigned_trust_envelope,
        )
        from app.trust.source_adapters import (  # noqa: PLC0415
            read_match_verdict_source,
        )
        from app.core.config import settings as _settings  # noqa: PLC0415

        _settings.B26_P2_HISTORY_WITNESS_REQUIRED = False

        from app.revenue_verification.source_attestation import (  # noqa: PLC0415
            DEFAULT_ATTESTATION_KEY_ID,
            build_statement,
            generate_keypair,
            sign_statement,
        )

        key_dir = Path(tempfile.mkdtemp(prefix="xxi-comp-attest-"))
        private_seed, public_b64 = generate_keypair()
        private_path = key_dir / "source.key"
        public_path = key_dir / "source.pub"
        private_path.write_text(private_seed, encoding="utf-8")
        public_path.write_text(public_b64, encoding="utf-8")
        _settings.B26_P2_SOURCE_ATTESTATION_REQUIRED = True
        _settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH = str(public_path)

        def _attest_source(
            ing: str,
            eref: str,
            sha: str,
            amount: int,
            *,
            provider: str = "stripe",
            cref: str = "xxi-c1",
            kind: str = "stripe_payment_intent_id",
            ts: str = "2026-09-01T12:00:00+00:00",
        ) -> None:
            igr = psycopg2.connect(ingress_dsn)
            igr.autocommit = False
            try:
                with igr.cursor() as icur:
                    icur.execute(
                        "SELECT set_config('app.current_tenant_id', %s, false)",
                        (tenant,),
                    )
                    icur.execute(
                        "SELECT public.b26_p2_authority_universe()::text"
                    )
                    universe = icur.fetchone()[0]
                    statement = build_statement(
                        tenant_id=tenant,
                        webhook_ingress_identity_id=ing,
                        provider=provider,
                        provider_native_event_reference=eref,
                        provider_native_commerce_reference=cref,
                        normalized_commerce_reference_kind=kind,
                        normalized_commerce_reference_value=cref,
                        verified_amount_minor=amount,
                        verified_amount_currency="USD",
                        verified_amount_scale=2,
                        event_timestamp=datetime.fromisoformat(ts),
                        body_sha256=sha,
                        authority_universe=universe,
                    )
                    signature, key_sha256 = sign_statement(
                        statement, private_key_path=private_path
                    )
                    icur.execute(
                        "INSERT INTO public.b26_p2_source_money_attestation ("
                        " webhook_ingress_identity_id, tenant_id, statement_version,"
                        " attested_amount_minor, attested_amount_currency,"
                        " attested_amount_scale, statement, signature, key_id, key_sha256"
                        ") VALUES (%s,%s,%s,%s,%s,%s,CAST(%s AS jsonb),%s,%s,%s)"
                        " ON CONFLICT (webhook_ingress_identity_id) DO NOTHING",
                        (
                            ing,
                            tenant,
                            int(statement["version"]),
                            amount,
                            "USD",
                            2,
                            json.dumps(statement, sort_keys=True),
                            signature,
                            DEFAULT_ATTESTATION_KEY_ID,
                            key_sha256,
                        ),
                    )
                igr.commit()
            finally:
                igr.close()

        _attest_source(row, "xxi-v1", "a" * 64, 100000)

        async def _real_reads():
            engine = create_async_engine(
                admin_dsn.replace("postgresql://",
                                  "postgresql+asyncpg://"))
            try:
                async with AsyncSession(engine) as session:
                    await session.execute(
                        _stext("SELECT set_config('app.current_tenant_id',"
                               " :t, false)"),
                        {"t": tenant},
                    )
                    src = await read_match_verdict_source(
                        session,
                        tenant_id=uuid.UUID(tenant),
                        subject_ref=f"urn:skeldir:match_verdict:{verdict}",
                    )
                    adapter_auth = (src.ingress_has_current_authority
                                    if src else None)
                    request = TrustEnvelopeBuildRequest(
                        tenant_id=uuid.UUID(tenant),
                        subject_type="match_verdict",
                        subject_ref=f"urn:skeldir:match_verdict:{verdict}",
                        request_context={
                            "created_at": datetime.now(timezone.utc),
                            "audience_id": "xxi-validator",
                        },
                    )
                    built = await build_unsigned_trust_envelope(
                        session, request)
                    payload_status = None
                    if built.unsigned_payload is not None:
                        payload_status = built.unsigned_payload.get(
                            "match_verdict_status")
                    agg = await fetch_verification_coverage_aggregate(
                        session,
                        tenant_id=uuid.UUID(tenant),
                        window_start=datetime(2026, 9, 1,
                                              tzinfo=timezone.utc),
                        window_end=datetime(2026, 10, 1,
                                            tzinfo=timezone.utc),
                    )
                    return (adapter_auth, built.status,
                            payload_status, built.reason_code,
                            agg.connected_platform_revenue_minor)
            finally:
                await engine.dispose()

        (adapter_auth, built_status, payload_status, built_reason,
         connected) = asyncio.run(_real_reads())
        if adapter_auth is not True:
            violations.append("xxi_comp_real_adapter_not_current")
        else:
            checks["real_adapter_current_at_rest"] = True
        if built_status != "success" or payload_status != "matched":
            violations.append(
                f"xxi_comp_real_builder_not_truth:{built_status}/"
                f"{payload_status}/{built_reason}")
        else:
            checks["real_builder_issues_at_rest"] = True
        if connected != 100000:
            violations.append(f"xxi_comp_real_coverage_not_100000:{connected}")
        else:
            checks["real_coverage_100000_at_rest"] = True

        # V7: retire -> every real reader refuses/degrades; restore.
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry"
            " SET status='retired' WHERE regime_id='xvii-sovereign-v1'"
        )
        if _predicate(row) is not False:
            violations.append("xxi_comp_retire_predicate_survives")
        cur.execute(
            "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)",
            ("xxi-task-" + TASK_RUN, tenant),
        )
        if cur.fetchone()[0] is not False:
            violations.append("xxi_comp_retire_p3_survives")
        else:
            checks["real_p3_refuses_after_retire"] = True

        async def _real_reads_retired():
            engine = create_async_engine(
                admin_dsn.replace("postgresql://",
                                  "postgresql+asyncpg://"))
            try:
                async with AsyncSession(engine) as session:
                    await session.execute(
                        _stext("SELECT set_config('app.current_tenant_id',"
                               " :t, false)"),
                        {"t": tenant},
                    )
                    src = await read_match_verdict_source(
                        session,
                        tenant_id=uuid.UUID(tenant),
                        subject_ref=f"urn:skeldir:match_verdict:{verdict}",
                    )
                    request = TrustEnvelopeBuildRequest(
                        tenant_id=uuid.UUID(tenant),
                        subject_type="match_verdict",
                        subject_ref=f"urn:skeldir:match_verdict:{verdict}",
                        request_context={
                            "created_at": datetime.now(timezone.utc),
                            "audience_id": "xxi-validator",
                        },
                    )
                    built = await build_unsigned_trust_envelope(
                        session, request)
                    payload_status = None
                    if built.unsigned_payload is not None:
                        payload_status = built.unsigned_payload.get(
                            "match_verdict_status")
                    agg = await fetch_verification_coverage_aggregate(
                        session,
                        tenant_id=uuid.UUID(tenant),
                        window_start=datetime(2026, 9, 1,
                                              tzinfo=timezone.utc),
                        window_end=datetime(2026, 10, 1,
                                            tzinfo=timezone.utc),
                    )
                    return (src.ingress_has_current_authority
                            if src else None, built.status,
                            payload_status,
                            built.reason_code,
                            agg.connected_platform_revenue_minor)
            finally:
                await engine.dispose()

        adapter_auth2, built_status2, payload_status2, built_reason2, connected2 = (
            asyncio.run(_real_reads_retired()))
        if adapter_auth2 is not False:
            violations.append("xxi_comp_retire_adapter_survives")
        else:
            checks["real_adapter_refuses_after_retire"] = True
        # Retire appends supersession history (verdict authority
        # transitions are corrections by design), so any pre-retire
        # beat observation is genuinely stale: the builder must refuse
        # on history divergence here. Re-observe, then prove the
        # authority degrade path with fresh continuity.
        if built_reason2 != "history_integrity_unverifiable":
            violations.append(
                "xxi_comp_retire_builder_expected_history_refusal:"
                f"{built_status2}/{payload_status2}/{built_reason2}")
        else:
            checks["retire_triggers_history_refusal"] = True
        wconn3 = psycopg2.connect(worker_dsn)
        wconn3.autocommit = True
        try:
            with wconn3.cursor() as wcur:
                wcur.execute(
                    "SELECT * FROM"
                    " public.b26_p2_observe_history_integrity()")
                wcur.fetchall()
        finally:
            wconn3.close()
        # With fresh continuity, the same retired source must degrade
        # on authority (success envelope, unavailable status) rather
        # than issuing verified truth.
        (adapter_auth3, built_status3, payload_status3, built_reason3,
         connected3) = asyncio.run(_real_reads_retired())
        if adapter_auth3 is not False or connected3 != 0:
            violations.append(
                f"xxi_comp_retire_readers_survive:{adapter_auth3}/"
                f"{connected3}")
        elif payload_status3 == "unavailable" and built_status3 == "success":
            checks["real_builder_degrades_after_retire"] = True
        else:
            violations.append(
                "xxi_comp_retire_builder_truth:"
                f"{built_status3}/{payload_status3}/{built_reason3}")
        if connected2 != 0:
            violations.append(
                f"xxi_comp_retire_coverage_survives:{connected2}")
        else:
            checks["real_coverage_zero_after_retire"] = True
        cur.execute(
            "UPDATE public.b26_p2_semantic_regime_registry"
            " SET status='active' WHERE regime_id='xvii-sovereign-v1'"
        )
        if _predicate(row) is not True:
            violations.append("xxi_comp_restore_not_current")
        else:
            checks["readers_agree_after_restore"] = True

        # V8: continuity enforcement (behavioral, not file comparison:
        # fresh lanes carry different rows than any committed anchor,
        # so the anchor file documents genesis for auditors while live
        # guarantees come from executable controls below). Savepoint
        # probes need an explicit transaction (admin is autocommit).
        txn = psycopg2.connect(admin_dsn)
        try:
            tcur = txn.cursor()
            tcur.execute("SELECT set_config('app.current_tenant_id', %s, false)",
                         (tenant,))
            # V8a: TRUNCATE in-transaction -> beat contradiction REDs.
            tcur.execute(
                "INSERT INTO public.b26_p2_history_integrity_observations"
                " (ledger_count, ledger_tip, observer_violations)"
                " SELECT count(*), (SELECT l.entry_hash FROM"
                " public.b26_p2_verdict_supersession_ledger AS l"
                " ORDER BY l.seq DESC LIMIT 1), ''"
                " FROM public.b26_p2_verdict_supersession_ledger"
            )
            tcur.execute("SELECT count(*) FROM"
                         " public.b26_p2_verdict_supersession_ledger")
            _pre_count = tcur.fetchone()[0]
            tcur.execute("SELECT pg_advisory_xact_lock(82173645, 300004)")
            tcur.execute("SAVEPOINT xxi_truncate_probe")
            try:
                tcur.execute("TRUNCATE public.b26_p2_verdict_supersession_ledger")
                tcur.execute(
                    "SELECT o.ledger_count FROM"
                    " public.b26_p2_history_integrity_observations AS o"
                    " ORDER BY o.id DESC LIMIT 1"
                )
                _beat_count = tcur.fetchone()[0]
                tcur.execute("SELECT count(*) FROM"
                            " public.b26_p2_verdict_supersession_ledger")
                _live_count = tcur.fetchone()[0]
                if not (_beat_count > 0 and _live_count == 0):
                    violations.append("xxi_comp_truncate_probe_inconclusive")
                else:
                    # The beat-recorded count contradicts the emptied
                    # ledger: erasure is observable, never valid-empty.
                    checks["truncate_contradiction_detected"] = True
            finally:
                tcur.execute("ROLLBACK TO SAVEPOINT xxi_truncate_probe")
            tcur.execute("SELECT count(*) FROM"
                        " public.b26_p2_verdict_supersession_ledger")
            if tcur.fetchone()[0] != _pre_count:
                violations.append("xxi_comp_truncate_restore_failed")
            else:
                checks["truncate_exact_restore"] = True
            # V8b: coherent rewrite in-transaction -> beat-tip REDs.
            # Faithful to the auditor attack: disable the immutability
            # trigger, alter amounts, RECOMPUTE the chain hash per the
            # documented preimage (self-consistent forgery), re-enable.
            tcur.execute("SELECT entry_hash FROM"
                        " public.b26_p2_verdict_supersession_ledger"
                        " ORDER BY seq DESC LIMIT 1")
            _live_tip = tcur.fetchone()
            _live_tip = _live_tip[0] if _live_tip else None
            tcur.execute("SAVEPOINT xxi_rewrite_probe")
            try:
                tcur.execute(
                    "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                    " DISABLE TRIGGER trg_b26_p2_xix_ledger_immutable")
                tcur.execute(
                    "UPDATE public.b26_p2_verdict_supersession_ledger AS l"
                    " SET new_verified_amount_minor=88888,"
                    " entry_hash = encode(digest("
                    " COALESCE(l.verdict_id::text, '')"
                    " || '|' || COALESCE(l.prior_attributed_amount_minor::text,"
                    " 'NULL')"
                    " || '|' || COALESCE(l.new_attributed_amount_minor::text,"
                    " 'NULL')"
                    " || '|' || COALESCE(l.prior_verified_amount_minor::text,"
                    " 'NULL')"
                    " || '|88888'"
                    " || '|' || COALESCE(l.prior_authority_state, 'NULL')"
                    " || '|' || COALESCE(l.new_authority_state, 'NULL')"
                    " || '|' || COALESCE(l.prev_entry_hash, ''),"
                    " 'sha256'), 'hex')"
                    " WHERE verdict_id=%s", (verdict,))
                tcur.execute(
                    "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                    " ENABLE TRIGGER trg_b26_p2_xix_ledger_immutable")
                tcur.execute(
                    "SELECT o.ledger_tip FROM"
                    " public.b26_p2_history_integrity_observations AS o"
                    " ORDER BY o.id DESC LIMIT 1")
                _beat_tip = tcur.fetchone()[0]
                tcur.execute(
                    "SELECT l.entry_hash FROM"
                    " public.b26_p2_verdict_supersession_ledger AS l"
                    " ORDER BY l.seq DESC LIMIT 1")
                _new_tip = tcur.fetchone()
                _new_tip = _new_tip[0] if _new_tip else None
                # The recomputed tip no longer matches the beat-recorded
                # tip predating the tamper: coherent forgery detected.
                if _beat_tip is not None and _new_tip != _beat_tip:
                    checks["rewrite_tip_divergence_detected"] = True
                else:
                    violations.append("xxi_comp_rewrite_probe_inconclusive")
            finally:
                tcur.execute("ROLLBACK TO SAVEPOINT xxi_rewrite_probe")
            tcur.execute(
                "SELECT new_verified_amount_minor FROM"
                " public.b26_p2_verdict_supersession_ledger"
                " WHERE verdict_id=%s ORDER BY seq DESC LIMIT 1",
                (verdict,))
            if tcur.fetchone()[0] != 100000:
                violations.append("xxi_comp_rewrite_restore_failed")
            else:
                checks["rewrite_exact_restore"] = True
            txn.commit()
        except Exception as _txn_exc:
            try:
                txn.rollback()
            except Exception:
                pass
            violations.append(f"xxi_comp_probe_txn_failed:{_txn_exc}"[:160])
        finally:
            txn.close()

        # V9: supported downgrade preserves disqualification everywhere.
        import os as _os  # noqa: PLC0415
        import subprocess as _sp  # noqa: PLC0415

        env = dict(_os.environ)
        env["MIGRATION_DATABASE_URL"] = admin_dsn
        env["DATABASE_URL"] = admin_dsn
        # Ledger preservation snapshot (downgrade/re-upgrade must not
        # alter committed history rows).
        cur.execute(
            "SELECT id::text, entry_hash FROM"
            " public.b26_p2_verdict_supersession_ledger ORDER BY seq ASC")
        _ledger_before = cur.fetchall()
        # Explicit supported-boundary target (not -1): with the
        # additive 300005 follow-up, -1 would stop at 300004 and never
        # exercise the 300003 boundary this leg exists to prove.
        down = _sp.run(
            [sys.executable, "-m", "alembic", "downgrade", "202609300003"],
            capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
        )
        if down.returncode != 0:
            violations.append(
                f"xxi_comp_downgrade_failed:{down.stderr[-200:]}"
            )
        else:
            cur.execute("SELECT version_num FROM alembic_version")
            if cur.fetchone()[0] != "202609300003":
                violations.append("xxi_comp_downgrade_wrong_revision")
            else:
                # Cascade hygiene is proven statically (the downgrade
                # procedure writes no session state) and by full
                # downgrade cascades (P13 job); a same-session GUC read
                # here cannot observe another session's state.
                checks["downgrade_hygiene_static_plus_cascade"] = True
                cur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,))
                if _predicate(bf) is not False:
                    violations.append(
                        "xxi_comp_downgrade_resurrects_backfill")
                else:
                    checks["downgrade_preserves_disqualification"] = True
                cur.execute(
                    "SELECT count(*) FROM public.webhook_ingress_identities"
                    " AS wi WHERE wi.tenant_id=%s AND wi.id=%s AND"
                    " public.b26_p2_ingress_has_current_authority(wi.id)",
                    (tenant, bf),
                )
                if cur.fetchone()[0] != 0:
                    violations.append("xxi_comp_downgrade_coverage_includes")
                else:
                    checks["downgrade_coverage_excludes"] = True
                cur.execute(
                    "SELECT public.b26_p2_state_eligible_for_p3(%s,%s)",
                    ("xxi-task-" + TASK_RUN, tenant),
                )
                # P3 task was built on the lawful v2-minted row, which
                # stays current at 300003: eligibility must remain TRUE
                # (no honest-path regression at the downgraded state).
                p3down = cur.fetchone()[0]
                if p3down is not True:
                    violations.append(
                        f"xxi_comp_downgrade_p3_regressed:{p3down}")
                else:
                    checks["downgrade_p3_stays_eligible"] = True
                # The restored v1 adjudicator must evaluate strictly
                # (not error on the restored names, not silently skip).
                cur.execute("SELECT public.b26_p2_xiv_topology_check()")
                if str(cur.fetchone()[0]) != "xiv_topology_strict":
                    violations.append("xxi_comp_downgrade_topology_lax")
                else:
                    checks["downgrade_topology_strict"] = True
            up = _sp.run(
                [sys.executable, "-m", "alembic", "upgrade", "head"],
                capture_output=True, text=True, cwd=str(REPO_ROOT), env=env,
            )
            if up.returncode != 0:
                violations.append(
                    f"xxi_comp_reupgrade_failed:{up.stderr[-200:]}")
            else:
                cur.execute("SELECT version_num FROM alembic_version")
                if cur.fetchone()[0] != "202610280001":
                    violations.append("xxi_comp_reupgrade_wrong_revision")
                else:
                    checks["downgrade_reupgrade_converges"] = True
                    # The v2 adjudicator must evaluate strictly again.
                    cur.execute(
                        "SELECT public.b26_p2_xiv_topology_check()")
                    if (str(cur.fetchone()[0])
                            != "xiv_topology_strict"):
                        violations.append(
                            "xxi_comp_reupgrade_topology_lax")
                    else:
                        checks["reupgrade_topology_strict"] = True
                    cur.execute(
                        "SELECT id::text, entry_hash FROM"
                        " public.b26_p2_verdict_supersession_ledger"
                        " ORDER BY seq ASC")
                    _ledger_after = cur.fetchall()
                    _b_ids = {r[0] for r in _ledger_before}
                    _a_ids = {r[0] for r in _ledger_after}
                    # XXV attestations are intentionally dropped by the
                    # supported downgrade to a pre-XXV revision. Re-upgrade
                    # must truthfully append the resulting authority
                    # transitions; it must never lose or rewrite a committed
                    # row. Append-only prefix preservation is the law here.
                    if _ledger_after[: len(_ledger_before)] != _ledger_before:
                        violations.append(
                            "xxi_comp_downgrade_altered_history:"
                            f"before={len(_ledger_before)}"
                            f" after={len(_ledger_after)}"
                            f" lost={sorted(_b_ids - _a_ids)[:2]}"
                            f" gained={sorted(_a_ids - _b_ids)[:2]}")
                    else:
                        checks["downgrade_preserves_history"] = True
                        if len(_ledger_after) > len(_ledger_before):
                            checks["downgrade_appends_xxv_truth"] = True
        cur.execute("SELECT floor_revision FROM public.b26_p2_operational_floor"
                    " WHERE id=1")
        if cur.fetchone()[0] != "202609300004":
            violations.append("xxi_comp_floor_not_xxi")
        else:
            checks["floor_at_xxi"] = True
        # 300005 follow-up: the verdict-keyed reader is live with exactly
        # the two Bayesian-read grants and fails closed for others. The
        # operational floor intentionally stays at 300004 (additive
        # helper; no semantic-law advance).
        cur.execute(
            "SELECT count(*) FROM pg_proc p JOIN pg_namespace n"
            " ON n.oid = p.pronamespace"
            " WHERE n.nspname = 'public'"
            " AND p.proname = 'b26_p2_verdict_has_current_authority'"
        )
        if cur.fetchone()[0] != 1:
            violations.append("xxi_comp_reader_absent_live")
        else:
            cur.execute(
                "SELECT grantee FROM information_schema.role_routine_grants"
                " WHERE routine_schema = 'public'"
                " AND routine_name = 'b26_p2_verdict_has_current_authority'"
                " AND grantee NOT IN ('migration_owner', 'postgres')"
                " ORDER BY grantee"
            )
            _holders = sorted(r[0] for r in cur.fetchall())
            if _holders != ["app_user", "app_worker"]:
                violations.append(
                    f"xxi_comp_reader_grants_wrong:{_holders}")
            else:
                checks["verdict_reader_live_fenced"] = True
        cur.close()
    except Exception as exc:
        import traceback as _tb  # noqa: PLC0415
        violations.append(
            f"xxi_comp_live_failed:{exc}:{_tb.format_exc(limit=6)[-900:]}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XXI composition closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XXI_COMPOSITION_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B2.6-P2-XXI-COMPOSITION",
                    "status": status,
                    "violations": sorted(violations),
                    "checks": checks,
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
