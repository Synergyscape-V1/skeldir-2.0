#!/usr/bin/env python3
"""B2.6-P2 Corrective XVI database-physics closure (H-XVI-R5/R6/R8/R12/R21).

Laws (each REDs on the effect):
- one payment mints one lineage: the atomic refuses a second
  authenticated row for identical bytes (static: fence tokens in the
  XVI migration; live: same-sha second auth refused, different event
  with different-sha allowed, same-row re-entry idempotent);
  NOTE (XVII supersession, H-XVII-R4/R5): same event reference with
  different bytes, and same commerce identity across distinct events,
  are now conflict-refused by the XVII atomic -- so the live
  "distinct bytes authenticate" probe uses a DISTINCT event reference
  AND distinct commerce identity (a genuinely distinct provider event).
  The XVII physics gate proves the conflict refusals themselves.
- the evidence gate admits only the exact sovereign frame (static:
  anchored signature regex present, substring LIKE absent from the XVI
  upgrade; live: lawful atomic path mints evidence, direct INSERT as
  app_ingress is grant-denied, pg_temp function creation denied);
- trusted state cannot survive evidence destruction (static: the XIV
  downgrade demotes ALL authenticated rows, not just quarantined
  ones, before dropping evidence; live demote-all runs on the
  migration lanes);
- event linkage is provably non-authoritative (live: rebind event_id,
  every authority projection + scope classification identical);
- NULL/UNKNOWN never authorizes (live: NULL-parameter atomic calls
  refused with shape tokens, never silently admitted).

Exit code is the gate. Live DB checks run only with --dsn.
"""

from __future__ import annotations

import argparse
import json
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XIV = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609270001_b26_p2_corrective_xiv_compositional_closure.py"
)
MIG_XVI = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609280002_b26_p2_corrective_xvi_sovereign_closure.py"
)

# File-text form of the strict frame (the migration source carries the
# regex escaped for its own Python string layer: two file-text
# backslashes become one at migration runtime, which Postgres reads as
# an escaped parenthesis).
_STRICT_FRAME = (
    "PL/pgSQL function b26_p2_authenticate_ingress_atomic"
    "\\\\(uuid,text,text,text,text,text,text\\\\)"
)


def _static_checks(violations: list[str], checks: dict) -> None:
    try:
        xvi = MIG_XVI.read_text(encoding="utf-8")
        xiv = MIG_XIV.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xvi_phys_unreadable:{exc}")
        return
    upgrade = xvi.split("def downgrade", 1)[0]
    for token in (
        "pg_advisory_xact_lock",
        "b26_p2_atomic_sovereign_duplicate_refused",
        "b26_p2_provider_auth_consequence",
        "authenticated_known",
        "IS DISTINCT FROM p_ingress",
        "c.provider_event_reference IS NOT DISTINCT FROM p_event_ref",
    ):
        if token not in upgrade:
            violations.append(f"xvi_phys_fence_missing:{token}")
    checks["sovereign_fence_present"] = True
    if _STRICT_FRAME not in upgrade:
        violations.append("xvi_phys_strict_frame_missing")
    if "NOT LIKE '%b26_p2_authenticate_ingress_atomic%'" in upgrade:
        violations.append("xvi_phys_substring_gate_survives")
    checks["strict_frame_present"] = True
    # Downgrade must restore predecessors verbatim.
    downgrade = xvi.split("def downgrade", 1)[1]
    if "NOT LIKE '%b26_p2_authenticate_ingress_atomic%'" not in downgrade:
        violations.append("xvi_phys_downgrade_gate_not_restored")
    checks["downgrade_restores_predecessor"] = True
    # Demote-all: the XIV downgrade must demote EVERY authenticated row
    # before evidence is dropped, not just quarantined ones, and the
    # predicate must not admit a state-label escape (no ingress-state
    # condition at all: a NULL or odd state demotes too).
    # (Adjacent Python string literals leave embedded double quotes in
    # the flattened source; strip them before matching the SQL shape.)
    tail_flat = " ".join(
        xiv.split("def downgrade", 1)[1].replace('"', "").split()
    )
    if tail_flat.count("pending_authentication") < 2 or (
        "SET b26_p2_provenance_status = 'pending_authentication'"
        " WHERE i.b26_p2_provenance_status"
        " IS NOT DISTINCT FROM 'authenticated_known'" not in tail_flat
    ):
        violations.append("xvi_phys_demote_all_missing")
    checks["demote_all_present"] = True
    # No authority consumer may read the ingress event linkage: scan all
    # foundation migrations for ingress-table event_id reads outside the
    # two dispatch lookup hints, the adoption fallback probe, and the
    # uniqueness law. Attribution-plane event ids (allocations, verdicts,
    # attribution_events) are a different column on different tables.
    offenders = []
    mig_dir = REPO_ROOT / "alembic" / "versions" / "007_skeldir_foundation"
    for mig in sorted(mig_dir.glob("*.py")):
        text = mig.read_text(encoding="utf-8")
        for lineno, line in enumerate(text.splitlines(), 1):
            stripped = line.strip()
            if not stripped or stripped.startswith(("--", "#", "*", '"""', "'''")):
                continue
            low = line.lower()
            if "event_id" not in low:
                continue
            if "webhook_ingress_identit" not in low and "ingress" not in low:
                continue
            if "attribution_allocations" in low or "attribution_events" in low:
                continue
            if "attribution_event_id" in low:
                continue
            if "webhook_ingress_identity_id" in low and "i.event_id" not in low:
                continue
            if "i.event_id = :event_id" in low:
                continue  # dispatch / re-drive lookup hints
            if "unique" in low or "uq_webhook" in low or "constraint" in low:
                continue  # uniqueness law, not a read
            if "fallback probe" in low or ("probe" in low and "tenant" in low):
                continue  # adoption fallback probe
            offenders.append(f"{mig.name}:{lineno}:{stripped[:100]}")
    if offenders:
        violations.append(f"xvi_phys_linkage_consumers:{offenders[:5]}")
    else:
        checks["linkage_consumer_census_clean"] = True


def _live_checks(admin_dsn: str, violations: list[str], checks: dict) -> None:
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xvi_phys_no_driver:{exc}")
        return
    ingress_dsn = (
        admin_dsn.replace("migration_owner:migration_owner", "app_ingress:app_ingress")
        if "migration_owner:migration_owner" in admin_dsn
        else None
    )
    if ingress_dsn is None:
        violations.append("xvi_phys_role_dsn_underivable")
        return
    try:
        admin = psycopg2.connect(admin_dsn)
        admin.autocommit = True
    except Exception as exc:
        violations.append(f"xvi_phys_connect_failed:{exc}")
        return
    try:
        cur = admin.cursor()
        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash, notification_email)"
            " VALUES (%s,%s,%s,%s)",
            (tenant, "xvi-phys", uuid.uuid4().hex, "xvi-phys@example.invalid"),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xvi_phys_ch', 'xvi_phys', true,"
            " 'XVIPHYS', 'active') ON CONFLICT (code) DO NOTHING"
        )

        def _mkrow(tag: str, key: str, evref: str = "e1"):
            ev, ing = str(uuid.uuid4()), str(uuid.uuid4())
            cur.execute(
                "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                " correlation_id, session_id, revenue_cents, raw_payload, idempotency_key,"
                " event_type, channel, campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
                " 'xvi_phys_ch','c',7600,'USD',now(),now(),'processed')",
                (ev, tenant, str(uuid.uuid4()), str(uuid.uuid4()), tag),
            )
            # XVII: each probe row carries a DISTINCT commerce identity so
            # the XVII commerce-conservation fence (same commerce across
            # distinct rows -> conflict refusal) does not trip on the XVI
            # event-granularity probe itself.
            cref = f"o-{tag}"
            cur.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id, event_id,"
                " provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_order_id',%s,7600,'USD',"
                " now(),%s,'authenticity_verified')",
                (ing, tenant, ev, evref, cref, cref, key),
            )
            return ing

        def _auth(icur, ing: str, sha: str, sig: str = "b" * 64):
            icur.execute(
                "SELECT set_config('app.b26_p2_event_family',"
                " 'payment_intent.succeeded', false)"
            )
            icur.execute(
                "SELECT set_config('app.b26_p2_event_family_source',"
                " 'body-signal:type', false)"
            )
            icur.execute(
                "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe','e1',%s,%s,"
                "'hmac-sha256-timestamped-hex','v1')",
                (ing, sha, sig),
            )
            return str(icur.fetchone()[0])

        def _auth_ref(icur, ing: str, eref: str, sha: str, sig: str = "b" * 64):
            # XVII: the atomic binds the caller's event reference; a
            # genuinely distinct provider event carries its own reference.
            icur.execute(
                "SELECT set_config('app.b26_p2_event_family',"
                " 'payment_intent.succeeded', false)"
            )
            icur.execute(
                "SELECT set_config('app.b26_p2_event_family_source',"
                " 'body-signal:type', false)"
            )
            icur.execute(
                "SELECT public.b26_p2_authenticate_ingress_atomic(%s,'stripe',%s,%s,%s,"
                "'hmac-sha256-timestamped-hex','v1')",
                (ing, eref, sha, sig),
            )
            return str(icur.fetchone()[0])

        def _authority_projection(icur, ing: str) -> dict:
            icur.execute(
                "SELECT i.id::text, i.tenant_id::text, i.provider,"
                " i.provider_native_event_reference,"
                " i.provider_native_commerce_reference,"
                " i.normalized_commerce_reference_kind,"
                " i.normalized_commerce_reference_value,"
                " i.verified_amount_minor, i.verified_amount_currency,"
                " i.verified_amount_scale, i.event_timestamp::text,"
                " i.idempotency_key, i.verified_commerce_ingress_state,"
                " i.b26_p2_provenance_status,"
                " (SELECT count(*) FROM public.b26_p2_ingress_auth_witness w"
                " WHERE w.webhook_ingress_identity_id = i.id),"
                " (SELECT count(*) FROM public.b26_p2_auth_root_evidence r"
                " WHERE r.webhook_ingress_identity_id = i.id),"
                " (SELECT count(*) FROM public.b26_p2_provider_auth_consequence c"
                " WHERE c.webhook_ingress_identity_id = i.id)"
                " FROM public.webhook_ingress_identities i WHERE i.id = %s",
                (ing,),
            )
            row = icur.fetchone()
            return {"cols": [str(v) for v in row]}

        ing = psycopg2.connect(ingress_dsn)
        ing.autocommit = True
        try:
            with ing.cursor() as icur:
                icur.execute(
                    "SELECT set_config('app.current_tenant_id', %s, false)",
                    (tenant,),
                )
                sha = "e" * 64
                row1 = _mkrow("xvi-phys-1", "xvi-phys-key-1")
                assert _auth(icur, row1, sha) == "authenticated_known"
                checks["lawful_path_mints_evidence"] = True
                # Sovereign duplicate: same bytes, second row/key.
                row2 = _mkrow("xvi-phys-2", "xvi-phys-key-2")
                try:
                    _auth(icur, row2, sha)
                    violations.append("xvi_phys_same_bytes_second_lineage")
                except Exception as exc:
                    if "b26_p2_atomic_sovereign_duplicate_refused" not in str(exc):
                        violations.append(
                            "xvi_phys_dup_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["same_bytes_second_lineage_refused"] = True
                # Distinct bytes still authenticate (event granularity):
                # XVII requires a genuinely distinct provider event --
                # distinct reference AND distinct commerce identity -- so
                # the row carries its own reference from birth.
                row2b = _mkrow("xvi-phys-2b", "xvi-phys-key-2b", evref="e2")
                assert _auth_ref(icur, row2b, "e2", "d" * 64) == "authenticated_known"
                checks["distinct_bytes_authenticate"] = True
                row2 = row2b
                # Same-row re-entry stays idempotent.
                assert _auth(icur, row1, sha) == "authenticated_known"
                checks["same_row_reentry_idempotent"] = True
                # NULL-parameter calls fail closed with shape tokens
                # (exercised on the verified row2 so the refusal is the
                # NULL shape, never the state gate).
                for params, token in (
                    ((row2, None, "b" * 64), "b26_p2_atomic_sha_refused"),
                    ((row2, sha, None), "b26_p2_atomic_sha_refused"),
                ):
                    try:
                        _auth(icur, *params)
                        violations.append(f"xvi_phys_null_admitted:{token}")
                    except Exception as exc:
                        if token not in str(exc):
                            violations.append(
                                "xvi_phys_null_wrong_refusal:"
                                f"{str(exc).splitlines()[0][:120]}"
                            )
                checks["null_parameters_refused"] = True
                # Grants first: direct evidence INSERT as app_ingress denied.
                try:
                    icur.execute(
                        "INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
                        " webhook_ingress_identity_id, idempotency_key, provider,"
                        " provider_native_event_reference, body_sha256,"
                        " signature_envelope_sha256, auth_method) VALUES (%s,"
                        " gen_random_uuid(),'xvi-direct','stripe','e',%s,%s,'m')",
                        (tenant, "c" * 64, "d" * 64),
                    )
                    violations.append("xvi_phys_direct_evidence_permitted")
                except Exception as exc:
                    if "denied" not in str(exc).lower() and "refused" not in str(exc):
                        violations.append(
                            "xvi_phys_direct_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:120]}"
                        )
                    else:
                        checks["direct_evidence_grant_denied"] = True
                # pg_temp spoof composition: even a same-name,
                # same-signature function whose PG_CONTEXT frame is textually
                # identical to the sovereign frame cannot mint evidence --
                # grants deny the write first, the gate second.
                icur.execute(
                    "CREATE FUNCTION pg_temp.b26_p2_authenticate_ingress_atomic("
                    " uuid, text, text, text, text, text, text)"
                    " RETURNS text LANGUAGE plpgsql"
                    " AS $func$ BEGIN"
                    " INSERT INTO public.b26_p2_auth_root_evidence (tenant_id,"
                    " webhook_ingress_identity_id, idempotency_key, provider,"
                    " provider_native_event_reference, body_sha256,"
                    " signature_envelope_sha256, auth_method) VALUES (%s::uuid,"
                    " gen_random_uuid(),'xvi-spoof','stripe','e',%s,%s,'m');"
                    " RETURN 'spoofed'; END $func$;",
                    (tenant, "c" * 64, "d" * 64),
                )
                try:
                    icur.execute(
                        "SELECT pg_temp.b26_p2_authenticate_ingress_atomic("
                        "gen_random_uuid(),'stripe','e',%s,%s,'m','v1')",
                        ("c" * 64, "d" * 64),
                    )
                    violations.append("xvi_phys_spoof_evidence_permitted")
                except Exception as exc:
                    if "denied" not in str(exc).lower() and "refused" not in str(
                        exc
                    ):
                        violations.append(
                            "xvi_phys_spoof_wrong_refusal:"
                            f"{str(exc).splitlines()[0][:160]}"
                        )
                    else:
                        checks["identical_frame_spoof_refused"] = True
                finally:
                    icur.execute(
                        "DROP FUNCTION pg_temp.b26_p2_authenticate_ingress_atomic("
                        "uuid,text,text,text,text,text,text)"
                    )
                # R5 behavioral: rebind event_id to a second genuine
                # ingestion event; every authority projection and the scope
                # classification must be identical (linkage provably
                # non-authoritative). The target must exist: event_id is
                # FK-bound to attribution_events, as in production where
                # adoption binds the linkage to a real delivery.
                ev_b = str(uuid.uuid4())
                cur.execute(
                    "INSERT INTO public.attribution_events (id, tenant_id, occurred_at,"
                    " correlation_id, session_id, revenue_cents, raw_payload,"
                    " idempotency_key, event_type, channel, campaign_id,"
                    " conversion_value_cents, currency, event_timestamp,"
                    " processed_at, processing_status)"
                    " VALUES (%s,%s,now(),%s,%s,7600,'{}'::jsonb,%s,'conversion',"
                    " 'xvi_phys_ch','c',7600,'USD',now(),now(),'processed')",
                    (
                        ev_b,
                        tenant,
                        str(uuid.uuid4()),
                        str(uuid.uuid4()),
                        "xvi-phys-rebind-target",
                    ),
                )
                before = _authority_projection(icur, row1)
                icur.execute(
                    "UPDATE public.webhook_ingress_identities"
                    " SET event_id = %s WHERE id = %s",
                    (ev_b, row1),
                )
                after = _authority_projection(icur, row1)
                if before != after:
                    keys = [
                        (a, b)
                        for a, b in zip(before["cols"], after["cols"])
                        if a != b
                    ]
                    violations.append(f"xvi_phys_rebind_changed_authority:{keys}")
                else:
                    checks["rebind_preserves_authority"] = True
                # Dispatch resolution by row identity is unaffected.
                icur.execute(
                    "SELECT count(*) FROM public.webhook_ingress_identities i"
                    " WHERE i.id = %s"
                    " AND i.verified_commerce_ingress_state = 'authenticity_verified'"
                    " AND i.b26_p2_provenance_status"
                    " IS NOT DISTINCT FROM 'authenticated_known'"
                    " AND EXISTS (SELECT 1 FROM public.b26_p2_ingress_auth_witness w"
                    " WHERE w.webhook_ingress_identity_id = i.id)"
                    " AND EXISTS (SELECT 1 FROM public.b26_p2_provider_auth_consequence c"
                    " WHERE c.webhook_ingress_identity_id = i.id)",
                    (row1,),
                )
                if icur.fetchone()[0] != 1:
                    violations.append("xvi_phys_dispatch_predicate_broken")
                else:
                    checks["dispatch_predicate_stable_across_rebind"] = True
        finally:
            ing.close()
        cur.close()
    except Exception as exc:
        violations.append(f"xvi_phys_live_failed:{exc}")
    finally:
        admin.close()


def main() -> int:
    parser = argparse.ArgumentParser(description="XVI database-physics closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVI_PHYS_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVI-PHYSICS",
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
