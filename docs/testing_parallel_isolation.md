# M2 Serial/Parallel Isolation Authority

M2 CI is serial-only until per-worker disposable DB/schema isolation is added.

The serial-only guard is explicit:

- `SKELDIR_TEST_PARALLEL_MODE=serial-only`
- `SKELDIR_TEST_RUN_ID=m2-<run>`
- `PYTEST_XDIST_WORKER` must be absent or `master`
- `make test-parallel-isolation` fails if xdist-style workers execute the M2
  proof loop without a per-worker isolation implementation

Run-scoped namespaces are mandatory even in serial mode. M2 runtime tests derive
temporary queue names, probe tables, tenant IDs, and idempotency/test markers
from `SKELDIR_TEST_RUN_ID` plus random UUID suffixes. Append-only-sensitive tests
must remain repeatable without deleting or truncating protected truth tables.

Future parallel enablement must replace this guard with per-worker
database/schema/container isolation keyed by `PYTEST_XDIST_WORKER`.
