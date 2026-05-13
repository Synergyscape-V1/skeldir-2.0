# Topology URL Authority Matrix

| Variable | Purpose | Profiles | Pooler allowed | External allowed | Standard CI | Default local tests | Validator rule |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `DATABASE_URL` | application runtime DB | direct local | no | no | yes | yes | local host only |
| `DIRECT_DATABASE_URL` | explicit direct runtime DB | direct local | no | no | yes | yes | local host only |
| `POOLED_DATABASE_URL` | explicit transaction-pooler DB | pooler | yes | no | yes | no | local pooler only |
| `TEST_DATABASE_URL` | default test DB | direct local | no | no | yes | yes | local host only |
| `TEST_DIRECT_DATABASE_URL` | direct test DB | direct local | no | no | yes | yes | local host only |
| `TEST_POOLED_DATABASE_URL` | pooler test DB | pooler | yes | no | yes | no | local pooler only |
| `ALEMBIC_DATABASE_URL` | migration DB | direct local | no | no | yes | yes | local host only |
| `MIGRATION_DATABASE_URL` | migration DB | direct local | no | no | yes | yes | local host only |
| `EXTERNAL_DATABASE_URL` | optional external smoke DB | external smoke | yes | opt-in only | no | no | requires `SKELDIR_ALLOW_EXTERNAL_DB_TESTS=true` |
| `CELERY_BROKER_URL` | Celery broker | local Postgres | no | no | yes | yes | `sqla+postgresql://` local only |
| `CELERY_RESULT_BACKEND` | Celery results | local Postgres | no | no | yes | yes | `db+postgresql://` local only |

Enforcement lives in `scripts/testing/assert_topology_urls.py` and `scripts/ci/validate_m2_test_feedback_loop.py`.

Neon and other external Postgres hosts are permitted only in explicit external-smoke jobs. They are never inferred by default tests.
