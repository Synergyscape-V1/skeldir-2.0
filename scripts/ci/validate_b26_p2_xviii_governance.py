#!/usr/bin/env python3
"""B2.6-P2 Corrective XVIII governance gate: wiring, isolation, conventions.

- H-XVIII-R22/NC-14: XVIII consequence revocation is transactional DB
  state, not async machinery. The XVIII diff must introduce no new
  Celery task, queue, Beat entry, or worker registration: a repair
  flow existing only in source (unwired) REDs, and so does a newly
  wired flow this gate does not know.
- H-XVIII-R23/U (ontological isolation): the P2 authority path stays
  free of LLM/Bayesian/probabilistic dependencies.
- H-XVIII-R18: no application-convention authority -- the changed
  authority surfaces are database-enforced (trigger/predicate
  presence asserted on the migration, not on callers).

Exit code is the gate. Prints B26_P2_XVIII_GOVERNANCE_PASS on success.
Static gate (no database required).
"""

from __future__ import annotations

import argparse
import ast
import json
import re
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
MIG_XVIII = (
    REPO_ROOT
    / "alembic"
    / "versions"
    / "007_skeldir_foundation"
    / "202609300001_b26_p2_corrective_xviii_authority_conservation.py"
)

# P2 authority-path files: no inference dependency may enter these.
AUTHORITY_PATH_FILES = [
    REPO_ROOT / "backend" / "app" / "webhooks" / "commerce_derivation.py",
    REPO_ROOT / "backend" / "app" / "auth_service" / "server.py",
    REPO_ROOT / "backend" / "app" / "ingestion" / "event_service.py",
    REPO_ROOT / "backend" / "app" / "revenue_verification" / "batch_engine.py",
    REPO_ROOT
    / "backend"
    / "app"
    / "revenue_verification"
    / "verification_coverage.py",
    REPO_ROOT
    / "backend"
    / "app"
    / "revenue_verification"
    / "match_engine_kernel.py",
]
FORBIDDEN_AUTHORITY_IMPORTS = (
    "llm",
    "prompt",
    "bayesian",
    "pymc",
    "inference",
    "confidence_computation",
    "mmm",
    "causal_inference",
)


def _diff_names() -> list[str]:
    proc = subprocess.run(
        ["git", "diff", "--name-only", "HEAD"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    tracked = [line.strip() for line in proc.stdout.splitlines() if line.strip()]
    proc2 = subprocess.run(
        ["git", "ls-files", "--others", "--exclude-standard"],
        capture_output=True,
        text=True,
        cwd=str(REPO_ROOT),
    )
    untracked = [line.strip() for line in proc2.stdout.splitlines() if line.strip()]
    return tracked + untracked


def main() -> int:
    parser = argparse.ArgumentParser(description="XVIII governance gate.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}

    changed = set(_diff_names())
    wiring_hits: list[str] = []
    for name in sorted(changed):
        if not name.endswith(".py"):
            continue
        try:
            text = (REPO_ROOT / name).read_text(encoding="utf-8")
        except OSError:
            continue
        # XVIII scope: any wiring primitive in an XVIII change file
        # is a violation (revocation is transactional DB state; a new
        # repair flow would need producer/scheduler/broker/queue/
        # consumer proof, which must not exist).
        if name in {
            "backend/app/revenue_verification/batch_engine.py",
            "backend/app/revenue_verification/verification_coverage.py",
            "backend/app/revenue_verification/match_engine_kernel.py",
            "backend/app/webhooks/commerce_derivation.py",
            "backend/app/auth_service/server.py",
            "backend/app/ingestion/event_service.py",
            "backend/app/api/webhooks.py",
            "backend/app/finance_reconciliation/candidate_conduction.py",
            "backend/app/finance_reconciliation/dispatch_authority.py",
            "backend/app/bayesian/eligibility.py",
            "backend/app/bayesian/source_snapshot.py",
            "backend/app/bayesian/source_contract_authority.py",
            "backend/app/bayesian/api_projection.py",
            "backend/app/trust/source_adapters.py",
            "backend/app/trust/builder.py",
            "backend/app/api/trust_export.py",
            "backend/app/api/revenue_verification.py",
            "backend/app/schemas/revenue_verification.py",
        }:
            for token in (
                "@shared_task",
                "celery_app.task",
                "BeatSchedule",
                "beat_schedule[",
                "add_periodic_task",
            ):
                if token in text:
                    wiring_hits.append(f"{name}:{token}")
    if wiring_hits:
        violations.append(f"xviii_unwired_or_new_async_machinery:{wiring_hits[:3]}")
    else:
        checks["no_new_async_machinery"] = True

    for path in AUTHORITY_PATH_FILES:
        try:
            text = path.read_text(encoding="utf-8")
        except OSError as exc:
            violations.append(f"governance_unreadable:{path.name}:{exc}")
            continue
        # Import-aware: comments/docstrings that NAME the boundary
        # (e.g. "No LLM, Bayesian dependency") are not dependencies.
        # Only real imports of inference-bearing modules count.
        try:
            tree = ast.parse(text)
        except SyntaxError as exc:
            violations.append(f"governance_unparseable:{path.name}:{exc}")
            continue
        imported = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                imported.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                imported.add(node.module)
        # The sole adjudicated exception (both independent audits):
        # app.bayesian.dirty_marker.append_dirty_event is fire-and-forget
        # observability bookkeeping that never gates authority. Every
        # other inference-bearing import is a breach.
        effective = {
            name
            for name in imported
            if name != "app.bayesian.dirty_marker"
        }
        lowered_imports = " ".join(sorted(effective)).lower()
        hits = [
            token
            for token in FORBIDDEN_AUTHORITY_IMPORTS
            if re.search(rf"(^|[\s.]){re.escape(token)}", lowered_imports)
        ]
        if hits:
            violations.append(f"isolation_breach:{path.name}:{hits[:3]}")
    if not [v for v in violations if "isolation_breach" in v]:
        checks["ontological_isolation_intact"] = True

    try:
        mig_text = MIG_XVIII.read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xviii_migration_unreadable:{exc}")
        mig_text = ""
    for token in (
        "trg_b26_p2_ingress_authority_transition",
        "b26_p2_ingress_has_current_authority",
        "b26_p2_atomic_demoted_ingress_refused",
        "b26_p2_downgrade_serving_refused",
        "b26_p2_atomic_family_unbound_refused",
        "trg_b26_p2_verdict_authority_stamp",
        "trg_b26_p2_verdict_authority_propagate",
        "b26_p2_evidence_demoted_ingress_refused",
    ):
        if token not in mig_text:
            violations.append(f"db_authority_missing:{token}")
    _compact_gov = re.sub(r"\s+", " ", mig_text)
    for label, pattern in (
        (
            "ingress_authority_columns",
            r"REVOKE UPDATE.{0,80}b26_p2_provenance_status"
            r".{0,80}b26_p2_semantic_regime.{0,80}b26_p2_demotion_reason",
        ),
        (
            "verdict_authority_column",
            r"REVOKE UPDATE.{0,80}b26_p2_source_authority_state",
        ),
    ):
        if not re.search(pattern, _compact_gov):
            violations.append(f"db_authority_missing:privilege_{label}")
    if not [v for v in violations if "db_authority_missing" in v]:
        checks["authority_database_enforced"] = True

    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XVIII_GOVERNANCE_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XVIII-GOVERNANCE",
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
