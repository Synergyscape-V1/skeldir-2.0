# B2.4 Dependency Decision Record

## Decision

Recommended default for B2.4 implementation:

- Sampling: PyMC.
- Diagnostics: ArviZ.
- Marketing model helpers: PyMC-Marketing deferred until a concrete model specification needs it.

M5 installs nothing. M5 does not clone, fork, vendor, or pin new statistical dependencies.

## Candidate Stack

| Package | Role | M5 decision |
|---|---|---|
| PyMC | Probabilistic model construction and sampling. | Preferred sampler for B2.4 implementation. |
| ArviZ | R-hat, ESS, divergence, HDI, posterior summary diagnostics. | Required diagnostics package when implementation begins. |
| PyMC-Marketing | Higher-level marketing mix/attribution helpers. | Deferred; use only if P2/P3 model spec proves value beyond raw PyMC. |
| NumPy/Pandas/SciPy | Data preparation and numeric support. | Existing support libraries may be used according to current dependency governance. |

## Installation and Pinning Plan

Dependencies enter only when B2.4 implementation starts after M5/M6/M7 authorization.

Required mechanics:

- Declare dependencies in the canonical backend dependency file and lockfile used by CI.
- Pin compatible PyMC, PyTensor, ArviZ, NumPy, and Python versions.
- Record lockfile update in the B2.4 dependency PR.
- Add import/runtime smoke tests in the isolated B2.4 lane, not by expanding unrelated CI workflows.
- Do not install dependencies from GitHub URLs unless a fork exception is approved.

## PyMC-Marketing Decision

PyMC-Marketing is not required for initial B2.4 substrate. It may be introduced only if the approved model spec needs maintained upstream marketing abstractions and those abstractions preserve deterministic source truth and artifact requirements.

## Fork and Vendor Policy

Default: no fork, no clone, no vendoring.

A fork requires all of:

- Concrete upstream bug or missing feature blocking B2.4.
- Minimal patch scope documented.
- Security and license review.
- Replacement/removal plan.
- Lockfile and provenance evidence.

Manual local clones are not acceptable dependency management.

## Compatibility Risks

Windows/local:

- PyMC/PyTensor binary compatibility and compiler availability can differ from Linux CI.
- Local Windows dev may require documented Python version and wheel availability.
- M5 avoids installing to keep maintainability stabilization deterministic.

Linux/CI:

- CI must run Python 3.11 or later if required by selected PyMC/PyTensor versions.
- Sampling tests must be bounded and non-flaky; heavy MCMC belongs in dedicated/nightly lanes unless merge-blocking proof is minimal and deterministic enough.
- Dependency cache must not hide missing lockfile changes.

## Authorization Point

Installation is authorized only in B2.4 P3 after:

- M5 design validator is green.
- M6 LLM boundary decision is closed.
- M7 authorizes B2.4 entry.
- P1 persistence migration design is accepted.
- P2 source snapshot and eligibility behavior are implemented or stubbed behind deterministic tests.

## Why M5 Installs Nothing

M5 is a design lock. Installing PyMC, PyMC-Marketing, or ArviZ during M5 would blur design governance with implementation, make local proof harder to reproduce, and risk reintroducing dependency uncertainty before the persistence and fallback contracts are frozen.
