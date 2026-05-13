# B2.4 Persistence Entry Gate

M2 does not implement B2.4 Bayesian modeling.

The canonical entry gate is `b24_persistence_entry_gate`. It allows a future
B2.4-P0 schema-substrate remediation to add or validate the persistence table,
but it blocks Bayesian execution, model fitting, Bayesian runtime dependency
use, and convergence-diagnostic runtime behavior until that substrate exists.

The gate checks for `bayesian_model_fits` or a documented canonical successor
table with tenant authority, model type/version, status, started/completed
timestamps, runtime/timeout fields, convergence diagnostics, abort/fallback
fields, and tenant/status lookup indexes.

Current M2 guard outcome:

`M2_BLOCKED_BY_UNCONFIRMED_B24_PERSISTENCE_SUBSTRATE`

This is an intentional entry-gate block, not permission to implement B2.4
feature semantics inside M2.
