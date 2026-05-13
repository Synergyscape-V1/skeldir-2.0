# Test Database Topology

M2 has three database profiles.

| Profile | URL | Purpose | External allowed |
| --- | --- | --- | --- |
| Local direct Postgres | `TEST_DIRECT_DATABASE_URL` | migrations, DB invariants, B2.3 representative tests | no |
| Local transaction pooler | `TEST_POOLED_DATABASE_URL` | RLS/GUC transaction-boundary and pooler reset proof | no |
| External smoke | `EXTERNAL_DATABASE_URL` | optional compatibility check | only with `SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true` |

`docker-compose.local.yml` remains the M1 canonical local runtime. `docker-compose.test.yml` adds PgBouncer in transaction pooling mode for M2 pooler tests.

Alembic uses direct local Postgres only. Pooler URLs are prohibited for migrations.

Corrective M2 adds `make test-pooler-worker-concurrent`: the broker/result
backend remain direct local Postgres, while worker DB sessions use
`TEST_POOLED_DATABASE_URL`/`DATABASE_URL` through PgBouncer transaction pooling.
`SKELDIR_ASYNCPG_DISABLE_STATEMENT_CACHE=1` is set for this profile so asyncpg
does not use prepared-statement behavior that is invalid under transaction
pooling.
