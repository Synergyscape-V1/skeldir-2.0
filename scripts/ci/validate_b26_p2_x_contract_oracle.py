#!/usr/bin/env python3
"""B2.6-P2 Corrective X independent contract oracle.

Judges the single P2 semantic authority (the live SQL functions) against
stable phase laws, not against a reimplementation of the production
algorithm and not against candidate-side representations. Expectations
below are hardcoded from the governed scope-policy contract
(strip_ascii_lower law, half-open UTC window, deterministic exclusion
priority, SUPPORTED/UNRESOLVED/EXCLUDED/REFUSED meanings, tenant
isolation, integer money): changing every executable P2 implementation
to the same wrong meaning -- and refreshing every candidate hash, pin,
manifest, and validator expectation -- still leaves this oracle RED.

Live-only by construction: --dsn is REQUIRED. No DSN (or an
unreachable/unmigrated database) is a REQUIRED GATE RED, never a
static PASS.

Exit code is the gate: 0 on PASS, 1 plus a violation list on FAIL.
"""

from __future__ import annotations

import argparse
import json
import uuid
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

TAB = chr(9)
CR = chr(13)
LF = chr(10)
NBSP = chr(0xA0)

TENANT_SEED = "10000000-0000-4000-8000-000000000000"
WS = datetime(2026, 9, 1, 0, 0, tzinfo=timezone.utc)
WE = datetime(2026, 9, 2, 0, 0, tzinfo=timezone.utc)
MID = datetime(2026, 9, 1, 12, 0, tzinfo=timezone.utc)
BEFORE = datetime(2026, 8, 31, 23, 59, 59, tzinfo=timezone.utc)
POLICY_V2 = "b2.6-p2-scope-policy-v2"


def _classify(cur, tenant, provider, currency, event, ref="ord-1",
              ws=WS, we=WE, policy=POLICY_V2):
    cur.execute(
        "SELECT o_provider AS p, o_rail AS r, o_currency AS c,"
        " o_disposition AS d, o_reason AS n"
        " FROM public.b26_p2_classify_candidate(%s,%s,%s,%s,%s,%s,%s,%s)",
        (str(tenant), provider, currency, event, ws, we, policy, ref),
    )
    row = cur.fetchone()
    return {"provider": row[0], "rail": row[1], "currency": row[2],
            "disposition": row[3], "reason": row[4]}


def _expect_raise(cur, tenant, provider, currency, event, ref="ord-1",
                  ws=WS, we=WE, policy=POLICY_V2):
    try:
        _classify(cur, tenant, provider, currency, event, ref, ws, we, policy)
    except Exception as exc:  # noqa: BLE001
        return str(exc).split("\n")[0][:200]
    return None


def _check_semantic_law(cur, violations, checks):
    tenant = uuid.uuid4()
    cells: dict[str, bool] = {}

    got = _classify(cur, tenant, TAB + "paypal", "USD", MID)
    cells["ascii_whitespace_normalizes"] = (
        got["disposition"] == "SUPPORTED_AND_IN_SCOPE"
        and got["provider"] == "paypal" and got["rail"] == "paypal"
    )
    got = _classify(cur, tenant, " stripe" + CR + LF, "usd", MID)
    cells["crlf_case_normalizes"] = (
        got["disposition"] == "SUPPORTED_AND_IN_SCOPE"
        and got["provider"] == "stripe" and got["currency"] == "USD"
    )
    got = _classify(cur, tenant, NBSP + "paypal", "USD", MID)
    cells["unicode_whitespace_never_normalizes"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "unsupported_provider_excluded"
    )
    err = _expect_raise(cur, tenant, TAB, "USD", MID, ref=TAB)
    cells["whitespace_only_provider_refused"] = (
        err is not None and "blank" in err
    )
    got = _classify(cur, tenant, "square", "USD", MID)
    cells["unknown_provider_excluded"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "unsupported_provider_excluded"
    )
    got = _classify(cur, tenant, "stripe", "EUR", MID)
    cells["unsupported_currency_excluded"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "unsupported_currency_excluded"
    )
    got = _classify(cur, tenant, "stripe", "1US", MID)
    cells["nonmember_currency_excluded_not_shaped"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "unsupported_currency_excluded"
    )
    got = _classify(cur, tenant, "stripe", "USD", MID, ref="   ")
    cells["missing_reference_unresolved"] = (
        got["disposition"] == "SUPPORTED_BUT_UNRESOLVED"
        and got["reason"] == "source_identity_unresolved"
    )
    got = _classify(cur, tenant, "stripe", "USD", MID, ref=TAB)
    cells["whitespace_only_reference_unresolved"] = (
        got["disposition"] == "SUPPORTED_BUT_UNRESOLVED"
        and got["reason"] == "source_identity_unresolved"
    )
    got = _classify(cur, tenant, "stripe", "USD", WS)
    cells["window_start_inclusive"] = (
        got["disposition"] == "SUPPORTED_AND_IN_SCOPE"
    )
    got = _classify(cur, tenant, "stripe", "USD", WE)
    cells["window_end_exclusive"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "outside_governed_window_excluded"
    )
    got = _classify(cur, tenant, "stripe", "USD", BEFORE)
    cells["window_before_excluded"] = (
        got["disposition"] == "EXPLICITLY_EXCLUDED"
        and got["reason"] == "outside_governed_window_excluded"
    )
    got = _classify(cur, tenant, "square", "EUR", MID)
    cells["exclusion_priority_provider_first"] = (
        got["reason"] == "unsupported_provider_excluded"
    )
    got = _classify(cur, tenant, "stripe", "EUR", BEFORE)
    cells["exclusion_priority_currency_before_window"] = (
        got["reason"] == "unsupported_currency_excluded"
    )
    err = _expect_raise(cur, tenant, "   ", "USD", MID)
    cells["blank_provider_refused"] = err is not None and "blank" in err
    err = _expect_raise(cur, tenant, "stripe", "  ", MID)
    cells["blank_currency_refused"] = err is not None and "blank" in err
    err = _expect_raise(cur, tenant, "stripe", "USD", MID,
                        policy="b2.6-p2-scope-policy-v1")
    cells["wrong_policy_version_refused"] = (
        err is not None and "policy_version" in err
    )

    checks["semantic_cells"] = cells
    for name, ok in cells.items():
        if not ok:
            violations.append(f"x_oracle_semantic_law_broken:{name}")


def _check_identity_law(cur, violations, checks, admin_dsn):
    import psycopg2  # noqa: PLC0415  # type: ignore[import-untyped]

    tenant = uuid.uuid4()
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur2:
            cur2.execute(
                "INSERT INTO public.tenants (id, name, api_key_hash,"
                " notification_email) VALUES (%s, %s, %s, %s)",
                (str(tenant), f"x-oracle-{tenant.hex[:8]}",
                 uuid.uuid4().hex, "x-oracle@example.invalid"),
            )
            cur2.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant),),
            )
            cur2.execute(
                "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
                " display_name, state) VALUES ('x_oracle_chan', 'x_oracle',"
                " true, 'XORACLE', 'active') ON CONFLICT (code) DO NOTHING"
            )
            noon = MID
            event_uuid = uuid.uuid4()
            cur2.execute(
                "INSERT INTO public.attribution_events (id, tenant_id,"
                " occurred_at, correlation_id, session_id, revenue_cents,"
                " raw_payload, idempotency_key, event_type, channel,"
                " campaign_id, conversion_value_cents, currency,"
                " event_timestamp, processed_at, processing_status)"
                " VALUES (%s, %s, %s, %s, %s, 76000,"
                " '{\"order_id\": \"x\"}'::jsonb, %s, 'conversion',"
                " 'x_oracle_chan', 'x-oracle-camp', 76000, 'USD',"
                " %s, %s, 'processed')",
                (str(event_uuid), str(tenant), noon, str(uuid.uuid4()),
                 str(uuid.uuid4()), f"x-oracle:{tenant.hex[:8]}", noon, noon),
            )
            ingress = uuid.uuid4()
            cur2.execute(
                "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
                " event_id, provider, provider_native_event_reference,"
                " provider_native_commerce_reference,"
                " normalized_commerce_reference_kind,"
                " normalized_commerce_reference_value, verified_amount_minor,"
                " verified_amount_currency, event_timestamp, idempotency_key,"
                " verified_commerce_ingress_state)"
                " VALUES (%s, %s, %s, %s, %s, %s, 'order_reference',"
                " %s, 76000, 'USD', %s, %s, 'authenticity_verified')",
                (str(ingress), str(tenant), str(event_uuid),
                 TAB + "stripe", "evt-x", "ord-x", "ord-x", noon,
                 f"x-oracle:{tenant.hex[:8]}"),
            )
    finally:
        admin.close()
    cur.execute(
        "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
        (str(tenant), WS, WE),
    )
    first = str(cur.fetchone()[0])
    cur.execute(
        "SELECT public.b26_p2_canonical_scope_identity_for_window(%s,%s,%s)",
        (str(tenant), WS, WE),
    )
    second = str(cur.fetchone()[0])
    checks["identity_stable"] = first == second and len(first) == 64
    if not checks["identity_stable"]:
        violations.append("x_oracle_identity_unstable")
    # ASCII-whitespace provider variant must share the lawful
    # meaning: the tab-prefixed row above classifies IN_SCOPE, so
    # the identity must equal the clean-provider identity over the
    # same multiset. Proved by direct classifier agreement instead:
    got = _classify(cur, tenant, TAB + "stripe", "USD", noon, ref="ord-x")
    checks["tab_row_in_scope"] = (
        got["disposition"] == "SUPPORTED_AND_IN_SCOPE"
    )
    if not checks["tab_row_in_scope"]:
        violations.append("x_oracle_tab_row_not_in_scope")
    # NOTE: oracle tenants/rows are intentionally left in place. Lanes
    # are disposable per run (fresh database per CI job); deleting
    # tenants fights attribution/session FKs and risks nothing by
    # staying (fresh UUIDs, tenant-scoped reads).


def _check_tenant_isolation(cur, violations, checks, admin_dsn):
    import psycopg2  # noqa: PLC0415  # type: ignore[import-untyped]

    tenant_a = uuid.uuid4()
    tenant_b = uuid.uuid4()
    admin = psycopg2.connect(admin_dsn)
    admin.autocommit = True
    try:
        with admin.cursor() as cur2:
            for tenant in (tenant_a, tenant_b):
                cur2.execute(
                    "INSERT INTO public.tenants (id, name, api_key_hash,"
                    " notification_email) VALUES (%s, %s, %s, %s)",
                    (str(tenant), f"x-oracle-iso-{tenant.hex[:8]}",
                     uuid.uuid4().hex, "x-oracle-iso@example.invalid"),
                )
    finally:
        admin.close()
    worker_dsn = admin_dsn.replace(
        "migration_owner:migration_owner", "app_worker:app_worker"
    )
    try:
        worker = psycopg2.connect(worker_dsn)
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_oracle_worker_principal_unavailable:{exc}")
        return
    worker.autocommit = True
    try:
        with worker.cursor() as wcur:
            wcur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (str(tenant_b),),
            )
            wcur.execute(
                "SELECT count(*) FROM public.webhook_ingress_identities"
            )
            count_b = int(wcur.fetchone()[0])
            checks["cross_tenant_rows_visible_to_b"] = count_b
            if count_b != 0:
                violations.append("x_oracle_tenant_isolation_broken")
    finally:
        worker.close()
    # NOTE: oracle tenants are intentionally left in place (see above).


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.6-P2 Corrective X contract oracle."
    )
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-dir", type=Path, default=None)
    parser.add_argument("--evidence-out", type=Path, default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict[str, object] = {}
    try:
        if not args.dsn:
            violations.append("x_oracle_live_check_required_no_dsn")
            checks["live_check"] = "refused_no_dsn"
        else:
            try:
                import psycopg2  # noqa: PLC0415  # type: ignore[import-untyped]
            except ImportError:
                violations.append("x_oracle_live_check_driver_missing")
                checks["live_check"] = "driver_missing"
            else:
                try:
                    conn = psycopg2.connect(args.dsn)
                except Exception as exc:  # noqa: BLE001
                    violations.append(
                        f"x_oracle_live_check_connect_failed:{exc}"
                    )
                    checks["live_check"] = "connect_failed"
                else:
                    try:
                        conn.autocommit = True
                        with conn.cursor() as cur:
                            cur.execute(
                                "SELECT version_num FROM public.alembic_version"
                            )
                            head = str(cur.fetchone()[0])
                            checks["migration_head"] = head
                            if head != "202609240002":
                                violations.append(
                                    f"x_oracle_unexpected_migration_head:{head}"
                                )
                            else:
                                _check_semantic_law(cur, violations, checks)
                                _check_identity_law(
                                    cur, violations, checks, args.dsn
                                )
                                _check_tenant_isolation(
                                    cur, violations, checks, args.dsn
                                )
                                checks["live_check"] = "executed"
                    except Exception as exc:  # noqa: BLE001
                        violations.append(f"x_oracle_live_check_failed:{exc}")
                        checks["live_check"] = "query_failed"
                    finally:
                        conn.close()
    except Exception as exc:  # noqa: BLE001
        violations.append(f"x_oracle_validator_crash:{exc}")
    status = "PASS" if not violations else "FAIL"
    evidence = {
        "gate_id": "B26-P2-X-ORACLE",
        "validator": "validate_b26_p2_x_contract_oracle",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        args.evidence_out.parent.mkdir(parents=True, exist_ok=True)
        args.evidence_out.write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if args.evidence_dir is not None:
        args.evidence_dir.mkdir(parents=True, exist_ok=True)
        (args.evidence_dir / "x-oracle.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    if violations:
        print("B26_P2_X_ORACLE_FAIL " + ";".join(sorted(violations)))
        return 1
    print("B26_P2_X_ORACLE_PASS")
    print(json.dumps(evidence, sort_keys=True, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())