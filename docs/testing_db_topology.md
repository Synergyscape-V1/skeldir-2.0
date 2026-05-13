# Test Database Topology

M2 has three database profiles.

| Profile | URL | Purpose | External allowed |
| --- | --- | --- | --- |
| Local direct Postgres | `TEST_DIRECT_DATABASE_URL` | migrations, DB invariants, B2.3 representative tests | no |
| Local transaction pooler | `TEST_POOLED_DATABASE_URL` | RLS/GUC transaction-boundary and pooler reset proof | no |
| External smoke | `EXTERNAL_DATABASE_URL` | optional compatibility check | only with `SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true` |

`docker-compose.local.yml` remains the M1 canonical local runtime. `docker-compose.test.yml` adds PgBouncer in transaction pooling mode for M2 pooler tests.

Alembic uses direct local Postgres only. Pooler URLs are prohibited for migrations.
