# Celery Test Modes

M2 separates task logic from worker topology.

| Marker | Meaning | Claim |
| --- | --- | --- |
| `celery_eager` | task function executes in-process/eager | logic proof only |
| `celery_worker` | broker/result backend topology is local Postgres and real worker proof is run by M1/M2 runtime harness | worker/broker proof |

`make test-celery-eager` must not be used as evidence that workers boot, queues bind, retries persist, or result backend writes succeed.

`make test-celery-worker` and `make test-broker-topology` use local Postgres-backed Celery URLs. Alternate broker infrastructure, external brokers, and hidden warm broker state are prohibited in default tests.
