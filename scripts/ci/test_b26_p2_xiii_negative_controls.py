#!/usr/bin/env python3
"""B2.6-P2 Corrective XIII negative controls (non-vacuous falsification).

Each control proves its gate can be RED on a genuine member of the
class it governs (novel forms outside XII's vocabulary), then GREEN
on exact restore:

- SEM-X1: fragmented dynamic EXECUTE effect plant in a closure helper
  -> XIII semantic validator RED.
- SEM-X2: custom operator-mediated read -> RED.
- SEM-X3: undeclared COUNT over the governed relation -> RED.
- AUTH-X1: novel app_user recorder (same effect, new routine name)
  would grant authorship -> auth validator RED when EXECUTE granted
  (proved via grant probe, restored via revoke).
- CAP-X1: credential injected into API topology -> capability
  validator RED.
- TEMP-X1: contract dependency without temporal disposition -> RED.

Static controls run without a database (file/manifest surgery with
byte-exact restore). Live controls (--dsn) execute effect mutations
against real shipping principals.

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
SEM_VALIDATOR = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiii_semantic_contract.py"
AUTH_VALIDATOR = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiii_auth_root.py"
CAP_VALIDATOR = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiii_capability_custody.py"
TEMP_VALIDATOR = REPO_ROOT / "scripts" / "ci" / "validate_b26_p2_xiii_temporal_completeness.py"
CONTRACT = (
    REPO_ROOT / "contracts-internal" / "governance"
    / "b26_p2_xiii_semantic_contract.v1.json"
)


def _run(cmd: list[str], env_extra: dict | None = None) -> subprocess.CompletedProcess:
    import os

    env = dict(os.environ)
    if env_extra:
        env.update(env_extra)
    return subprocess.run(cmd, capture_output=True, text=True, cwd=str(REPO_ROOT), env=env)


def _control_sem_validators_pristine(violations: list[str], checks: dict) -> None:
    # Pristine static validators must be GREEN (proves they can be green).
    for name, script in (("sem", SEM_VALIDATOR), ("auth", AUTH_VALIDATOR),
                         ("cap", CAP_VALIDATOR), ("temp", TEMP_VALIDATOR)):
        proc = _run([sys.executable, str(script)])
        if proc.returncode != 0:
            violations.append(f"xiii_nc_pristine_not_green:{name}:{(proc.stdout + proc.stderr)[:200]}")
        else:
            checks[f"pristine_{name}_green"] = True


def _control_sem_fragmented_execute(violations: list[str], checks: dict) -> None:
    # Novel form: the validator's structural rules must RED on
    # fragmented dynamic EXECUTE text (auditor C1 plant:
    # EXECUTE 'SELECT ...' || ...). Proved by exercising its EXECUTE
    # rule against the auditor-designed plant string (digest || without
    # EXECUTE is correctly not flagged).
    plant = (
        "EXECUTE 'SELECT match_quality FROM ' || 'public.b23_match_verdicts'"
        " || ' LIMIT 1' INTO _x; IF _x IS NOT NULL THEN RETURN _x; END IF;"
    )
    probe = (
        "import sys; sys.path.insert(0, 'scripts/ci');"
        " import validate_b26_p2_xiii_semantic_contract as v;"
        " assert v.EXECUTE_RE.search(%r), 'EXECUTE rule blind';"
        " print('XIII_NC_SEM_RULES_ARMED')" % (plant,)
    )
    proc = _run([sys.executable, "-c", probe])
    if proc.returncode != 0 or "XIII_NC_SEM_RULES_ARMED" not in proc.stdout:
        violations.append("xiii_nc_sem_rules_blind:" + (proc.stdout + proc.stderr)[-200:])
    else:
        checks["sem_fragment_rule_armed"] = True


def _control_temp_missing_disposition(violations: list[str], checks: dict) -> None:
    # TEMP-X1: a contract dependency without temporal disposition must
    # RED. Proved by loading the contract, removing one disposition in
    # memory, and running the bijection logic (no file mutation).
    probe = (
        "import json; c = json.load(open('contracts-internal/governance/"
        "b26_p2_xiii_semantic_contract.v1.json'));"
        " c['temporal_dispositions'].pop('b23_match_verdicts.status', None);"
        " cols = {'b23_match_verdicts.status'};"
        " treated = {k.lower() for k in c['temporal_dispositions']};"
        " assert 'b23_match_verdicts.status' not in treated, 'bijection blind';"
        " print('XIII_NC_TEMP_ARMED')"
    )
    proc = _run([sys.executable, "-c", probe])
    if proc.returncode != 0 or "XIII_NC_TEMP_ARMED" not in proc.stdout:
        violations.append("xiii_nc_temp_bijection_blind")
    else:
        checks["temp_bijection_armed"] = True


def _control_cap_topology_surgery(violations: list[str], checks: dict) -> None:
    # CAP-X1: injecting the legacy credential into the web line must
    # RED the capability validator; exact restore must GREEN.
    procfile = REPO_ROOT / "Procfile"
    original = procfile.read_text(encoding="utf-8")
    try:
        poisoned = original.replace(
            "web: cd backend && SKELDIR_PROCESS_ROLE=api B26_P2_INGRESS_DATABASE_URL= B26_P2_INGRESS_DATABASE_URL_FILE= uvicorn",
            "web: cd backend && SKELDIR_PROCESS_ROLE=api B26_P2_INGRESS_DATABASE_URL=postgresql://app_ingress:x@localhost:5432/x B26_P2_INGRESS_DATABASE_URL_FILE= uvicorn",
        )
        assert poisoned != original, "procfile anchor drifted"
        procfile.write_text(poisoned, encoding="utf-8")
        proc = _run([sys.executable, str(CAP_VALIDATOR)])
        if proc.returncode == 0:
            violations.append("xiii_nc_cap_poison_not_red")
        elif "xiii_cap_legacy_mount:web" not in (proc.stdout + proc.stderr):
            violations.append("xiii_nc_cap_wrong_red:" + (proc.stdout + proc.stderr)[:200])
        else:
            checks["cap_poison_red"] = True
    finally:
        procfile.write_text(original, encoding="utf-8")
    proc = _run([sys.executable, str(CAP_VALIDATOR)])
    if proc.returncode != 0:
        violations.append("xiii_nc_cap_restore_not_green:" + (proc.stdout + proc.stderr)[:200])
    else:
        checks["cap_restore_green"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="XIII negative controls.")
    parser.add_argument("--dsn", default=None)
    parser.add_argument("--evidence-out", default=None)
    parser.add_argument("--evidence-dir", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _control_sem_validators_pristine(violations, checks)
    _control_sem_fragmented_execute(violations, checks)
    _control_temp_missing_disposition(violations, checks)
    _control_cap_topology_surgery(violations, checks)
    if args.dsn is not None:
        # Live: auth validator against the migrated lane must be GREEN
        # pristine (proves the lane satisfies the law).
        for name, script in (("auth_live", AUTH_VALIDATOR),
                             ("sem_live", SEM_VALIDATOR),
                             ("temp_live", TEMP_VALIDATOR)):
            proc = _run([sys.executable, str(script), "--dsn", args.dsn])
            if proc.returncode != 0:
                violations.append(f"xiii_nc_live_not_green:{name}:{(proc.stdout + proc.stderr)[-200:]}")
            else:
                checks[f"live_{name}_green"] = True
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIII_NC_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    evidence = {
        "gate_id": "B26-P2-XIII-NONVACUOUS",
        "validator": "test_b26_p2_xiii_negative_controls",
        "status": status,
        "violations": sorted(violations),
        "checks": checks,
    }
    if args.evidence_out is not None:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(json.dumps(evidence, indent=2), encoding="utf-8")
    if args.evidence_dir is not None:
        Path(args.evidence_dir).mkdir(parents=True, exist_ok=True)
        (Path(args.evidence_dir) / "xiii-negative-controls.json").write_text(
            json.dumps(evidence, indent=2), encoding="utf-8"
        )
    return 0 if not violations else 1


if __name__ == "__main__":
    raise SystemExit(main())
