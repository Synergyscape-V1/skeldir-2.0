#!/usr/bin/env python3
"""B2.6-P2 Corrective XXII context-robust witness gate.

Audit-68 falsifiers:

- coherent ledger rewrite + recomputed chain + owner-planted clean
  observation must not issue: the out-of-database signed checkpoint
  refuses a live tip/count/prefix divergence;
- truncate-to-zero must not issue: the signed count diverges;
- future observations, future ingress events, reversed or non-equal
  Shopify creation moments, and ledger money that is not the lawful
  continuation of its authenticated source must all refuse.

Static law-presence plus a live battery. Prints
B26_P2_XXII_COMPOSITION_PASS on success.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import tempfile
import uuid
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

MIG_XXII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202610180002_b26_p2_corrective_xxii_context_robust_witness.py"
)
MIG_XXIII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202610180003_b26_p2_corrective_xxiii_witness_growth_authority.py"
)
MIG_XXV = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202610270001_b26_p2_corrective_xxv_source_attestation.py"
)
MIG_XXV_2 = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202610270002_b26_p2_corrective_xxv_provider_amendment.py"
)
ATTESTATION = (
    REPO_ROOT
    / "backend"
    / "app"
    / "revenue_verification"
    / "source_attestation.py"
)
SWEEP = (
    REPO_ROOT
    / "scripts"
    / "ci"
    / "b26_p2_xxv_attestation_sweep.py"
)
CONTRACT = REPO_ROOT / "backend" / "app" / "core" / "construction_authority.py"
MATCH_KERNEL = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "match_engine_kernel.py"
)
CORRECTIONS = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "corrections.py"
)
BATCH_ENGINE = (
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "batch_engine.py"
)
WEBHOOKS = REPO_ROOT / "backend" / "app" / "api" / "webhooks.py"
BUILDER = REPO_ROOT / "backend" / "app" / "trust" / "builder.py"
WITNESS = REPO_ROOT / "backend" / "app" / "trust" / "history_witness.py"
REVENUE_TASKS = (
    REPO_ROOT / "backend" / "app" / "tasks" / "revenue_verification.py"
)
OBSERVER = REPO_ROOT / "backend" / "app" / "tasks" / "b26_p2_history.py"
COVERAGE = REPO_ROOT / "scripts" / "ci" / "b26_p2_xxii_coverage.py"
WORKFLOW = (
    REPO_ROOT
    / ".github"
    / "workflows"
    / "b2_6-p1-finance-reconciliation-adjudication.yml"
)

HEAD = "202610280001"


def _read(path: Path, violations: list[str], tag: str) -> str:
    try:
        return path.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xxii_comp_unreadable:{tag}:{exc}")
        return ""


def _executable_only(source: str) -> str:
    """Strip whole-line comments so a static cell judges CODE, not prose.

    The migration records *why* the owner-written epoch table was removed,
    and that explanation necessarily names the removed identifiers. A static
    gate that read the comment would fail the corrected tree and pass the
    defective one, which is exactly backwards. Only full-line comments are
    removed; a token on a line that carries code is still judged.
    """
    return "\n".join(
        line for line in source.splitlines() if not line.lstrip().startswith("#")
    )


def _static_checks(violations: list[str], checks: dict) -> None:
    mig = _read(MIG_XXII, violations, "migration")
    mig_next = _read(MIG_XXIII, violations, "migration_xxiii")
    combined = mig + "\n" + mig_next
    contract = _read(CONTRACT, violations, "contract")
    builder = _read(BUILDER, violations, "builder")
    witness = _read(WITNESS, violations, "witness")
    observer = _read(OBSERVER, violations, "observer")
    coverage = _read(COVERAGE, violations, "coverage")
    workflow = _read(WORKFLOW, violations, "workflow")

    if 'revision = "202610180002"' not in mig:
        violations.append("xxii_comp_migration_revision_missing")
    if 'down_revision = "202610180001"' not in mig:
        violations.append("xxii_comp_migration_parent_missing")
    if 'revision = "202610180003"' not in mig_next:
        violations.append("xxii_comp_migration_head_missing")
    if 'down_revision = "202610180002"' not in mig_next:
        violations.append("xxii_comp_migration_head_parent_missing")
    if f'REQUIRED_SCHEMA_REVISION = "{HEAD}"' not in contract:
        violations.append("xxii_comp_contract_head_missing")

    required_sql = {
        "witness_state": "b26_p2_read_history_witness_state",
        "prefix_digest": "b26_p2_read_history_prefix_digest",
        "entry_hash": "b26_p2_read_history_entry_hash",
        "violations": "b26_p2_read_history_violations",
        "conservation": "b26_p2_verify_source_money_conservation",
        "observation_chronology": "b26_p2_enforce_observation_chronology",
        "ingress_chronology": "b26_p2_enforce_ingress_event_chronology",
        "lifecycle": "b26_p2_enforce_lifecycle_admission",
        "authority_universe": "b26_p2_authority_universe",
        "snapshot": "b26_p2_read_history_snapshot",
        "growth_continuity": "b26_p2_verify_history_continuity",
        "money_authority": "b26_p2_enforce_verdict_money_authority",
        "money_trigger": "trg_b26_p2_verdict_money_authority",
        "source_null_refusal": "conservation_source_ingress_missing",
        "source_amount_refusal": "conservation_source_amount_diverged",
        "source_authority_refusal": "conservation_source_authority_unresolved",
        "source_event_amount_refusal": (
            "conservation_source_event_amount_diverged"
        ),
    }
    for name, token in required_sql.items():
        if token not in combined:
            violations.append(f"xxii_comp_sql_missing:{name}")
    for role in ("app_user", "app_worker", "app_beat"):
        if f'"{role}"' not in combined:
            violations.append(f"xxii_comp_grant_missing:{role}")
    if "_revoke_execute(" not in mig:
        violations.append("xxii_comp_public_revoke_missing")
    if "SECURITY DEFINER" not in mig:
        violations.append("xxii_comp_definer_missing")

    if 'DROP FUNCTION IF EXISTS"\n        " public.b26_p2_read_history_prefix_digest()' not in mig:
        violations.append("xxii_comp_downgrade_prefix_digest_not_dropped")
    if "b26_p2_lifecycle_not_creation_moment" not in mig:
        violations.append("xxii_comp_lifecycle_equality_missing")
    if "abs(extract(epoch FROM" not in mig.split("def downgrade", 1)[-1]:
        violations.append("xxii_comp_downgrade_lifecycle_not_restored")
    downgrade_tail = mig_next.split("def downgrade", 1)[-1]
    if "DROP TABLE IF EXISTS public.b26_p2_authority_universe" in downgrade_tail:
        violations.append("xxii_comp_downgrade_drops_authority_universe")
    if (
        "DROP FUNCTION IF EXISTS public.b26_p2_authority_universe()"
        in downgrade_tail
    ):
        violations.append("xxii_comp_downgrade_drops_authority_universe_reader")

    builder_tokens = {
        "witness_gate": "_verify_signed_history_witness",
        "snapshot": "b26_p2_read_history_snapshot",
        "conservation": "read_source_money_conservation_status",
        "universe": "authority_universe",
        "custody": "load_custody",
        "compiled_anchor": "COMPILED_PUBLIC_KEY_SHA256",
        "heartbeat": "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH",
        "issuance_lock": "pg_advisory_xact_lock",
    }
    for name, token in builder_tokens.items():
        if token not in builder:
            violations.append(f"xxii_comp_builder_missing:{name}")
    for token in (
        "Ed25519",
        "witness_live_count_diverged",
        "witness_live_tip_diverged",
        "witness_live_prefix_diverged",
        "witness_authority_universe_missing",
        "witness_live_universe_diverged",
        "witness_history_tip_not_advanced",
        "witness_heartbeat_diverged",
        "witness_source_evidence_diverged_without_ledger",
        "witness_custody_missing",
    ):
        if token not in witness:
            violations.append(f"xxii_comp_witness_missing:{token}")
    if "b26_p2_read_history_snapshot" not in observer:
        violations.append("xxii_comp_observer_snapshot_missing")
    if "witness_history_prefix_diverged" not in observer:
        violations.append("xxii_comp_observer_prefix_refusal_missing")
    if "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH" not in observer:
        violations.append("xxii_comp_observer_heartbeat_missing")
    for token in (
        "app_worker:EXECUTE:b26_p2_read_history_prefix_digest",
        "app_beat:EXECUTE:b26_p2_read_history_prefix_digest",
        "app_trust_issuer:EXECUTE:b26_p2_verify_source_money_conservation",
    ):
        if token not in coverage:
            violations.append(f"xxii_comp_coverage_missing:{token}")
    if "validate_b26_p2_xxii_composition.py" not in workflow:
        violations.append("xxii_comp_workflow_step_missing")
    # XXV (A6/A10/A12): the sovereign source attestation must be present in
    # the tree under proof, chained to the XXIII head, and actually enforced
    # by the builder. A proof that can run without the attestation law is a
    # proof of the previous release.
    mig_xxv = _read(MIG_XXV, violations, "xxv_migration")
    if 'revision = "202610270001"' not in mig_xxv:
        violations.append("xxv_migration_revision_missing")
    if 'down_revision = "202610180003"' not in mig_xxv:
        violations.append("xxv_migration_not_chained_to_xxiii")
    if "b26_p2_source_money_attestation" not in mig_xxv:
        violations.append("xxv_attestation_table_absent")
    attestation_module = _read(ATTESTATION, violations, "xxv_attestation_module")
    for token in (
        "def verify_signature",
        "attestation_key_not_anchored",
        "verdict_net_unsupported_by_attestation",
        "adjustment_attestation_missing",
        "read_verdict_source_attestation_status",
    ):
        if token not in attestation_module:
            violations.append(f"xxv_attestation_law_absent:{token}")
    builder_source = _read(BUILDER, violations, "builder")
    if "read_verdict_source_attestation_status" not in builder_source:
        violations.append("xxv_builder_does_not_require_attestation")
    checks["static_xxv_attestation_law"] = True
    # XXV (A6/A10 class closure): no reader and no oracle may decide
    # authority by consulting an instant the maintenance principal owns.
    #
    # The candidate artifact granted a "predecessor generation" exemption to
    # any row with no attestation whose creation time preceded a watermark
    # stored in a table the maintenance principal owns. Deleting the
    # authentication root's attestation row and moving that watermark was
    # enough to have a coherently forged amount served as current money while
    # this proof printed PASS (falsifier xxv-hb03-predecessor-escape). The
    # exemption is removed, the watermark table is removed, and these static
    # cells keep the class closed: the absence of an attestation is never a
    # grant, and nothing may reintroduce a comparable owner-written instant.
    for banned in ("attestation_required_from", "attestation_watermark"):
        if banned in _executable_only(mig_xxv):
            violations.append(f"xxv_owner_written_instant_present_in_migration:{banned}")
        if banned in _executable_only(attestation_module):
            violations.append(f"xxv_owner_written_instant_present_in_reader:{banned}")
        if banned in _executable_only(_read(SWEEP, violations, "xxv_attestation_sweep")):
            violations.append(f"xxv_owner_written_instant_present_in_oracle:{banned}")
    if "b26_p2_source_attestation_authority" in _executable_only(mig_xxv):
        violations.append("xxv_owner_written_epoch_table_present_in_migration")
    if "attestation_missing" not in attestation_module:
        violations.append("xxv_attestation_absence_grant_absent_from_reader")
    checks["static_xxv_no_owner_written_instant"] = True
    # XXV-2 (A2/B10): a provider amendment must be admissible without
    # weakening commerce-identity collision refusal, and the corrected money
    # must be linked to the amending source's own attestation. The static cells
    # bind the tree under proof to the admission split, the current-only
    # commerce index, the tenant-bound demotion propagation, the correction
    # relink, and the exclusion of amendment sources from independent B2.3
    # match (which would otherwise create a second verdict for one identity).
    mig_xxv_2 = _read(MIG_XXV_2, violations, "xxv_2_migration")
    for token, reason in (
        ('revision = "202610270002"', "xxv_2_revision_missing"),
        ('down_revision = "202610270001"', "xxv_2_not_chained_to_xxv"),
        ("superseded_by_provider_amendment", "xxv_2_supersession_absent"),
        (
            "b26_p2_atomic_commerce_identity_conflict_refused",
            "xxv_2_collision_refusal_absent",
        ),
        (
            "b26_p2_demotion_reason IS NULL",
            "xxv_2_current_only_commerce_index_absent",
        ),
        (
            "app.current_tenant_id",
            "xxv_2_propagation_tenant_binding_absent",
        ),
        (
            "_amendment_link",
            "xxv_2_conducted_relink_exemption_absent",
        ),
        (
            "b26_p2_conducted_verdict_regression_refused",
            "xxv_2_conducted_relink_guard_absent",
        ),
        (
            "interval '60 seconds'",
            "xxv_2_lifecycle_creation_window_absent",
        ),
    ):
        if token not in mig_xxv_2:
            violations.append(reason)
    kernel_source = _read(MATCH_KERNEL, violations, "xxv_2_match_kernel")
    for token in (
        "source_webhook_ingress_identity_id",
        "_is_lawful_superseding_amendment_source",
    ):
        if token not in kernel_source:
            violations.append(f"xxv_2_correction_relink_absent:{token}")
    corrections_source = _read(CORRECTIONS, violations, "xxv_2_corrections")
    if 'webhook_ingress_identity_id=ingress["id"]' not in corrections_source:
        violations.append("xxv_2_correction_evidence_ingress_absent")
    batch_source = _read(BATCH_ENGINE, violations, "xxv_2_batch_engine")
    if "prior.b26_p2_provenance_status = 'authenticated_known'" not in batch_source:
        violations.append("xxv_2_amendment_source_not_excluded_from_match")
    webhook_source = _read(WEBHOOKS, violations, "xxv_2_webhooks")
    if "(prior.created_at, prior.id)" not in webhook_source:
        violations.append("xxv_2_amendment_source_not_excluded_from_dispatch")
    checks["static_xxv_2_amendment_law"] = True
    # XXV (A3/HB-08): an append path must ask the observer to witness the new
    # ledger state, and concurrent observers must serialize the journal.
    witness_source = _read(WITNESS, violations, "xxv_a3_witness")
    if "def witness_lock" not in witness_source:
        violations.append("xxv_a3_witness_lock_absent")
    tasks_source = _read(REVENUE_TASKS, violations, "xxv_a3_tasks")
    if "_enqueue_history_observation" not in tasks_source:
        violations.append("xxv_a3_observation_enqueue_absent")
    if "QUEUE_B26_P2_HISTORY" not in tasks_source:
        violations.append("xxv_a3_history_queue_binding_absent")
    checks["static_xxv_a3_observation_on_growth"] = True
    checks["static_laws"] = True


def _expect_exception(cur, sql: str, params: tuple, token: str) -> None:
    cur.execute("SAVEPOINT xxii_cell")
    try:
        cur.execute(sql, params)
    except Exception as exc:  # noqa: BLE001 - refusal is the result
        cur.execute("ROLLBACK TO SAVEPOINT xxii_cell")
        if token not in str(exc):
            raise AssertionError(f"expected {token}, got {exc}") from exc
        return
    cur.execute("ROLLBACK TO SAVEPOINT xxii_cell")
    raise AssertionError(f"expected refusal {token}, statement succeeded")


class _CompatResult:
    def __init__(self, rows: list[dict]) -> None:
        self._rows = rows

    def mappings(self) -> "_CompatResult":
        return self

    def first(self) -> dict | None:
        return self._rows[0] if self._rows else None

    def one(self) -> dict:
        if len(self._rows) != 1:
            raise AssertionError(f"expected one row, got {len(self._rows)}")
        return self._rows[0]

    def scalar(self) -> object:
        if not self._rows:
            return None
        return next(iter(self._rows[0].values()))


class _AsyncCompatSession:
    def __init__(self, cursor: object) -> None:
        self._cursor = cursor

    async def execute(self, statement: object, params: object = None) -> _CompatResult:
        sql = str(statement)
        self._cursor.execute(sql, params or {})
        if self._cursor.description is None:
            return _CompatResult([])
        columns = [column[0] for column in self._cursor.description]
        rows = [
            dict(zip(columns, row, strict=True))
            for row in self._cursor.fetchall()
        ]
        return _CompatResult(rows)


def _builder_status(cursor: object) -> tuple[bool, str]:
    from app.trust.builder import read_history_integrity_status  # noqa: PLC0415

    return asyncio.run(read_history_integrity_status(_AsyncCompatSession(cursor)))


def _live_state(
    cursor: object,
) -> tuple[int, int | None, str | None, str, str | None]:
    cursor.execute(
        "SELECT n, tip_seq, tip_hash, prefix_digest, authority_universe"
        " FROM public.b26_p2_read_history_snapshot(NULL)"
    )
    n, tip_seq, tip_hash, digest, universe = cursor.fetchone()
    return (
        int(n),
        tip_seq,
        tip_hash,
        digest,
        str(universe) if universe is not None else None,
    )


def _plant_observation(
    cursor: object, count: int, tip: str | None
) -> None:
    cursor.execute(
        "INSERT INTO public.b26_p2_history_integrity_observations"
        "(ledger_count, ledger_tip, observer_violations, observed_at, author)"
        " VALUES (%s,%s,'',now(),'app_worker')",
        (count, tip),
    )


def _coherent_rewrite_cell(
    cursor: object,
    *,
    ledger_count: int,
    ledger_tip_seq: int | None,
    ledger_tip_hash: str | None,
    violations: list[str],
    checks: dict,
) -> None:
    from app.core.config import settings  # noqa: PLC0415
    from app.trust.history_witness import (  # noqa: PLC0415
        append_checkpoint,
        generate_keypair,
    )

    with tempfile.TemporaryDirectory(prefix="xxii-witness-") as directory:
        root = Path(directory)
        private_seed, public_key = generate_keypair()
        private_path = root / "witness.key"
        public_path = root / "witness.pub"
        journal = root / "journal.jsonl"
        custody = root / "custody.json"
        heartbeat = root / "heartbeat.json"
        private_path.write_text(private_seed, encoding="utf-8")
        public_path.write_text(public_key, encoding="utf-8")
        _n, _seq, _tip, digest, universe = _live_state(cursor)
        # XXV: a published checkpoint carries its custody record. Issuance
        # refuses a missing custody record in EVERY environment now (the old
        # guard compared ENVIRONMENT to the alias literal "production", which
        # canonicalisation makes unreachable, so custody loss was accepted in
        # every deployment -- both independent XXIV audits deleted the custody
        # record and kept receiving signed envelopes).
        append_checkpoint(
            journal,
            private_key_path=private_path,
            ledger_count=ledger_count,
            ledger_tip_seq=ledger_tip_seq,
            ledger_tip_hash=ledger_tip_hash,
            ledger_prefix_digest=digest,
            authority_universe=universe,
            custody_path=custody,
            heartbeat_path=heartbeat,
        )
        previous = (
            settings.B26_P2_HISTORY_WITNESS_REQUIRED,
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
            settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH,
            settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
            settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
            settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
        )
        try:
            settings.B26_P2_HISTORY_WITNESS_REQUIRED = True
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH = str(journal)
            settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH = str(public_path)
            settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH = None
            settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH = str(custody)
            settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH = str(heartbeat)
            _plant_observation(cursor, ledger_count, ledger_tip_hash)
            if _builder_status(cursor) != (True, ""):
                violations.append("xxii_comp_witness_clean_refused")

            cursor.execute(
                "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                " DISABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
            )
            cursor.execute(
                "UPDATE public.b26_p2_verdict_supersession_ledger"
                " SET new_attributed_amount_minor=999,"
                " new_verified_amount_minor=999, entry_hash ="
                " encode(digest(COALESCE(verdict_id::text,'') || '|' ||"
                " COALESCE(prior_attributed_amount_minor::text,'NULL') ||"
                " '|999|' ||"
                " COALESCE(prior_verified_amount_minor::text,'NULL') ||"
                " '|999|' ||"
                " COALESCE(prior_authority_state,'NULL') || '|' ||"
                " COALESCE(new_authority_state,'NULL') || '|' ||"
                " COALESCE(prev_entry_hash,''), 'sha256'), 'hex')"
                " WHERE seq = (SELECT max(seq) FROM"
                " public.b26_p2_verdict_supersession_ledger)"
            )
            cursor.execute(
                "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                " ENABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
            )
            new_count, new_seq, new_tip, _new_digest, _new_universe = _live_state(
                cursor
            )
            cursor.execute(
                "SELECT public.b26_p2_read_history_violations()"
            )
            live_violations = str(cursor.fetchone()[0] or "").strip()
            if live_violations:
                violations.append(
                    f"xxii_comp_rewrite_not_coherent:{live_violations}"
                )
            _plant_observation(cursor, new_count, new_tip)
            after = _builder_status(cursor)
            if after[0] or "witness" not in after[1]:
                violations.append(
                    f"xxii_comp_witness_rewrite_blind:{after}"
                )

            cursor.execute(
                "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                " DISABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
            )
            cursor.execute(
                "UPDATE public.b26_p2_verdict_supersession_ledger"
                " SET new_attributed_amount_minor=1000,"
                " new_verified_amount_minor=1000, entry_hash ="
                " encode(digest(COALESCE(verdict_id::text,'') || '|' ||"
                " COALESCE(prior_attributed_amount_minor::text,'NULL') ||"
                " '|1000|' ||"
                " COALESCE(prior_verified_amount_minor::text,'NULL') ||"
                " '|1000|' ||"
                " COALESCE(prior_authority_state,'NULL') || '|' ||"
                " COALESCE(new_authority_state,'NULL') || '|' ||"
                " COALESCE(prev_entry_hash,''), 'sha256'), 'hex')"
                " WHERE seq = (SELECT max(seq) FROM"
                " public.b26_p2_verdict_supersession_ledger)"
            )
            cursor.execute(
                "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
                " ENABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
            )
            checks["live_coherent_rewrite_refused"] = True
        finally:
            (
                settings.B26_P2_HISTORY_WITNESS_REQUIRED,
                settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
                settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH,
                settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
                settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
                settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
            ) = previous


def _truncate_cell(
    cursor: object,
    *,
    ledger_count: int,
    ledger_tip_seq: int | None,
    ledger_tip_hash: str | None,
    violations: list[str],
    checks: dict,
) -> None:
    from app.core.config import settings  # noqa: PLC0415
    from app.trust.history_witness import (  # noqa: PLC0415
        append_checkpoint,
        generate_keypair,
    )

    with tempfile.TemporaryDirectory(prefix="xxii-witness-") as directory:
        root = Path(directory)
        private_seed, public_key = generate_keypair()
        private_path = root / "witness.key"
        public_path = root / "witness.pub"
        journal = root / "journal.jsonl"
        custody = root / "custody.json"
        heartbeat = root / "heartbeat.json"
        private_path.write_text(private_seed, encoding="utf-8")
        public_path.write_text(public_key, encoding="utf-8")
        _n, _seq, _tip, digest, universe = _live_state(cursor)
        # XXV: a published checkpoint carries its custody record. Issuance
        # refuses a missing custody record in EVERY environment now (the old
        # guard compared ENVIRONMENT to the alias literal "production", which
        # canonicalisation makes unreachable, so custody loss was accepted in
        # every deployment -- both independent XXIV audits deleted the custody
        # record and kept receiving signed envelopes).
        append_checkpoint(
            journal,
            private_key_path=private_path,
            ledger_count=ledger_count,
            ledger_tip_seq=ledger_tip_seq,
            ledger_tip_hash=ledger_tip_hash,
            ledger_prefix_digest=digest,
            authority_universe=universe,
            custody_path=custody,
            heartbeat_path=heartbeat,
        )
        previous = (
            settings.B26_P2_HISTORY_WITNESS_REQUIRED,
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
            settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH,
            settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
            settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
            settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
        )
        try:
            settings.B26_P2_HISTORY_WITNESS_REQUIRED = True
            settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH = str(journal)
            settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH = str(public_path)
            settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH = None
            settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH = str(custody)
            settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH = str(heartbeat)
            cursor.execute(
                "TRUNCATE public.b26_p2_verdict_supersession_ledger"
            )
            _plant_observation(cursor, 0, None)
            after = _builder_status(cursor)
            if after[0] or "witness_live_count_diverged" not in after[1]:
                violations.append(f"xxii_comp_witness_truncate_blind:{after}")
            checks["live_truncate_refused"] = True
        finally:
            (
                settings.B26_P2_HISTORY_WITNESS_REQUIRED,
                settings.B26_P2_HISTORY_WITNESS_JOURNAL_PATH,
                settings.B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH,
                settings.B26_P2_HISTORY_WITNESS_GENESIS_HASH,
                settings.B26_P2_HISTORY_WITNESS_CUSTODY_PATH,
                settings.B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH,
            ) = previous


def _external_false_world_cell(
    dsn: str, violations: list[str], checks: dict
) -> None:
    """Commit a coherent false financial world and require refusal.

    HB-12: the validator must not mint its own state and then verify its
    own mutation. It establishes an independently authenticated source
    (1000 minor units), commits that source, then a second connection
    commits a coherent 99,999 world with a matching supersession chain.
    The unmodified downstream consumer must reject the consequence from
    its independent source reference.
    """
    import psycopg2  # noqa: PLC0415

    tenant = str(uuid.uuid4())
    event = str(uuid.uuid4())
    ingress = str(uuid.uuid4())
    verdict = str(uuid.uuid4())
    channel = "xxiii_fw_" + uuid.uuid4().hex[:8]
    event_ref = "xxiii-fw-" + uuid.uuid4().hex
    commerce_ref = "xxiii-fw-order-" + uuid.uuid4().hex
    idempotency_key = "xxiii-fw-idem-" + uuid.uuid4().hex

    def _seed(conn: object) -> None:
        cur = conn.cursor()
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xxiii-fw", uuid.uuid4().hex, "xxiii@example.invalid"),
        )
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES (%s,'xxiii',true,'XXIII','active')"
            " ON CONFLICT (code) DO NOTHING",
            (channel,),
        )
        cur.execute("SELECT set_config('app.current_tenant_id', %s, false)", (tenant,))
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id,"
            " occurred_at, correlation_id, session_id, revenue_cents,"
            " raw_payload, idempotency_key, event_type, channel,"
            " campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s,%s,now(),%s,%s,1000,'{}'::jsonb,%s,'conversion',"
            " %s,'c',1000,'USD',now(),now(),'processed')",
            (
                event,
                tenant,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                channel,
            ),
        )
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
            " event_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe',%s,%s,'order_reference',%s,1000,"
            " 'USD',now(),%s,'authenticity_verified')",
            (
                ingress,
                tenant,
                event,
                event_ref,
                commerce_ref,
                commerce_ref,
                idempotency_key,
            ),
        )
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family',"
            " 'payment_intent.succeeded', false)"
        )
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family_source',"
            " 'body-signal:type', false)"
        )
        cur.execute(
            "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
            " %s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1',"
            " NULL,NULL,FALSE,NULL,NULL)",
            (
                ingress,
                event_ref,
                "c" * 64,
                "d" * 64,
            ),
        )
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, webhook_ingress_identity_id, provider,"
            " canonical_commerce_reference, provider_native_event_reference,"
            " provider_native_commerce_reference, status, match_quality,"
            " attributed_amount_minor, verified_amount_minor, currency_code,"
            " last_transition_at, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s,%s,%s,%s,'stripe',%s,%s,%s,'matched_confirmed',"
            " 'high',1000,1000,'USD',now(),1000,1000,1000,0,0,'exact')",
            (
                verdict,
                tenant,
                event,
                ingress,
                "xxiii-fw-" + uuid.uuid4().hex,
                "xxiii-fw-" + uuid.uuid4().hex,
                "xxiii-fw-" + uuid.uuid4().hex,
            ),
        )

    seeded = False
    try:
        admin = psycopg2.connect(dsn)
        admin.autocommit = False
        _seed(admin)
        admin.commit()
        seeded = True

        ref = psycopg2.connect(dsn)
        ref.autocommit = False
        with ref.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT i.verified_amount_minor, i.b26_p2_provenance_status"
                " FROM public.webhook_ingress_identities AS i"
                " WHERE i.id=%s AND i.tenant_id=%s",
                (ingress, tenant),
            )
            amount, state = cur.fetchone()
            if amount != 1000 or state != "authenticated_known":
                violations.append(
                    "xxii_comp_false_world_source_not_independent"
                )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " DISABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " DISABLE TRIGGER trg_b26_p2_ingress_xv_meaning_immutability"
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor=99999"
                " WHERE tenant_id=%s AND id=%s",
                (tenant, ingress),
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " ENABLE TRIGGER trg_b26_p2_ingress_xv_meaning_immutability"
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " ENABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
            )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET verified_amount_minor=99999,"
                "     canonical_captured_gross_amount_minor=99999,"
                "     canonical_net_verified_amount_minor=99999,"
                "     discrepancy_amount_minor=98999,"
                "     discrepancy_ratio_bps=989990,"
                "     discrepancy_band='severe_gap'"
                " WHERE tenant_id=%s AND id=%s",
                (tenant, verdict),
            )
        ref.commit()

        consumer = psycopg2.connect(dsn)
        consumer.autocommit = False
        with consumer.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "SELECT violation FROM"
                " public.b26_p2_verify_source_money_conservation(%s,%s)",
                (tenant, verdict),
            )
            refused = [row[0] for row in cur.fetchall()]
            if "conservation_source_event_amount_diverged" not in refused:
                violations.append(
                    "xxii_comp_false_world_not_refused:"
                    + ";".join(refused or ["<none>"])
                )
        consumer.rollback()
        consumer.close()

        # XXV: restore the amounts this cell forged. A proof that leaves an
        # unsupported financial world committed in the database it adjudicates
        # is itself a source of false finance, and the XXV live attestation
        # sweep reads the database as it finds it.
        with ref.cursor() as cur:
            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false)",
                (tenant,),
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " DISABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " DISABLE TRIGGER trg_b26_p2_ingress_xv_meaning_immutability"
            )
            cur.execute(
                "UPDATE public.webhook_ingress_identities"
                " SET verified_amount_minor=1000"
                " WHERE tenant_id=%s AND id=%s",
                (tenant, ingress),
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " ENABLE TRIGGER trg_b26_p2_ingress_xv_meaning_immutability"
            )
            cur.execute(
                "ALTER TABLE public.webhook_ingress_identities"
                " ENABLE TRIGGER trg_b26_p2_ingress_sovereign_custody"
            )
            cur.execute(
                "UPDATE public.b23_match_verdicts"
                " SET verified_amount_minor=1000,"
                "     canonical_captured_gross_amount_minor=1000,"
                "     canonical_net_verified_amount_minor=1000,"
                "     discrepancy_amount_minor=0,"
                "     discrepancy_ratio_bps=0,"
                "     discrepancy_band='within_tolerance'"
                " WHERE tenant_id=%s AND id=%s",
                (tenant, verdict),
            )
        ref.commit()
        ref.close()
        checks["live_external_false_world_refused"] = True
        checks["live_external_false_world_restored"] = True
    except Exception as exc:  # noqa: BLE001 - surface the failing cell
        violations.append(
            f"xxii_comp_false_world_failed:{type(exc).__name__}:{exc}"
        )
    finally:
        if seeded:
            # The ledger is a global hash chain. Deleting one tenant's rows
            # breaks the predecessor link for every later append, so the cell
            # deliberately leaves its lawful appends in place and asserts the
            # chain is still clean.
            try:
                cleanup = psycopg2.connect(dsn)
                cleanup.autocommit = True
                with cleanup.cursor() as cur:
                    cur.execute(
                        "SELECT public.b26_p2_read_history_violations()"
                    )
                    raw_residual = cur.fetchone()[0] or ""
                cleanup.close()
                residual = [
                    value for value in str(raw_residual).split(",") if value
                ]
                checks["live_external_false_world_chain_preserved"] = (
                    not residual
                )
                if residual:
                    violations.append(
                        "xxii_comp_false_world_chain_polluted:"
                        + ",".join(residual)
                    )
            except Exception as exc:  # noqa: BLE001 - surface the failing cell
                violations.append(
                    "xxii_comp_false_world_chain_unverified:"
                    f"{type(exc).__name__}:{exc}"
                )
        try:
            admin.close()  # type: ignore[name-defined]
        except Exception:  # noqa: BLE001
            pass


def _xxv_attestation_sweep_cell(dsn: str, violations: list[str], checks: dict) -> None:
    """XXV (A12): judge the live financial state, not a self-made fixture.

    Both XXIV audits obtained ``B26_P2_XXII_COMPOSITION_PASS`` -- including a
    cell literally named ``live_external_false_world_refused`` -- while a
    coherently forged amount was being served as current money. The cell was
    asserting that the validator's OWN mutation had been refused, which is a
    statement about the validator, not about the database.

    This cell walks every verdict in the database under proof and requires
    each one's money to be justified by a signature produced by the
    authentication root. No in-database principal can satisfy that, so a
    false world introduced by anyone -- including an auditor who never
    touched this script -- turns the mandatory proof RED.
    """
    from b26_p2_xxv_attestation_sweep import (  # noqa: PLC0415
        default_public_key_path,
        sweep,
    )

    try:
        result = sweep(dsn, public_key_path=default_public_key_path())
    except Exception as exc:  # noqa: BLE001 - an unrunnable oracle is a failure
        violations.append(f"xxv_attestation_sweep_unrunnable:{type(exc).__name__}:{exc}")
        return
    checks["live_xxv_attestation_sweep"] = True
    checks["live_xxv_attestation_census"] = result["census"]
    checks["live_xxv_verdicts_examined"] = result["verdicts_examined"]
    source_status = str(
        result.get("source_evidence", {}).get("status", "")
    )
    if source_status.startswith("FAIL:"):
        checks["live_xxv_attestation_sweep"] = False
        violations.append(f"xxv_source_evidence:{source_status}")
    if result["unverifiable"]:
        checks["live_xxv_attestation_sweep"] = False
        for row in result["unverifiable"][:10]:
            violations.append(
                "xxv_source_money_unattested:"
                f"{row['verdict_id']}:{row['reason']}"
            )


def _live_conduction_completeness_cell(
    dsn: str, violations: list[str], checks: dict
) -> None:
    """Every current first-authenticated source must have a consequence.

    A source with an earlier authenticated sibling is an amendment awaiting
    the authorised correction surface, not a missing match. A first source
    older than the grace window with no verdict is accepted ingress that the
    required B2.3 financial consumer did not conduct. This is the B6/HB-14
    negative-control oracle: removing the worker used to leave the mandatory
    proof green.
    """
    import psycopg2  # noqa: PLC0415

    conn = psycopg2.connect(dsn)
    try:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT i.id::text, i.provider,
                       i.event_timestamp
                  FROM public.webhook_ingress_identities AS i
                 WHERE i.verified_commerce_ingress_state =
                       'authenticity_verified'
                   AND i.b26_p2_provenance_status = 'authenticated_known'
                   AND i.b26_p2_demotion_reason IS NULL
                   AND i.event_timestamp < now() - interval '60 seconds'
                   AND NOT EXISTS (
                       SELECT 1 FROM public.b23_match_verdicts AS v
                        WHERE v.webhook_ingress_identity_id = i.id
                   )
                   AND NOT EXISTS (
                       SELECT 1
                         FROM public.webhook_ingress_identities AS prior
                        WHERE prior.tenant_id = i.tenant_id
                          AND prior.provider = i.provider
                          AND prior.normalized_commerce_reference_kind
                              IS NOT DISTINCT FROM
                              i.normalized_commerce_reference_kind
                          AND prior.normalized_commerce_reference_value
                              IS NOT DISTINCT FROM
                              i.normalized_commerce_reference_value
                          AND prior.b26_p2_provenance_status =
                              'authenticated_known'
                          AND prior.id <> i.id
                          AND (prior.created_at, prior.id)
                              < (i.created_at, i.id)
                   )
                 ORDER BY i.event_timestamp ASC
                 LIMIT 5
                """
            )
            rows = cur.fetchall()
    finally:
        conn.close()
    if rows:
        violations.append(
            "xxii_comp_conduction_missing:"
            + ";".join(f"{row[0]}:{row[1]}" for row in rows)
        )
    checks["live_conduction_completeness"] = not rows


def _live_checks(dsn: str, violations: list[str], checks: dict) -> None:
    import os  # noqa: PLC0415

    os.environ.setdefault(
        "DATABASE_URL", dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
    )
    try:
        import psycopg2  # noqa: PLC0415
    except ImportError as exc:
        violations.append(f"xxii_comp_no_driver:{exc}")
        return
    try:
        conn = psycopg2.connect(dsn)
        conn.autocommit = False
    except Exception as exc:
        violations.append(f"xxii_comp_connect_failed:{exc}")
        return
    try:
        cur = conn.cursor()
        cur.execute("SELECT version_num FROM public.alembic_version")
        if cur.fetchone()[0] != HEAD:
            violations.append("xxii_comp_head_not_live")
        checks["live_head"] = True

        cur.execute(
            "SELECT proname, prosecdef,"
            " has_function_privilege('app_user', p.oid, 'EXECUTE'),"
            " has_function_privilege('app_worker', p.oid, 'EXECUTE'),"
            " has_function_privilege('app_beat', p.oid, 'EXECUTE')"
            " FROM pg_proc p WHERE p.pronamespace = 'public'::regnamespace"
            " AND p.proname IN ('b26_p2_read_history_witness_state',"
            " 'b26_p2_read_history_prefix_digest',"
            " 'b26_p2_read_history_entry_hash',"
            " 'b26_p2_read_history_violations')"
        )
        rows = cur.fetchall()
        if len(rows) != 4:
            violations.append("xxii_comp_reader_surface_incomplete")
        for name, definer, user_ok, worker_ok, beat_ok in rows:
            if not definer:
                violations.append(f"xxii_comp_not_definer:{name}")
            if not (user_ok and worker_ok and beat_ok):
                violations.append(f"xxii_comp_reader_grant_missing:{name}")
        checks["live_reader_surface"] = True

        cur.execute(
            "SELECT has_function_privilege('app_user',"
            " 'public.b26_p2_verify_source_money_conservation(uuid,uuid)',"
            " 'EXECUTE'), has_function_privilege('app_trust_issuer',"
            " 'public.b26_p2_verify_source_money_conservation(uuid,uuid)',"
            " 'EXECUTE')"
        )
        if cur.fetchone() != (True, True):
            violations.append("xxii_comp_conservation_grant_missing")
        checks["live_conservation_surface"] = True

        cur.execute(
            "SELECT tgname FROM pg_trigger WHERE NOT tgisinternal AND tgname IN"
            " ('trg_b26_p2_observation_chronology',"
            "  'trg_b26_p2_ingress_event_chronology')"
        )
        triggers = {row[0] for row in cur.fetchall()}
        if triggers != {
            "trg_b26_p2_observation_chronology",
            "trg_b26_p2_ingress_event_chronology",
        }:
            violations.append("xxii_comp_chronology_trigger_missing")
        checks["live_chronology_triggers"] = True

        cur.execute(
            "SELECT public.b26_p2_enforce_lifecycle_admission("
            "'shopify','orders.create','pending',NULL,false,"
            "%s::timestamptz,%s::timestamptz,true)",
            ("2026-10-01T00:00:00+00:00", "2026-10-01T00:00:30+00:00"),
        )
        _expect_exception(
            cur,
            "SELECT public.b26_p2_enforce_lifecycle_admission("
            "'shopify','orders.create','pending',NULL,false,"
            "%s::timestamptz,%s::timestamptz,true)",
            ("2026-10-01T00:00:00+00:00", "2026-10-01T00:02:00+00:00"),
            "b26_p2_lifecycle_not_creation_moment",
        )
        _expect_exception(
            cur,
            "SELECT public.b26_p2_enforce_lifecycle_admission("
            "'shopify','orders.create','pending',NULL,false,"
            "%s::timestamptz,%s::timestamptz,true)",
            ("2026-10-01T00:00:30+00:00", "2026-10-01T00:00:00+00:00"),
            "b26_p2_lifecycle_reversed_chronology",
        )
        cur.execute(
            "SELECT public.b26_p2_enforce_lifecycle_admission("
            "'shopify','orders.create','pending',NULL,false,"
            "%s::timestamptz,%s::timestamptz,true)",
            ("2026-10-01T00:00:00+00:00", "2026-10-01T00:00:00+00:00"),
        )
        checks["live_creation_law"] = True

        tenant = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.tenants (id, name, api_key_hash,"
            " notification_email) VALUES (%s,%s,%s,%s)",
            (tenant, "xxii-comp", uuid.uuid4().hex, "xxii@example.invalid"),
        )
        cur.execute(
            "SELECT set_config('app.current_tenant_id', %s, false)", (tenant,)
        )
        cur.execute(
            "INSERT INTO public.channel_taxonomy (code, family, is_paid,"
            " display_name, state) VALUES ('xxii_comp_ch', 'xxii', true,"
            " 'XXII', 'active') ON CONFLICT (code) DO NOTHING"
        )
        _expect_exception(
            cur,
            "INSERT INTO public.b26_p2_history_integrity_observations"
            "(ledger_count, ledger_tip, observer_violations, observed_at,"
            " author) VALUES (0,NULL,'',now() + interval '10 minutes',"
            "'app_worker')",
            (),
            "b26_p2_observation_future_refused",
        )
        event = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.attribution_events (id, tenant_id,"
            " occurred_at, correlation_id, session_id, revenue_cents,"
            " raw_payload, idempotency_key, event_type, channel,"
            " campaign_id, conversion_value_cents, currency,"
            " event_timestamp, processed_at, processing_status)"
            " VALUES (%s,%s,now(),%s,%s,1000,'{}'::jsonb,%s,'conversion',"
            " 'xxii_comp_ch','c',1000,'USD',now(),now(),'processed')",
            (
                event,
                tenant,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ),
        )
        _expect_exception(
            cur,
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
            " event_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',"
            " %s,1000,'USD',now() + interval '10 minutes',%s,"
            " 'authenticity_verified')",
            (
                str(uuid.uuid4()),
                tenant,
                event,
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
                str(uuid.uuid4()),
            ),
            "b26_p2_ingress_event_future_refused",
        )
        checks["live_future_refusals"] = True

        ingress = str(uuid.uuid4())
        event_ref = str(uuid.uuid4())
        commerce_ref = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.webhook_ingress_identities (id, tenant_id,"
            " event_id, provider, provider_native_event_reference,"
            " provider_native_commerce_reference,"
            " normalized_commerce_reference_kind,"
            " normalized_commerce_reference_value, verified_amount_minor,"
            " verified_amount_currency, event_timestamp, idempotency_key,"
            " verified_commerce_ingress_state)"
            " VALUES (%s,%s,%s,'stripe',%s,%s,'stripe_payment_intent_id',"
            " %s,1000,'USD',now(),%s,'authenticity_verified')",
            (
                ingress,
                tenant,
                event,
                event_ref,
                commerce_ref,
                commerce_ref,
                str(uuid.uuid4()),
            ),
        )
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family',"
            " 'payment_intent.succeeded', false)"
        )
        cur.execute(
            "SELECT set_config('app.b26_p2_event_family_source',"
            " 'body-signal:type', false)"
        )
        cur.execute(
            "SELECT public.b26_p2_authenticate_ingress_atomic_v2("
            " %s,'stripe',%s,%s,%s,'hmac-sha256-timestamped-hex','v1',"
            " NULL,NULL,FALSE,NULL,NULL)",
            (
                ingress,
                event_ref,
                "c" * 64,
                "d" * 64,
            ),
        )
        verdict = str(uuid.uuid4())
        cur.execute(
            "INSERT INTO public.b23_match_verdicts (id, tenant_id,"
            " attribution_event_id, webhook_ingress_identity_id, provider,"
            " canonical_commerce_reference, provider_native_event_reference,"
            " provider_native_commerce_reference, status, match_quality,"
            " attributed_amount_minor, verified_amount_minor, currency_code,"
            " last_transition_at, canonical_expected_gross_amount_minor,"
            " canonical_captured_gross_amount_minor,"
            " canonical_net_verified_amount_minor, discrepancy_amount_minor,"
            " discrepancy_ratio_bps, discrepancy_band)"
            " VALUES (%s,%s,%s,%s,'stripe',%s,%s,%s,'matched_confirmed',"
            " 'high',1000,1000,'USD',now(),1000,1000,1000,0,0,'exact')",
            (
                verdict,
                tenant,
                event,
                ingress,
                uuid.uuid4().hex,
                uuid.uuid4().hex,
                uuid.uuid4().hex,
            ),
        )

        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (tenant, verdict),
        )
        if cur.fetchall() != []:
            violations.append("xxii_comp_conservation_clean_not_clean")

        for _ in range(2):
            cur.execute(
                "INSERT INTO public.b26_p2_verdict_supersession_ledger"
                "(verdict_id, tenant_id, provider,"
                " provider_native_event_reference, prior_source_ingress,"
                " new_source_ingress, prior_attributed_amount_minor,"
                " new_attributed_amount_minor, prior_verified_amount_minor,"
                " new_verified_amount_minor, prior_authority_state,"
                " new_authority_state) VALUES"
                " (%s,%s,'stripe',%s,%s,%s,1000,1000,1000,1000,'a','b')",
                (verdict, tenant, uuid.uuid4().hex, ingress, ingress),
            )
        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (tenant, verdict),
        )
        if cur.fetchall() != []:
            violations.append("xxii_comp_conservation_chain_not_clean")

        _count, _seq, _tip, _digest, _universe = _live_state(cur)
        _coherent_rewrite_cell(
            cur,
            ledger_count=_count,
            ledger_tip_seq=_seq,
            ledger_tip_hash=_tip,
            violations=violations,
            checks=checks,
        )

        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " DISABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
        )
        cur.execute(
            "UPDATE public.b26_p2_verdict_supersession_ledger"
            " SET new_verified_amount_minor=999"
            " WHERE seq = (SELECT max(seq) FROM"
            " public.b26_p2_verdict_supersession_ledger"
            " WHERE tenant_id=%s AND verdict_id=%s)",
            (tenant, verdict),
        )
        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " ENABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
        )
        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (tenant, verdict),
        )
        current_rows = [row[0] for row in cur.fetchall()]
        if current_rows != ["conservation_ledger_not_current"]:
            violations.append(
                f"xxii_comp_conservation_current_blind:{current_rows}"
            )

        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " DISABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
        )
        cur.execute(
            "UPDATE public.b26_p2_verdict_supersession_ledger"
            " SET new_verified_amount_minor=1000"
            " WHERE seq = (SELECT max(seq) FROM"
            " public.b26_p2_verdict_supersession_ledger"
            " WHERE tenant_id=%s AND verdict_id=%s)",
            (tenant, verdict),
        )
        cur.execute(
            "ALTER TABLE public.b26_p2_verdict_supersession_ledger"
            " ENABLE TRIGGER trg_b26_p2_xix_ledger_immutable"
        )
        cur.execute(
            "INSERT INTO public.b26_p2_verdict_supersession_ledger"
            "(verdict_id, tenant_id, provider,"
            " provider_native_event_reference, prior_source_ingress,"
            " new_source_ingress, prior_attributed_amount_minor,"
            " new_attributed_amount_minor, prior_verified_amount_minor,"
            " new_verified_amount_minor, prior_authority_state,"
            " new_authority_state) VALUES"
            " (%s,%s,'stripe',%s,%s,%s,900,900,900,900,'b','c')",
            (verdict, tenant, uuid.uuid4().hex, ingress, ingress),
        )
        cur.execute(
            "SELECT violation FROM"
            " public.b26_p2_verify_source_money_conservation(%s,%s)",
            (tenant, verdict),
        )
        chain_rows = [row[0] for row in cur.fetchall()]
        if not chain_rows or chain_rows[0] != "conservation_chain_discontinuous":
            violations.append(
                f"xxii_comp_conservation_chain_blind:{chain_rows}"
            )
        checks["live_conservation_cells"] = True

        cur.execute("SELECT public.b26_p2_read_history_prefix_digest()")
        digest = cur.fetchone()[0]
        cur.execute(
            "SELECT encode(digest(coalesce(string_agg(l.seq::text || ':' ||"
            " l.entry_hash, '|' ORDER BY l.seq), ''), 'sha256'), 'hex')"
            " FROM public.b26_p2_verdict_supersession_ledger l"
        )
        expected_digest = cur.fetchone()[0]
        if digest != expected_digest:
            violations.append("xxii_comp_prefix_digest_wrong")
        checks["live_prefix_digest"] = True

        _count, _seq, _tip, _digest, _universe = _live_state(cur)
        _truncate_cell(
            cur,
            ledger_count=_count,
            ledger_tip_seq=_seq,
            ledger_tip_hash=_tip,
            violations=violations,
            checks=checks,
        )

        conn.rollback()
        _live_conduction_completeness_cell(dsn, violations, checks)
        _external_false_world_cell(dsn, violations, checks)
        _xxv_attestation_sweep_cell(dsn, violations, checks)
        _source_evidence_cell(dsn, violations, checks)
    except Exception as exc:  # noqa: BLE001 - surface the failing cell
        violations.append(f"xxii_comp_live_failed:{type(exc).__name__}:{exc}")
        try:
            conn.rollback()
        except Exception:  # noqa: BLE001
            pass
    finally:
        conn.close()


def _source_evidence_cell(
    dsn: str, violations: list[str], checks: dict
) -> None:
    """Compare the live complete lifecycle manifest to the signed witness.

    The per-fact attestation sweep proves each present fact; this cell proves
    the set is the set the independent observer signed. It is deliberately
    separate so a present-but-forged fact and a missing-but-signed fact both
    fail the same governing proof.
    """
    import os  # noqa: PLC0415

    journal_path = os.getenv("B26_P2_HISTORY_WITNESS_JOURNAL_PATH", "").strip()
    public_key_path = os.getenv(
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH", ""
    ).strip()
    if not journal_path or not public_key_path:
        checks["live_source_evidence"] = "SKIPPED:no_witness_env"
        return
    try:
        from sqlalchemy.ext.asyncio import (  # noqa: PLC0415
            AsyncSession,
            create_async_engine,
        )

        from app.revenue_verification.source_evidence import (  # noqa: PLC0415
            source_evidence_snapshots,
        )
        from app.trust.history_witness import (  # noqa: PLC0415
            load_public_key,
            verify_journal,
        )

        async def _snapshots():
            engine = create_async_engine(
                dsn.replace("postgresql://", "postgresql+asyncpg://", 1)
            )
            try:
                async with AsyncSession(engine) as session:
                    return await source_evidence_snapshots(session)
            finally:
                await engine.dispose()

        snapshots = asyncio.run(_snapshots())
        journal = verify_journal(
            journal_path,
            public_key=load_public_key(public_key_path),
            require_freshness=False,
        )
        latest = journal.latest
        if latest.source_evidence_by_tenant is None:
            violations.append("xxii_comp_source_evidence_missing")
            return
        expected = {
            tenant: str(snapshot["digest"])
            for tenant, snapshot in snapshots.items()
        }
        if expected != dict(latest.source_evidence_by_tenant):
            violations.append("xxii_comp_source_evidence_diverged")
            return
        checks["live_source_evidence"] = True
    except Exception as exc:  # noqa: BLE001 - surface the failing cell
        violations.append(
            f"xxii_comp_source_evidence_failed:{type(exc).__name__}:{exc}"
        )


def main() -> int:
    parser = argparse.ArgumentParser(description="XXII composition closure.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _static_checks(violations, checks)
    if args.dsn is not None:
        _live_checks(args.dsn, violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XXII_COMPOSITION_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B2.6-P2-XXII-COMPOSITION",
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
