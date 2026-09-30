#!/usr/bin/env python3
"""B2.6-P2 Corrective XIV cross-lane topology equivalence (BLOCKERS B/G).

Law: PRODUCTION, E2E P2, C19 P2, B0.4 P2 (serving shape), and the XIV
exit harness all use the SAME authority topology:

- the general API is role=api, holds NO authenticated-ingress DB
  credential in any form (env string or file), and relays to the root
  (B26_P2_AUTH_ROOT_URL set);
- the dedicated authentication trust root is role=auth_ingress and the
  SOLE holder of the file-mounted ingress credential;
- exactly one secret-delivery mechanism exists (file/secret mount; the
  legacy environment-string fallback is absent everywhere, including
  test lanes and backend code outside the refusal/sanitizer boundary);
- no worker/relay/beat/B2.3 process holds the credential.

Allowed differences: ports, ephemeral secret values, database names,
test fixture tenants. Forbidden: API-as-auth-root in any
P2-equivalent lane, root absent in production, env credential in one
lane vs file in another P2 proof lane, different DB principal
authority.

Exit code is the gate.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]

LEGACY_TOKEN = "B26_P2_INGRESS_DATABASE_URL"
FILE_TOKEN = "B26_P2_INGRESS_DATABASE_URL_FILE"
ROLE_TOKEN = "SKELDIR_PROCESS_ROLE"
RELAY_TOKEN = "B26_P2_AUTH_ROOT_URL"


def _compose_service_env(path: Path) -> dict[str, dict[str, str]]:
    """Parse top-level service environment lines (best-effort YAML scan)."""
    body = path.read_text(encoding="utf-8")
    services: dict[str, dict[str, str]] = {}
    current: str | None = None
    in_env = False
    for line in body.splitlines():
        m = re.match(r"^  ([a-z0-9_]+):\s*$", line)
        if m:
            current = m.group(1)
            services[current] = {}
            in_env = False
            continue
        if current is None:
            continue
        if re.match(r"^    environment:\s*$", line):
            in_env = True
            continue
        if re.match(r"^    [a-z_]+:", line):
            in_env = False
            continue
        if in_env:
            m2 = re.match(r"^\s+([A-Z0-9_]+):\s*(.*)$", line.strip() and line)
            if m2:
                key = m2.group(1).strip()
                val = m2.group(2).strip().strip('"').strip("'")
                services[current][key] = val
    return services


def _lane_checks(violations: list[str], checks: dict) -> None:
    lanes = {
        "production(local)": REPO_ROOT / "docker-compose.local.yml",
        "e2e": REPO_ROOT / "docker-compose.e2e.yml",
        "c19": REPO_ROOT / "docker-compose.c19.yml",
    }
    for lane, path in lanes.items():
        if not path.is_file():
            violations.append(f"xiv_topo_lane_missing:{lane}")
            continue
        services = _compose_service_env(path)
        api = services.get("api", {})
        # API: non-auth role, no credential in any form, relay set.
        if api.get(ROLE_TOKEN, "") != "api":
            violations.append(f"xiv_topo_api_role_not_api:{lane}:{api.get(ROLE_TOKEN)}")
        if api.get(LEGACY_TOKEN, "").strip():
            violations.append(f"xiv_topo_api_legacy_mount:{lane}")
        if api.get(FILE_TOKEN, "").strip():
            violations.append(f"xiv_topo_api_file_mount:{lane}")
        if not api.get(RELAY_TOKEN, "").strip():
            violations.append(f"xiv_topo_api_no_relay:{lane}")
        # Root: sole file holder with auth role.
        root = services.get("auth_ingress", {})
        if root.get(ROLE_TOKEN, "") != "auth_ingress":
            violations.append(f"xiv_topo_root_role:{lane}:{root.get(ROLE_TOKEN)}")
        if not root.get(FILE_TOKEN, "").strip():
            violations.append(f"xiv_topo_root_no_file:{lane}")
        if root.get(LEGACY_TOKEN, "").strip():
            violations.append(f"xiv_topo_root_legacy_mount:{lane}")
        # Workers/relay/beat: no credential.
        for svc in (
            "worker",
            "worker_b23",
            "worker_bayesian",
            "relay_b26_p2",
            "beat",
            "worker_attribution",
        ):
            env = services.get(svc, {})
            if env.get(LEGACY_TOKEN, "").strip() or env.get(FILE_TOKEN, "").strip():
                violations.append(f"xiv_topo_worker_mount:{lane}:{svc}")
        checks[f"lane_{lane}"] = True
    # Procfile parity.
    try:
        procfile = (REPO_ROOT / "Procfile").read_text(encoding="utf-8")
    except OSError as exc:
        violations.append(f"xiv_topo_procfile_unreadable:{exc}")
        return
    for line in procfile.splitlines():
        s = line.strip()
        if s.startswith("web:"):
            if "SKELDIR_PROCESS_ROLE=api" not in s:
                violations.append("xiv_topo_procfile_web_role")
            if RELAY_TOKEN not in s:
                violations.append("xiv_topo_procfile_web_no_relay")
            m = re.search(r"B26_P2_INGRESS_DATABASE_URL=(\S*)", s)
            if m and m.group(1).strip():
                violations.append("xiv_topo_procfile_web_legacy")
            m = re.search(r"B26_P2_INGRESS_DATABASE_URL_FILE=(\S*)", s)
            if m and m.group(1).strip():
                violations.append("xiv_topo_procfile_web_file")
        if s.startswith("auth_ingress:"):
            if "SKELDIR_PROCESS_ROLE=auth_ingress" not in s:
                violations.append("xiv_topo_procfile_root_role")
            if "B26_P2_INGRESS_DATABASE_URL_FILE=" not in s:
                violations.append("xiv_topo_procfile_root_no_file")
    checks["procfile_parity"] = True


def _single_delivery_law(violations: list[str], checks: dict) -> None:
    # The legacy environment string may be referenced ONLY by the
    # refusal/sanitizer boundary (session.py), the relay-test mount
    # steps (workflows), and historical docs. Any backend holder that
    # constructs a pool from it is a second delivery path.
    offenders = []
    # NOTE: LEGACY_TOKEN is a substring of FILE_TOKEN; match the whole
    # token only (not followed by _FILE).
    legacy_use_re = re.compile(r"B26_P2_INGRESS_DATABASE_URL(?!_FILE)")
    for path in sorted((REPO_ROOT / "backend" / "app").rglob("*.py")):
        try:
            body = path.read_text(encoding="utf-8")
        except OSError:
            continue
        rel = str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        if not legacy_use_re.search(body):
            continue
        if rel in ("backend/app/db/session.py",):
            # Boundary file: must refuse/delete, never construct from it.
            if "return legacy or None" in body:
                offenders.append(rel + ":fallback")
            continue
        offenders.append(rel)
    if offenders:
        violations.append("xiv_topo_legacy_beyond_boundary:" + ",".join(offenders[:8]))
    else:
        checks["single_delivery_law"] = True
    # Workflows: no lane may export the legacy string to a runtime process.
    for wf in sorted((REPO_ROOT / ".github" / "workflows").glob("*.yml")):
        try:
            body = wf.read_text(encoding="utf-8")
        except OSError:
            continue
        for i, line in enumerate(body.splitlines(), 1):
            s = line.strip()
            if not s.startswith(LEGACY_TOKEN + ":"):
                continue
            val = s.split(":", 1)[1].strip().strip('"').strip("'")
            if val and val != '""':
                violations.append(f"xiv_topo_workflow_legacy:{wf.name}:{i}")
    checks["workflow_delivery_law"] = True


def main() -> int:
    parser = argparse.ArgumentParser(description="XIV cross-lane topology equivalence.")
    parser.add_argument("--evidence-out", default=None)
    args = parser.parse_args()
    violations: list[str] = []
    checks: dict = {}
    _lane_checks(violations, checks)
    _single_delivery_law(violations, checks)
    status = "PASS" if not violations else "FAIL"
    print(f"B26_P2_XIV_TOPO_{status}")
    if violations:
        print(";".join(sorted(violations)))
    else:
        print(json.dumps({"checks": checks}, sort_keys=True, default=str))
    if args.evidence_out:
        Path(args.evidence_out).parent.mkdir(parents=True, exist_ok=True)
        Path(args.evidence_out).write_text(
            json.dumps(
                {
                    "gate_id": "B26-P2-XIV-TOPOLOGY",
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
