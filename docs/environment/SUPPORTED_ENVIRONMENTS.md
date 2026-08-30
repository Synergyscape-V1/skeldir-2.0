# Supported Environments and Topology Contracts

B2.5-P13 Corrective XV, H-XV-08 / H-XV-09 / RC-XV-08.

This document exists because the repository previously stated *how* to bootstrap
without stating *where* that bootstrap is supported, or which invariants each
topology is meant to satisfy. Two auditors reached different conclusions from
the same repository, and both were reasonable, because the contract was
unwritten.

Governing rule, from the corrective directive:

> `PASS-INFRASTRUCTURE` does not waive `PASS-LOCAL-REPRODUCIBILITY`.

CI proving a topology says nothing about whether a developer can reproduce it.
Those are separate claims and are recorded separately below.

## Supported environments

| Host | Shell | Status | Notes |
|---|---|---|---|
| Linux x86-64 | bash | **Supported** | Reference environment. Matches CI. |
| macOS (Intel / Apple Silicon) | bash / zsh | **Supported** | Docker Desktop required for the Compose topology. |
| Windows 10/11 | Git Bash (MSYS2) | **Supported** | See the Windows constraints below. `.gitattributes` guarantees LF checkout for shell scripts. |
| Windows 10/11 | WSL2 | **Supported** | Behaves as Linux. |
| Windows 10/11 | PowerShell | **Supported for `.ps1` helpers only** | The canonical bootstrap is a bash script; run it from Git Bash or WSL2. |

### Windows: what was broken and is now fixed

Git for Windows ships `core.autocrlf=true` in its **system** config. Until
Corrective XV the repository declared no line-ending policy, so a fresh clone on
a stock Windows host rewrote every LF shell script to CRLF and the documented
bootstrap failed on its second line:

```text
scripts/ci/run_m1_onboarding_bootstrap.sh: line 1:
set: pipefail: invalid option name        (exit 2)
```

`.gitattributes` now pins `*.sh` (and `Makefile`, `Procfile`, `Dockerfile*`) to
`eol=lf` regardless of the operator's `core.autocrlf`, while `*.ps1`/`*.bat`
keep CRLF for their native interpreters. This is enforced by
`scripts/ci/validate_b25_p13_c15_closure.py`.

Two pre-existing Windows constraints remain, and are constraints rather than
defects — see `REPRODUCIBLE_GREENFIELD.md` §5 for detail:

* `uvloop` has no Windows wheel, so `backend/requirements-lock.txt` cannot be
  installed natively. Use the Compose topology or `requirements-dev.txt`.
* GNU Make is not present by default. Install it, use WSL2, or invoke the
  underlying `docker compose` commands directly.

## Not supported

These are stated explicitly so documentation does not imply compatibility the
repository does not provide:

* **Native Windows Python for the full dependency lock.** `uvloop` refuses to
  build. This is upstream, not a Skeldir defect.
* **PostgreSQL 16 or later.** Every migration replay and CI job pins
  PostgreSQL 15. A 16 data directory will not start under a 15 binary.
* **`cmd.exe` as the bootstrap shell.** The canonical bootstrap is bash.
* **Python other than 3.11.** CI pins 3.11; other minors are untested.
* **Running the M0/M1 scope-lock validators locally as authoritative.** They
  diff `M0_BASELINE_SHA` to local `HEAD` and sweep in every commit since the
  baseline, producing false violations. CI is authoritative for those two gates.

## Topology contracts

Four surfaces exist. Each satisfies a different set of invariants, and the
distinction is load-bearing: claiming local reproducibility for components a
documented path cannot start is exactly the failure this table prevents.

| Surface | Entry point | Services it actually starts | Invariants it is intended to satisfy |
|---|---|---|---|
| **Minimal local developer** | `bash scripts/ci/run_m1_onboarding_bootstrap.sh` | `postgres`, `migrate`, `api`, `worker`, `smoke`, `validator` (`docker-compose.local.yml`) | Service boot, migration replay to head, API readiness, M1 runtime smoke |
| **Local trust suite (bare database)** | `REPRODUCIBLE_GREENFIELD.md` §3 manual path | `postgres` only, with the six least-privilege roles | Full `backend/tests/trust` suite, migration/role/RLS checks, C13/C14/C15 closure validators |
| **Local forensic E2E** | `docker-compose.e2e.yml` | Adds `mock_platform`, `worker_bayesian` (`SKELDIR_CELERY_WORKER_ROLE=bayesian`), publisher identity, RS256 key material | The deepest P13 behavioural gates: C6/C7/C9/C10/C11/C12 live worker physics |
| **CI production-equivalent** | `.github/workflows/b2_5-p13-e2e-trust-closure.yml` | GitHub-hosted `postgres:15-alpine` plus the full role topology via `.github/actions/setup-postgres-ci` | The merge-governing `B2.5-P13 E2E Trust Closure` aggregate |

**The minimal local developer surface does not start the Bayesian worker or the
publisher.** That is deliberate, not a gap: those identities need
credential-separated roles that the local Compose file does not provision. An
auditor who expects the full production topology from `docker-compose.local.yml`
will correctly find it absent, and that is the documented boundary rather than a
defect. Use the forensic E2E surface for the worker-physics gates.

## Which gates run where

Unchanged from `REPRODUCIBLE_GREENFIELD.md` §7, restated here so the support
contract is readable in one place:

* **Local, no extra credentials:** B0.4 / B0.6 phase gates; B2.1–B2.4
  validators; the full `backend/tests/trust` suite; `validate_b25_p13_c13_closure`,
  `_c14_closure` and `_c15_closure` including `--negative-control`; migration,
  role and RLS checks; backend import.
* **Requires pushed-branch CI:** B0.1 / B0.2 / B0.3 (need `oasdiff` and Prism
  mocks); B1.1–B1.7 (need AWS OIDC); `ci.yml` and
  `b2_5-p13-e2e-trust-closure.yml`; M0 / M1 scope locks.

## Verified reproduction record

| Claim | Evidence class | Last verified |
|---|---|---|
| Shell scripts check out LF under `core.autocrlf=true` | `PASS-LOCAL-REPRODUCIBILITY` | 2026-08-29, Corrective XV |
| Documented bootstrap parses and executes its preamble under bash 5.2 | `PASS-LOCAL-REPRODUCIBILITY` | 2026-08-29, Corrective XV |
| PostgreSQL 15 + six least-privilege roles + `alembic upgrade head` | `PASS-INFRASTRUCTURE` | 2026-08-29, Corrective XV |
| Full `backend/tests/trust` suite from a clean worktree | `PASS-LOCAL-REPRODUCIBILITY` | 2026-08-29, Corrective XV |
| P13 E2E composition journey against live PostgreSQL | `PASS-SEMANTIC-FALSIFICATION` | 2026-08-29, Corrective XV |

See `docs/environment/INFRASTRUCTURE_EVIDENCE_CAPSULES.md` for the capsule
ledger and the invalidation rules that govern reusing any of the above.
