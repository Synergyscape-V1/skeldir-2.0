# Celery Test Modes

M2 separates task logic from worker topology.

| Marker | Meaning | Claim |
| --- | --- | --- |
| `celery_eager` | task function executes in-process/eager | logic proof only |
| `celery_worker` | broker/result backend topology is local Postgres and real worker proof is run by M1/M2 runtime harness | worker/broker proof |
| `celery_worker_concurrent` | real threaded worker with concurrency greater than one | no tenant ContextVar/session/GUC leakage under concurrent tasks |
| `pooler_worker_concurrent` | real threaded worker whose DB sessions use the transaction pooler | no stale pooled GUC reuse across tenants |

`make test-celery-eager` must not be used as evidence that workers boot, queues bind, retries persist, or result backend writes succeed.

`make test-celery-worker`, `make test-celery-worker-concurrent`, `make test-pooler-worker-concurrent`, and `make test-broker-topology` use local Postgres-backed Celery broker/result URLs. `make test-broker-topology` also runs a physical broker-absent negative control and real dispatch through a subprocess worker. Alternate broker infrastructure, external brokers, and hidden warm broker state are prohibited in default tests.
