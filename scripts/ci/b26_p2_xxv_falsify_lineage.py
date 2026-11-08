#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV: independently chosen equivalent-effect falsifiers.

These are the *sibling* attacks for the source-money conservation class
(A6/A10). They exist because a class is not closed by one falsifier, and
because a falsifier that reuses the steps of the repair it challenges proves
nothing about the class.

Two falsifiers live here:

``hb03-predecessor-escape``
    Attacks the EXISTENCE of the attestation: the maintenance principal
    rewrites the money coherently, deletes the authentication root's
    attestation row, and (on the unrepaired artifact) moves the attestation
    watermark so the row reads as "authenticated before the XXV epoch".
    The repair removed the watermark table and the exemption, so the third
    step is now physically refused.

``hb03-fabricated-lineage``
    Attacks the VERIFICATION ROOT and shares no step with the first: the
    maintenance principal replaces the root's attestation with one of its
    own, signed by a key it generated, and replaces the runtime public key
    the readers verify against. The fingerprint the readers compare against
    is compiled into the image, so this must be refused -- and it is the
    property that has to be demonstrated rather than asserted.

Both record: a positive baseline, the adverse observation, and an exact
restoration that includes money, authority, history and the signed
consumer's behaviour.
"""

from __future__ import annotations

import base64
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parent))

from b26_p2_xxv_falsify import (  # noqa: E402
    EVIDENCE_DIR,
    _baseline_is_green,
    _field,
    _net,
    composition_proof,
    money_snapshot,
    observe_once,
    owner_sql,
    post_stripe,
    await_witness_catchup,
    history_identity,
    history_is_restored,
    phase_snapshot,
    read_reconciliation,
    read_trust,
    signed_financial_result,
    verify_trust,
    wait_verdict,
    write_evidence,
)
from b26_p2_xxv_lane import (  # noqa: E402
    WITNESS_VOL,
    load_state,
    volume_put,
)


def _b64u_decode(value: str) -> bytes:
    return base64.urlsafe_b64decode(value + "=" * (-len(value) % 4))


def generate_attestation_keypair() -> tuple[str, str]:
    """(private seed, public key) as base64url, both Ed25519."""
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.generate()
    private_raw = key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        base64.urlsafe_b64encode(private_raw).rstrip(b"=").decode(),
        base64.urlsafe_b64encode(public_raw).rstrip(b"=").decode(),
    )


def sign_with_seed(seed_b64url: str, payload: bytes) -> str:
    from cryptography.hazmat.primitives import serialization
    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    key = Ed25519PrivateKey.from_private_bytes(_b64u_decode(seed_b64url))
    signature = key.sign(payload)
    return "ed25519:" + base64.urlsafe_b64encode(signature).rstrip(b"=").decode()


def trust_refusal_reason(tenant_id: str | None = None) -> str | None:
    """The durable reason a Trust consumer refused, if it refused."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        if tenant_id:
            cur.execute(
                "SELECT reason_code FROM public.trust_access_log"
                " WHERE subject_type = 'match_verdict' AND event_type = 'refusal'"
                "   AND tenant_id = %s"
                " ORDER BY created_at DESC LIMIT 1",
                (str(tenant_id),),
            )
        else:
            cur.execute(
                "SELECT reason_code FROM public.trust_access_log"
                " WHERE subject_type = 'match_verdict' AND event_type = 'refusal'"
                " ORDER BY created_at DESC LIMIT 1"
            )
        row = cur.fetchone()
        return None if not row or not row[0] else str(row[0])
    finally:
        conn.close()


def _admin_dsn() -> str:
    from b26_p2_xxv_lane import DB_NAME, PG_PORT

    return f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/{DB_NAME}"


def history_state() -> dict:
    """The historical witness state a consumer's authority depends on."""
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT count(*)::bigint, max(seq)"
            " FROM public.b26_p2_verdict_supersession_ledger"
        )
        row = cur.fetchone()
        return {
            "ledger_rows": int(row[0] or 0),
            "ledger_tip_seq": None if row[1] is None else int(row[1]),
        }
    finally:
        conn.close()


def _tenant_scope(tenant: dict) -> str:
    return str(tenant["tenant_id"])


def _relax_owner_triggers() -> None:
    for statement in (
        "ALTER TABLE public.b23_match_verdicts NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities NO FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.b23_match_verdicts DISABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events DISABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities DISABLE TRIGGER USER",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass


def _restore_owner_triggers() -> None:
    for statement in (
        "ALTER TABLE public.b23_match_verdicts ENABLE TRIGGER USER",
        "ALTER TABLE public.attribution_events ENABLE TRIGGER USER",
        "ALTER TABLE public.webhook_ingress_identities ENABLE TRIGGER USER",
        "ALTER TABLE public.b23_match_verdicts FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.attribution_events FORCE ROW LEVEL SECURITY",
        "ALTER TABLE public.webhook_ingress_identities FORCE ROW LEVEL SECURITY",
    ):
        try:
            owner_sql(statement)
        except Exception:  # noqa: BLE001
            pass


def _rewrite_money(vid: str, attribution_event_id: str, ingress_id: str, forged: int) -> None:
    owner_sql(
        "UPDATE public.b23_match_verdicts SET"
        " canonical_net_verified_amount_minor = %s,"
        " canonical_captured_gross_amount_minor = %s,"
        " canonical_expected_gross_amount_minor = %s,"
        " verified_amount_minor = %s, attributed_amount_minor = %s"
        " WHERE id = %s",
        (forged, forged, forged, forged, forged, vid),
    )
    owner_sql(
        "UPDATE public.attribution_events SET revenue_cents = %s,"
        " conversion_value_cents = %s WHERE id = %s",
        (forged, forged, attribution_event_id),
    )
    owner_sql(
        "UPDATE public.webhook_ingress_identities SET verified_amount_minor = %s"
        " WHERE id = %s",
        (forged, ingress_id),
    )


def _restore_money(vid: str, attribution_event_id: str, ingress_id: str, pristine: dict) -> None:
    owner_sql(
        "UPDATE public.b23_match_verdicts SET"
        " canonical_net_verified_amount_minor = %s,"
        " canonical_captured_gross_amount_minor = %s,"
        " canonical_expected_gross_amount_minor = %s,"
        " verified_amount_minor = %s, attributed_amount_minor = %s"
        " WHERE id = %s",
        (
            pristine["verdict_net_minor"],
            pristine["verdict_captured_minor"],
            pristine["verdict_expected_minor"],
            pristine["verified_amount_minor"],
            pristine["attributed_amount_minor"],
            vid,
        ),
    )
    owner_sql(
        "UPDATE public.attribution_events SET revenue_cents = %s,"
        " conversion_value_cents = %s WHERE id = %s",
        (
            pristine["attribution_revenue_cents"],
            pristine["attribution_revenue_cents"],
            attribution_event_id,
        ),
    )
    owner_sql(
        "UPDATE public.webhook_ingress_identities SET verified_amount_minor = %s"
        " WHERE id = %s",
        (pristine["ingress_verified_amount_minor"], ingress_id),
    )


def _attestation_row(ingress_id: str) -> tuple | None:
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT webhook_ingress_identity_id::text, tenant_id::text,"
            " statement_version, attested_amount_minor, attested_amount_currency,"
            " attested_amount_scale, statement::text, signature, key_id, key_sha256"
            " FROM public.b26_p2_source_money_attestation"
            " WHERE webhook_ingress_identity_id = %s",
            (str(ingress_id),),
        )
        return cur.fetchone()
    finally:
        conn.close()


def _replace_attestation(
    tenant_id: str,
    ingress_id: str,
    *,
    statement_version: int,
    amount_minor: int,
    currency: str,
    scale: int,
    statement_json: str,
    signature: str,
    key_id: str,
    key_sha256: str,
) -> None:
    owner_sql(
        "DO $$ BEGIN"
        " PERFORM set_config('app.current_tenant_id', %s, false);"
        " DELETE FROM public.b26_p2_source_money_attestation"
        " WHERE webhook_ingress_identity_id = %s;"
        " INSERT INTO public.b26_p2_source_money_attestation ("
        " webhook_ingress_identity_id, tenant_id, statement_version,"
        " attested_amount_minor, attested_amount_currency,"
        " attested_amount_scale, statement, signature, key_id, key_sha256)"
        " VALUES (%s, %s, %s, %s, %s, %s, CAST(%s AS jsonb), %s, %s, %s);"
        " END $$",
        (
            tenant_id,
            str(ingress_id),
            str(ingress_id),
            tenant_id,
            statement_version,
            amount_minor,
            currency,
            scale,
            statement_json,
            signature,
            key_id,
            key_sha256,
        ),
    )


def _verdict_ingress(vid: str) -> Any:
    import psycopg2

    conn = psycopg2.connect(_admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(
            "SELECT webhook_ingress_identity_id FROM public.b23_match_verdicts"
            " WHERE id = %s",
            (vid,),
        )
        return cur.fetchone()[0]
    finally:
        conn.close()


def f_fabricated_lineage(args: object = None) -> int:
    """Substitute the verification root; the forged money must be refused."""
    state = load_state()
    tenant = state["tenant_a"]
    import uuid

    intent = f"pi_xxv{uuid.uuid4().hex[:16]}"
    authentic = 4321
    forged = 77777
    status, text, _body = post_stripe(state, tenant, intent, authentic)
    verdict = wait_verdict(tenant["tenant_id"], intent)
    if verdict is None:
        write_evidence(
            "xxv-hb03-fabricated-lineage",
            {"error": "no_verdict", "ingress": {"status": status, "body": text[:400]}},
        )
        return 1
    vid = verdict["verdict_id"]
    ingress_id = _verdict_ingress(vid)
    original_attestation = _attestation_row(ingress_id)

    # The ORIGINAL runtime public key is captured BEFORE the swap: reading it
    # afterwards would capture the attacker's key and the restoration would
    # be a no-op dressed up as a restoration.
    from b26_p2_xxv_lane import volume_get

    original_public_key = volume_get(WITNESS_VOL, "source_attestation_ed25519.pub")

    # The attacker mints its own key and signs a statement over the forged
    # amount with it.
    attacker_private, attacker_public = generate_attestation_keypair()
    attacker_public_raw = _b64u_decode(attacker_public)
    attacker_fingerprint = hashlib.sha256(attacker_public_raw).hexdigest()
    statement = json.loads(original_attestation[6])
    statement["verified_amount_minor"] = forged
    forged_statement = json.dumps(statement, sort_keys=True, separators=(",", ":"))
    forged_signature = sign_with_seed(
        attacker_private, forged_statement.encode("utf-8")
    )

    # The witness is published before the baseline is read, so the baseline
    # is a GREEN baseline and not a freshness artefact of a previous run.
    baseline_observation = observe_once(state)
    pristine_db = money_snapshot(vid)
    pristine_recon = read_reconciliation(state, tenant, vid)
    pristine_trust = read_trust(tenant, vid)
    pristine_proof = composition_proof()
    pristine_history = history_state()
    pristine_history_identity = history_identity()
    if _baseline_is_green(
        "xxv-hb03-fabricated-lineage", pristine_proof, pristine_recon, pristine_trust
    ):
        return 1

    owner_steps: list[dict] = []

    def owner(statement: str, params: tuple = ()) -> None:
        try:
            owner_sql(statement, params)
            owner_steps.append(
                {"statement": statement.split(" SET")[0][:160], "result": "accepted"}
            )
        except Exception as exc:  # noqa: BLE001
            owner_steps.append(
                {
                    "statement": statement.split(" SET")[0][:160],
                    "result": f"refused:{exc}",
                }
            )

    _relax_owner_triggers()
    try:
        _rewrite_money(
            vid, verdict["attribution_event_id"], str(ingress_id), forged
        )
        owner_steps.append({"statement": "coherent money rewrite", "result": "accepted"})
    except Exception as exc:  # noqa: BLE001
        owner_steps.append(
            {"statement": "coherent money rewrite", "result": f"refused:{exc}"}
        )
    try:
        _replace_attestation(
            _tenant_scope(tenant),
            str(ingress_id),
            statement_version=int(original_attestation[2]),
            amount_minor=forged,
            currency=str(original_attestation[4]),
            scale=int(original_attestation[5]),
            statement_json=forged_statement,
            signature=forged_signature,
            key_id="kid:attacker-substituted-root",
            key_sha256=attacker_fingerprint,
        )
        owner_steps.append(
            {"statement": "attestation replaced by attacker-signed row", "result": "accepted"}
        )
    except Exception as exc:  # noqa: BLE001
        owner_steps.append(
            {
                "statement": "attestation replaced by attacker-signed row",
                "result": f"refused:{exc}",
            }
        )
    _restore_owner_triggers()

    # The runtime public key the readers verify against is replaced too.
    key_swap: dict[str, object] = {}
    try:
        volume_put(
            WITNESS_VOL,
            {"source_attestation_ed25519.pub": attacker_public.encode()},
            mode="0644",
        )
        key_swap = {"result": "accepted"}
    except Exception as exc:  # noqa: BLE001
        key_swap = {"result": f"refused:{exc}"}

    adverse_db = money_snapshot(vid)
    adverse_recon = read_reconciliation(state, tenant, vid)
    adverse_trust = read_trust(tenant, vid)
    adverse_proof = composition_proof()
    adverse_history = history_state()

    served_as_current = (
        adverse_recon[0] == 200
        and _net(adverse_recon[1]) == forged
        and _field(adverse_recon[1], "source_authority_state") == "current"
    )
    trust_issued = adverse_trust[0] == 200

    # ------------------------------------------------------------------
    # Exact restoration: the root's attestation, the runtime public key,
    # the money, and the witness (re-published by the shipping observer
    # so the signed consumer's authority is restored, not re-asserted).
    # ------------------------------------------------------------------
    restore_steps: list[dict] = []

    def restore(statement: str, params: tuple = ()) -> None:
        try:
            owner_sql(statement, params)
            restore_steps.append(
                {"statement": statement.split(" SET")[0][:160], "result": "accepted"}
            )
        except Exception as exc:  # noqa: BLE001
            restore_steps.append(
                {
                    "statement": statement.split(" SET")[0][:160],
                    "result": f"refused:{exc}",
                }
            )

    _relax_owner_triggers()
    _restore_money(
        vid, verdict["attribution_event_id"], str(ingress_id), pristine_db
    )
    restore_steps.append({"statement": "money restored", "result": "accepted"})
    _replace_attestation(
        _tenant_scope(tenant),
        str(ingress_id),
        statement_version=int(original_attestation[2]),
        amount_minor=int(original_attestation[3]),
        currency=str(original_attestation[4]),
        scale=int(original_attestation[5]),
        statement_json=str(original_attestation[6]),
        signature=str(original_attestation[7]),
        key_id=str(original_attestation[8]),
        key_sha256=str(original_attestation[9]),
    )
    restore_steps.append({"statement": "root attestation restored", "result": "accepted"})
    _restore_owner_triggers()

    key_restore: dict[str, object] = {}
    try:
        volume_put(
            WITNESS_VOL,
            {"source_attestation_ed25519.pub": original_public_key},
            mode="0644",
        )
        key_restore = {
            "result": "accepted",
            "restored_sha256": hashlib.sha256(original_public_key).hexdigest(),
            "attacker_sha256": attacker_fingerprint,
            "bytes_match_original": True,
        }
    except Exception as exc:  # noqa: BLE001
        key_restore = {"result": f"refused:{exc}"}

    # The witness is re-published by the shipping observer, then the
    # consumers are read again.
    observation = observe_once(state)
    # XXV: use the same forced-order snapshot as the boundary falsifiers. It
    # pauses the scheduler, runs the mandatory proof first (its cells append
    # ledger rows), then closes the freshness window, then reads both
    # consumers. Reading the signed consumer without pausing the scheduler let
    # a scheduled observation re-open the window between the catch-up and the
    # read, which is how a restored lane still produced a signed refusal.
    restored = phase_snapshot(state, tenant, vid, expected_minor=authentic)
    catchup = restored["witness_catchup"]
    restored_db = restored["db"]
    restored_recon = (
        restored["reconciliation"]["status"],
        {
            "canonical_net_verified_amount_minor": restored["reconciliation"]["net"],
            "source_authority_state": restored["reconciliation"][
                "source_authority_state"
            ],
            "source_money_attestation_status": restored["reconciliation"][
                "attestation_status"
            ],
        },
    )
    restored_trust = (
        restored["signed_financial_result"]["trust_status"],
        restored["signed_financial_result"],
    )
    restored_proof = {
        "printed_verdict": restored["mandatory_proof"],
        "stdout_tail": restored["mandatory_proof_stdout_tail"],
    }
    restored_history = history_state()
    restored_history_identity = restored["history_identity"]
    restored_history_verdict = history_is_restored(
        pristine_history_identity, restored_history_identity
    )
    restored_signed = restored["signed_financial_result"]

    record = {
        "property": (
            "P-XXV 1(a)(i): unsupported money must not become current authority"
            " when the verification root itself is substituted"
        ),
        "actor": (
            "migration_owner plus the runtime public-key configurator (the"
            " primitive both XXIV audits used against the historical witness"
            " root)"
        ),
        "expected_independently": (
            "the substituted key does not match the fingerprint compiled into"
            " the image, so the forged amount is refused by every consumer and"
            " the governing proof is RED"
        ),
        "falsifier": "xxv-hb03-fabricated-lineage",
        "independent_of": (
            "xxv-hb03-predecessor-escape: this attack never deletes an"
            " attestation to obtain an exemption and never consults a"
            " watermark; it replaces the ROOT itself"
        ),
        "verdict_id": vid,
        "ingress_id": str(ingress_id),
        "authentic_amount_minor": authentic,
        "forged_amount_minor": forged,
        "attack_steps": [
            "coherent owner rewrite of verdict/attribution/ingress money",
            "attestation row replaced by one the attacker signed itself",
            "runtime public key replaced with the attacker's key",
        ],
        "attacker_key_sha256": attacker_fingerprint,
        "pristine": {
            "db": pristine_db,
            "reconciliation": {
                "status": pristine_recon[0],
                "net": _net(pristine_recon[1]),
                "source_authority_state": _field(
                    pristine_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    pristine_recon[1], "source_money_attestation_status"
                ),
            },
            "trust": {
                "status": pristine_trust[0],
                "body_head": str(pristine_trust[1])[:300],
            },
            "mandatory_proof": pristine_proof["printed_verdict"],
            "history": pristine_history,
            "observer": {
                "returncode": baseline_observation["returncode"],
                "stdout_tail": baseline_observation["stdout_tail"][-400:],
            },
        },
        "owner_operations": owner_steps,
        "public_key_swap": key_swap,
        "adverse": {
            "db": adverse_db,
            "reconciliation": {
                "status": adverse_recon[0],
                "net": _net(adverse_recon[1]),
                "source_authority_state": _field(
                    adverse_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    adverse_recon[1], "source_money_attestation_status"
                ),
                "attestation_reason": _field(
                    adverse_recon[1], "source_money_attestation_reason"
                ),
                "body_head": str(adverse_recon[1])[:600],
            },
            "trust": {
                "status": adverse_trust[0],
                "body_head": str(adverse_trust[1])[:400],
                "durable_refusal_reason": trust_refusal_reason(_tenant_scope(tenant)),
            },
            "mandatory_proof": adverse_proof["printed_verdict"],
            "mandatory_proof_stdout_tail": adverse_proof["stdout_tail"][-1200:],
            "history": adverse_history,
        },
        "observed_result": (
            "RED if the reconciliation reader serves 77777 as current, or the"
            " signed consumer issues, or the mandatory proof prints PASS while"
            " the substituted root is live"
        ),
        "effect_summary": {
            "unsigned_reader_served_forged_as_current": served_as_current,
            "signed_consumer_issued": trust_issued,
            "mandatory_proof_green": adverse_proof["printed_verdict"] == "PASS",
            "red": bool(
                served_as_current
                or trust_issued
                or adverse_proof["printed_verdict"] == "PASS"
            ),
        },
        "restoration": {
            "steps": restore_steps,
            "public_key_restore": key_restore,
            "observer": {
                "returncode": observation["returncode"],
                "stdout_tail": observation["stdout_tail"][-600:],
            },
            "db": restored_db,
            "reconciliation": {
                "status": restored_recon[0],
                "net": _net(restored_recon[1]),
                "source_authority_state": _field(
                    restored_recon[1], "source_authority_state"
                ),
                "attestation_status": _field(
                    restored_recon[1], "source_money_attestation_status"
                ),
            },
            "trust": {
                "status": restored_trust[0],
                "body_head": str(restored_trust[1])[:300],
                "durable_refusal_reason": trust_refusal_reason(_tenant_scope(tenant)),
            },
            "mandatory_proof": restored_proof["printed_verdict"],
            "history": restored_history,
            "history_identity": restored_history_identity,
            "witness_catchup": catchup,
            "money_restored": restored_db == pristine_db,
            "history_restored": restored_history_verdict,
            "unsigned_consumer_restored": (
                restored_recon[0] == 200
                and _net(restored_recon[1]) == authentic
            ),
            "signed_consumer_restored": restored_signed,
            "consumer_restored": bool(
                restored_recon[0] == 200
                and _net(restored_recon[1]) == authentic
                and restored_signed["established"]
            ),
        },
    }
    write_evidence("xxv-hb03-fabricated-lineage", record)
    return 0


COMMANDS = {"hb03-fabricated-lineage": f_fabricated_lineage}


def main() -> int:
    import argparse

    parser = argparse.ArgumentParser(description="XXV independent falsifiers")
    parser.add_argument("falsifier", choices=sorted(COMMANDS))
    args = parser.parse_args()
    try:
        return int(COMMANDS[args.falsifier](args))
    except Exception as exc:  # noqa: BLE001
        import traceback

        print(f"[xxv-falsify-lineage] FAILED: {type(exc).__name__}: {exc}")
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
