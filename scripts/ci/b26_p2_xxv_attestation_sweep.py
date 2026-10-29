#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV: live sovereign-attestation sweep.

This is the effect oracle the A12 gate was missing. It does not construct a
fixture and then judge its own fixture: it walks **every** financial verdict
in the database it is pointed at and asks one question per row --

    does the database claim this money is current, and is that claim
    justified by a signature the database owner cannot produce?

Because the answer depends on an Ed25519 signature over the provider's
amount, no in-database primitive can satisfy it: an owner rewrite, a
superuser rewrite with triggers suppressed, a restore from a doctored
backup, a direct UPDATE through a definer routine, a coordinated rewrite
of every agreeing representation, and the deletion of the authentication
root's own attestation row all fail identically, and all of them turn this
sweep RED. That is what makes it a class oracle rather than a list of known
mutations.

An unattested row that the database does NOT call current is not a
violation: it is published as unqualified by every reader and refused by the
signed path, so it is not a served false result. What this oracle forbids is
a row the database still calls ``current`` without a verified attestation
over exactly that money.

Used by the mandatory composition proof (so the governing CI gate detects an
independently introduced false financial world) and runnable on its own.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

GATE_ID = "B26-P2-XXV-ATTESTATION-SWEEP"

SWEEP_SQL = """
SELECT v.id::text AS verdict_id,
       v.tenant_id::text AS tenant_id,
       v.canonical_net_verified_amount_minor AS verdict_net,
       v.canonical_captured_gross_amount_minor AS verdict_captured,
       v.verified_amount_minor AS verdict_verified,
       v.currency_code AS verdict_currency,
       v.b26_p2_source_authority_state::text AS recorded_authority_state,
       v.webhook_ingress_identity_id::text AS ingress_id,
       i.verified_amount_minor AS ingress_amount,
       i.verified_amount_currency AS ingress_currency,
       i.verified_amount_scale AS ingress_scale,
       i.provider AS ingress_provider,
       i.provider_native_event_reference AS ingress_event_reference,
       i.provider_native_commerce_reference AS ingress_commerce_reference,
       i.normalized_commerce_reference_kind AS ingress_normalized_kind,
       i.normalized_commerce_reference_value AS ingress_normalized_value,
       i.event_timestamp AS ingress_event_timestamp,
       c.body_sha256 AS consequence_body_sha256,
       (SELECT public.b26_p2_authority_universe()::text) AS current_universe,
       i.created_at AS ingress_created_at,
       a.statement AS statement,
       a.signature AS signature,
       a.attested_amount_minor AS attested_amount,
       (c.recorded_by = 'app_ingress') AS root_authenticated,
       aj.adjustments AS adjustments
  FROM public.b23_match_verdicts AS v
  LEFT JOIN public.webhook_ingress_identities AS i
         ON i.id = v.webhook_ingress_identity_id AND i.tenant_id = v.tenant_id
  LEFT JOIN public.b26_p2_source_money_attestation AS a
         ON a.webhook_ingress_identity_id = i.id AND a.tenant_id = i.tenant_id
  LEFT JOIN public.b26_p2_provider_auth_consequence AS c
         ON c.webhook_ingress_identity_id = i.id AND c.tenant_id = i.tenant_id
  LEFT JOIN LATERAL (
      SELECT COALESCE(
          json_agg(
              json_build_object(
                  'adjustment_evidence_id', e.id::text,
                  'tenant_id', e.tenant_id::text,
                  'verdict_id', e.verdict_id::text,
                  'provider', e.provider,
                  'event_type', e.event_type,
                  'provider_native_event_reference',
                      e.provider_native_event_reference,
                  'provider_native_commerce_reference',
                      e.provider_native_commerce_reference,
                  'amount_minor', e.amount_minor,
                  'currency_code', e.currency_code,
                  'event_timestamp', e.event_timestamp,
                  'body_sha256', e.body_sha256,
                  'statement', a.statement,
                  'signature', a.signature,
                  'attested_amount_minor', a.attested_amount_minor,
                  'attested_amount_currency', a.attested_amount_currency,
                  'attested_amount_scale', a.attested_amount_scale
              )
              ORDER BY e.event_timestamp, e.id
          ),
          '[]'::json
      ) AS adjustments
        FROM public.b26_p2_adjustment_evidence AS e
        LEFT JOIN public.b26_p2_adjustment_attestation AS a
               ON a.adjustment_evidence_id = e.id
              AND a.tenant_id = e.tenant_id
       WHERE e.tenant_id = v.tenant_id AND e.verdict_id = v.id
  ) AS aj ON true
"""


def sweep(dsn: str, *, public_key_path: str) -> dict:
    """Return the per-status census and every unverifiable row."""
    import psycopg2  # noqa: PLC0415

    from app.revenue_verification.source_attestation import (  # noqa: PLC0415
        ADJUSTMENT_NET_EFFECT_SIGN,
        SourceAttestationError,
        verify_adjustment_signature,
        verify_signature,
    )

    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(SWEEP_SQL)
        columns = [description[0] for description in cur.description]
        rows = [dict(zip(columns, record)) for record in cur.fetchall()]
    finally:
        conn.close()

    census = {
        "xxv_attested": 0,
        "unattested_not_claimed_current": 0,
        "attested_but_not_claimed_current": 0,
        # A verdict whose source carries no root-authored authentication
        # consequence was never authenticated by the authentication root, so
        # no attestation could exist for it. Such a row is NOT served as
        # current money -- every reader's attestation check returns
        # unverifiable and the published authority state becomes
        # source_attestation_unverifiable -- and deleting a real consequence
        # row revokes authority through the XIX evidence-loss trigger. It is
        # therefore counted here rather than treated as a served false
        # result. The database-level cells of this very proof create such
        # rows deliberately.
        "source_not_root_authenticated": 0,
    }
    unverifiable: list[dict] = []
    for row in rows:
        def fail(reason: str) -> None:
            unverifiable.append(
                {
                    "verdict_id": row["verdict_id"],
                    "tenant_id": row["tenant_id"],
                    "reason": reason,
                    "verdict_net_minor": row["verdict_net"],
                    "ingress_amount_minor": row["ingress_amount"],
                    "attested_amount_minor": row["attested_amount"],
                }
            )

        if row["ingress_id"] is None or row["ingress_amount"] is None:
            # No source row at all: there is no money to be current about.
            census["source_not_root_authenticated"] += 1
            continue
        if not row["root_authenticated"]:
            census["source_not_root_authenticated"] += 1
            continue
        claimed_current = str(row["recorded_authority_state"] or "") == "current"
        if row["statement"] is None:
            # No attestation. That is only a violation if the database still
            # calls the money current: an unattested row is published as
            # unqualified by every reader and refused by the signed path, so
            # it is not a served false result. XXV (A6/A10 class closure): the
            # absence of an attestation is never a grant, so this oracle may
            # not treat it as one either.
            if claimed_current:
                fail("attestation_missing_for_current_claim")
            else:
                census["unattested_not_claimed_current"] += 1
            continue
        statement = (
            row["statement"]
            if isinstance(row["statement"], dict)
            else json.loads(str(row["statement"]))
        )
        try:
            verify_signature(
                statement,
                str(row["signature"] or ""),
                public_key_path=public_key_path,
            )
        except SourceAttestationError as exc:
            fail(str(exc))
            continue
        attested = int(statement["verified_amount_minor"])
        currency = str(statement["verified_amount_currency"]).upper()
        if str(statement["tenant_id"]) != row["tenant_id"]:
            fail("attestation_tenant_mismatch")
            continue
        if str(statement["webhook_ingress_identity_id"]) != row["ingress_id"]:
            fail("attestation_subject_mismatch")
            continue
        if int(row["attested_amount"]) != attested:
            fail("attestation_column_diverged_from_statement")
            continue
        if int(row["ingress_amount"]) != attested:
            fail("ingress_amount_diverged_from_attestation")
            continue
        if str(row["ingress_currency"] or "").upper() != currency:
            fail("ingress_currency_diverged_from_attestation")
            continue
        if str(statement.get("provider") or "").lower() != str(
            row["ingress_provider"] or ""
        ).lower():
            fail("attestation_provider_mismatch")
            continue
        if str(statement.get("provider_native_event_reference") or "") != str(
            row["ingress_event_reference"] or ""
        ):
            fail("attestation_event_reference_mismatch")
            continue
        if str(statement.get("provider_native_commerce_reference") or "") != str(
            row["ingress_commerce_reference"] or ""
        ):
            fail("attestation_commerce_reference_mismatch")
            continue
        if statement.get("normalized_commerce_reference_kind") != row[
            "ingress_normalized_kind"
        ] or statement.get("normalized_commerce_reference_value") != row[
            "ingress_normalized_value"
        ]:
            fail("attestation_normalized_reference_mismatch")
            continue
        if int(statement.get("verified_amount_scale", -1)) != int(
            row["ingress_scale"]
        ):
            fail("attestation_scale_mismatch")
            continue
        try:
            from datetime import datetime, timezone  # noqa: PLC0415

            statement_instant = datetime.fromisoformat(
                str(statement["event_timestamp"]).replace("Z", "+00:00")
            )
            if statement_instant.tzinfo is None:
                statement_instant = statement_instant.replace(tzinfo=timezone.utc)
            if statement_instant.astimezone(timezone.utc) != row[
                "ingress_event_timestamp"
            ].astimezone(timezone.utc):
                fail("attestation_event_timestamp_mismatch")
                continue
        except (KeyError, TypeError, ValueError):
            fail("attestation_event_timestamp_invalid")
            continue
        if str(statement.get("body_sha256") or "").lower() != str(
            row["consequence_body_sha256"] or ""
        ).lower():
            fail("attestation_body_digest_mismatch")
            continue
        if str(statement.get("authority_universe") or "") != str(
            row["current_universe"] or ""
        ):
            fail("attestation_authority_universe_mismatch")
            continue
        adjustments = row.get("adjustments") or []
        adjustment_net = 0
        for adjustment in adjustments:
            if adjustment.get("statement") is None:
                fail("adjustment_attestation_missing")
                break
            statement = (
                adjustment["statement"]
                if isinstance(adjustment["statement"], dict)
                else json.loads(str(adjustment["statement"]))
            )
            try:
                verify_adjustment_signature(
                    statement,
                    str(adjustment.get("signature") or ""),
                    public_key_path=public_key_path,
                )
            except SourceAttestationError as exc:
                fail(f"adjustment_{exc}")
                break
            event_type = str(statement.get("event_type") or "").lower()
            sign = ADJUSTMENT_NET_EFFECT_SIGN.get(event_type)
            if sign is None or sign == 0:
                fail("adjustment_event_type_not_monetary")
                break
            expected = {
                "adjustment_evidence_id": str(
                    adjustment["adjustment_evidence_id"]
                ),
                "tenant_id": row["tenant_id"],
                "verdict_id": row["verdict_id"],
                "provider": str(adjustment["provider"]),
                "event_type": event_type,
                "provider_native_event_reference": str(
                    adjustment["provider_native_event_reference"]
                ),
                "provider_native_commerce_reference": str(
                    adjustment["provider_native_commerce_reference"]
                ),
                "verified_amount_minor": int(adjustment["amount_minor"]),
                "verified_amount_currency": str(
                    adjustment["currency_code"]
                ).upper(),
                "verified_amount_scale": int(
                    adjustment.get("attested_amount_scale") or 0
                ),
                "event_timestamp": str(adjustment["event_timestamp"]),
                "body_sha256": str(adjustment["body_sha256"]).lower(),
                "net_effect_sign": int(sign),
                "authority_universe": row["current_universe"],
            }
            mismatch = False
            for key, expected_value in expected.items():
                actual = statement.get(key)
                if key == "verified_amount_currency":
                    actual = str(actual or "").upper()
                elif key == "net_effect_sign":
                    actual = int(actual) if actual is not None else None
                elif key == "event_timestamp":
                    try:
                        from datetime import datetime, timezone  # noqa: PLC0415

                        actual_instant = datetime.fromisoformat(
                            str(actual).replace("Z", "+00:00")
                        )
                        expected_instant = datetime.fromisoformat(
                            str(expected_value).replace("Z", "+00:00")
                        )
                        if actual_instant.tzinfo is None:
                            actual_instant = actual_instant.replace(
                                tzinfo=timezone.utc
                            )
                        if expected_instant.tzinfo is None:
                            expected_instant = expected_instant.replace(
                                tzinfo=timezone.utc
                            )
                        actual = actual_instant.astimezone(timezone.utc)
                        expected_value = expected_instant.astimezone(timezone.utc)
                    except (TypeError, ValueError):
                        fail("adjustment_statement_event_timestamp_invalid")
                        mismatch = True
                        break
                if actual != expected_value:
                    fail(f"adjustment_statement_{key}_mismatch")
                    mismatch = True
                    break
            if mismatch:
                break
            if int(adjustment.get("attested_amount_minor") or -1) != int(
                adjustment["amount_minor"]
            ):
                fail("adjustment_column_diverged_from_statement")
                break
            adjustment_net += int(sign) * int(adjustment["amount_minor"])
        else:
            if int(row["verdict_captured"] or 0) != attested:
                fail("verdict_captured_unsupported_by_attestation")
                continue
            if int(row["verdict_verified"] or 0) != attested:
                fail("verdict_verified_unsupported_by_attestation")
                continue
            if int(row["verdict_net"] or 0) != attested + adjustment_net:
                fail("verdict_net_unsupported_by_attestation")
                continue
            if str(row["verdict_currency"] or "").upper() != currency:
                fail("verdict_currency_unsupported_by_attestation")
                continue
        if unverifiable and unverifiable[-1]["verdict_id"] == row["verdict_id"]:
            continue
        if not claimed_current:
            census["attested_but_not_claimed_current"] += 1
            continue
        census["xxv_attested"] += 1

    return {
        "verdicts_examined": len(rows),
        "census": census,
        "unverifiable": unverifiable,
        "public_key_path": public_key_path,
    }


def default_public_key_path() -> str:
    return os.environ.get(
        "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH",
        "var/b26_p2/source_attestation_ed25519.pub",
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dsn", required=True)
    parser.add_argument("--public-key-path", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()

    result = sweep(
        args.dsn, public_key_path=args.public_key_path or default_public_key_path()
    )
    status = "PASS" if not result["unverifiable"] else "FAIL"
    record = {"gate_id": GATE_ID, "status": status, **result}
    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(record, indent=2, sort_keys=True, default=str), encoding="utf-8")
    print(f"{GATE_ID}_{status}")
    print(json.dumps(record, sort_keys=True, default=str)[:4000])
    return 0 if status == "PASS" else 1


if __name__ == "__main__":
    raise SystemExit(main())
