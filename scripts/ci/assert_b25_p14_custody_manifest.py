#!/usr/bin/env python3
"""Assert the declared B2.8 credential-custody boundary is the deployed one.

B2.5-P14 Corrective VI, closing H-VI-03 / H-ART-VI-01 / Exit Gate 2.

The entering tree's custody module claimed a credential "only one code path can
reach". An independent audit refuted it in four lines::

    custody_dsn_direct_connect: ALLOWED
        session_user=app_b28_requester caller=__main__

``_assert_permitted_caller`` fences the *helper*. The DSN lives in the process
environment, so the honest boundary is the process, and Corrective VI says so:
``CUSTODY_TRUST_BOUNDARY = "process"``.

A declaration is only worth having if something checks it. Two facts are
checkable without running the deployment, and this script checks both:

**The declaration has not quietly widened.** ``CUSTODY_TRUST_BOUNDARY`` and
``CUSTODY_TRUSTED_SERVICES`` are read from the module, and the retracted claim
must stay retracted -- a docstring that reacquires "only one code path can reach"
turns this red.

**The deployment agrees with the declaration.** Directive VI H-ART-VI-01 says
not to infer credential custody from Python imports but to inspect runtime
composition. ``docker-compose.c19.yml`` is that composition: it names, per
service, which environment variables that container receives. The two B2.8 DSNs
must be delivered to exactly the declared services and to no other -- so a future
change that hands the solver credential to the beat scheduler or a worker is
merge-blocking rather than discovered by an auditor.

Usage::

    python scripts/ci/assert_b25_p14_custody_manifest.py [--evidence-out PATH]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
COMPOSE_PATH = REPO_ROOT / "docker-compose.c19.yml"
CUSTODY_MODULE = REPO_ROOT / "backend/app/simulation/consequence_custody.py"

#: The claim the audit refuted, keyed exactly as the module declares it. The
#: check is against the module's own `CUSTODY_RETRACTED_CLAIMS` mapping rather
#: than against its prose: a docstring may legitimately quote a withdrawn claim
#: while explaining why it was withdrawn, and a checker that could not tell the
#: difference would push the history out of the file.
REQUIRED_RETRACTION = (
    "a credential that only one code path can reach is a credential the rest of"
    " the process cannot spend"
)

#: The environment variables that carry the two causal credentials.
CUSTODY_ENV_VARS = ("B28_REQUEST_DATABASE_URL", "B28_SOLVER_DATABASE_URL")

#: Services that must never receive them. Named explicitly rather than derived
#: as "everything else", so a new service is a deliberate decision: it appears in
#: neither list and the completeness check below fails.
UNTRUSTED_SERVICES = (
    "postgres",
    "worker_attribution",
    "worker_b23_a",
    "worker_b23_b",
    "worker_bayesian",
    "worker_publisher",
    "beat",
    "trust_signer",
)


def _fail(message: str) -> None:
    print(f"[b25-p14-custody] FAIL: {message}")


def _load_declaration() -> dict[str, Any]:
    sys.path[:0] = [str(REPO_ROOT), str(REPO_ROOT / "backend")]
    from app.simulation.consequence_custody import (  # noqa: PLC0415
        B28_REQUEST_DATABASE_URL_ENV,
        B28_SOLVER_DATABASE_URL_ENV,
        CUSTODY_RETRACTED_CLAIMS,
        CUSTODY_TRUST_BOUNDARY,
        CUSTODY_TRUSTED_SERVICES,
    )

    return {
        "trust_boundary": CUSTODY_TRUST_BOUNDARY,
        "trusted_services": list(CUSTODY_TRUSTED_SERVICES),
        "env_vars": [B28_REQUEST_DATABASE_URL_ENV, B28_SOLVER_DATABASE_URL_ENV],
        "retracted_claims": dict(CUSTODY_RETRACTED_CLAIMS),
    }


def _service_environments() -> dict[str, dict[str, Any]]:
    document = yaml.safe_load(COMPOSE_PATH.read_text(encoding="utf-8"))
    services = document.get("services") or {}
    resolved: dict[str, dict[str, Any]] = {}
    for name, definition in services.items():
        environment = (definition or {}).get("environment") or {}
        if isinstance(environment, list):
            # The list form is `NAME=value`; normalize so both forms compare.
            environment = {
                entry.split("=", 1)[0]: entry.split("=", 1)[1] if "=" in entry else ""
                for entry in environment
            }
        resolved[name] = dict(environment)
    return resolved


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--evidence-out", default="")
    args = parser.parse_args()

    failures: list[str] = []
    declaration = _load_declaration()

    if declaration["trust_boundary"] != "process":
        failures.append(
            "declared trust boundary is "
            f"{declaration['trust_boundary']!r}; the measured boundary is 'process'"
            " (an in-process direct connect spends the DSN). Narrowing the"
            " declaration without a physical mechanism is the defect Corrective"
            " VI removed."
        )
    if sorted(declaration["env_vars"]) != sorted(CUSTODY_ENV_VARS):
        failures.append(
            f"custody env vars drifted: {declaration['env_vars']} != "
            f"{list(CUSTODY_ENV_VARS)}"
        )

    retracted = declaration["retracted_claims"]
    if REQUIRED_RETRACTION not in retracted:
        failures.append(
            "the module no longer records that the one-code-path custody claim"
            " was withdrawn; a claim that stops being recorded as refuted is a"
            " claim that can quietly return"
        )
    else:
        demonstration = retracted[REQUIRED_RETRACTION]
        if "custody_dsn_direct_connect: ALLOWED" not in demonstration:
            failures.append(
                "the retraction no longer cites the physical demonstration that"
                " produced it"
            )

    module_text = CUSTODY_MODULE.read_text(encoding="utf-8")
    if "diagnostic, not a control" not in module_text:
        failures.append(
            "the caller fence is no longer documented as a diagnostic; a reader"
            " could mistake it for the boundary again"
        )

    environments = _service_environments()
    trusted = set(declaration["trusted_services"])
    untrusted = set(UNTRUSTED_SERVICES)
    declared_services = trusted | untrusted
    actual_services = set(environments)
    unclassified = actual_services - declared_services
    if unclassified:
        failures.append(
            "compose services carry no custody classification: "
            + ", ".join(sorted(unclassified))
            + " -- add each to CUSTODY_TRUSTED_SERVICES or UNTRUSTED_SERVICES"
        )
    missing = declared_services - actual_services
    if missing:
        failures.append(
            "classified services absent from the compose topology: "
            + ", ".join(sorted(missing))
        )

    delivery: dict[str, list[str]] = {}
    for service, environment in sorted(environments.items()):
        carried = [name for name in CUSTODY_ENV_VARS if name in environment]
        delivery[service] = carried
        if service in trusted and sorted(carried) != sorted(CUSTODY_ENV_VARS):
            failures.append(
                f"trusted service {service!r} does not receive both custody"
                f" DSNs: {carried}"
            )
        if service in untrusted and carried:
            failures.append(
                f"untrusted service {service!r} receives {carried}; the"
                " credential must not cross that container boundary"
            )

    evidence = {
        "declaration": declaration,
        "untrusted_services": sorted(untrusted),
        "custody_delivery": delivery,
        "compose": COMPOSE_PATH.relative_to(REPO_ROOT).as_posix(),
        "failures": failures,
    }
    if args.evidence_out:
        out = Path(args.evidence_out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_text(json.dumps(evidence, indent=2, sort_keys=True), encoding="utf-8")

    for service, carried in delivery.items():
        marker = "TRUSTED" if service in trusted else "untrusted"
        print(f"[b25-p14-custody] {marker:9s} {service:20s} {carried}")
    print(f"[b25-p14-custody] declared_trust_boundary={declaration['trust_boundary']}")

    if failures:
        for failure in failures:
            _fail(failure)
        return 1
    print("[b25-p14] custody manifest PASSED")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
