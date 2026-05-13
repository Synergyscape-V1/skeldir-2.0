# B2.4 Persistence Readiness Audit

M2 does not implement B2.4 Bayesian modeling.

The readiness audit checks for the canonical `bayesian_model_fits` persistence substrate and validates whether it can store tenant authority, model type/version, status, start/completion timestamps, runtime/timeout data, convergence diagnostics, abort/fallback state, and tenant/status lookup indexes.

Current M2 guard outcome:

`M2_BLOCKED_BY_UNCONFIRMED_B24_PERSISTENCE_SUBSTRATE`

This means B2.4 implementation remains blocked unless a later schema remediation explicitly creates and validates `bayesian_model_fits` or a canonical successor table. M2 enforces that PyMC, PyMC-Marketing, ArviZ, sampling code, and convergence-diagnostic implementation do not enter runtime/test implementation paths before this substrate is resolved.
