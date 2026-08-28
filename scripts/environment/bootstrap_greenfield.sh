#!/usr/bin/env bash
# Idempotent greenfield bootstrap. See docs/environment/REPRODUCIBLE_GREENFIELD.md
# Safe to re-run. Exits non-zero if any verification fails.
set -euo pipefail

CONTAINER="${SKELDIR_DEV_PG_CONTAINER:-skeldir-dev-pg}"
PGPORT="${SKELDIR_DEV_PG_PORT:-55432}"
DBNAME="${SKELDIR_DEV_DB:-skeldir_dev}"
IMAGE="postgres:15-alpine"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
# Windows Python cannot read Git Bash /c/... paths; emit a native path when on MSYS.
if command -v cygpath >/dev/null 2>&1; then
  REPO_ROOT_NATIVE="$(cygpath -m "$REPO_ROOT")"
else
  REPO_ROOT_NATIVE="$REPO_ROOT"
fi
DK() { MSYS_NO_PATHCONV=1 docker "$@"; }
say() { printf '\n== %s ==\n' "$1"; }
fail() { printf 'FAIL: %s\n' "$1" >&2; exit 1; }

say "1/5 postgres ($IMAGE on 127.0.0.1:$PGPORT)"
if DK ps -a --format '{{.Names}}' | grep -qx "$CONTAINER"; then
  DK start "$CONTAINER" >/dev/null 2>&1 || true
  echo "reusing existing container $CONTAINER"
else
  DK run -d --name "$CONTAINER" \
    -e POSTGRES_PASSWORD=postgres -e POSTGRES_DB=postgres \
    -p "127.0.0.1:${PGPORT}:5432" "$IMAGE" >/dev/null
  echo "created container $CONTAINER"
fi
for _ in $(seq 1 60); do
  DK exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 && break
  sleep 1
done
DK exec "$CONTAINER" pg_isready -U postgres >/dev/null 2>&1 || fail "postgres did not become ready"

say "2/5 authority boundary (MUST precede migration)"
python "$REPO_ROOT/scripts/database/prepare_migration_authority_boundary.py" \
  --admin-dsn "postgresql://postgres:postgres@127.0.0.1:${PGPORT}/postgres" \
  --database-name "$DBNAME" | tail -8

say "3/5 alembic upgrade head (from repo root)"
cd "$REPO_ROOT"
DATABASE_URL="postgresql://migration_owner:migration_owner@127.0.0.1:${PGPORT}/${DBNAME}" \
MIGRATION_DATABASE_URL="postgresql://migration_owner:migration_owner@127.0.0.1:${PGPORT}/${DBNAME}" \
python -m alembic upgrade head 2>&1 | tail -3

say "4/5 verification"
HEAD_REV=$(DK exec "$CONTAINER" psql -U postgres -d "$DBNAME" -Atc \
  "SELECT version_num FROM alembic_version" 2>/dev/null | tr -d '\r')
[ -n "$HEAD_REV" ] || fail "no alembic_version row"
echo "alembic head: $HEAD_REV"

BADROLE=$(DK exec "$CONTAINER" psql -U postgres -d "$DBNAME" -Atc \
  "SELECT count(*) FROM pg_roles WHERE rolname IN
   ('app_user','app_worker','app_dispatch_publisher','migration_owner','app_rw','app_ro')
   AND (rolsuper OR rolbypassrls)" 2>/dev/null | tr -d '\r')
[ "$BADROLE" = "0" ] || fail "a runtime role holds superuser or BYPASSRLS"
NROLE=$(DK exec "$CONTAINER" psql -U postgres -d "$DBNAME" -Atc \
  "SELECT count(*) FROM pg_roles WHERE rolname IN
   ('app_user','app_worker','app_dispatch_publisher','migration_owner','app_rw','app_ro')" \
   2>/dev/null | tr -d '\r')
[ "$NROLE" = "6" ] || fail "expected 6 runtime roles, found ${NROLE}"
echo "roles: 6 present, none superuser, none BYPASSRLS"

NORLS=$(DK exec "$CONTAINER" psql -U postgres -d "$DBNAME" -Atc \
  "SELECT count(*) FROM pg_class WHERE relname IN
   ('b23_match_verdicts','bayesian_model_fits','bayesian_artifacts')
   AND NOT (relrowsecurity AND relforcerowsecurity)" 2>/dev/null | tr -d '\r')
[ "$NORLS" = "0" ] || fail "RLS/FORCE RLS missing on a tenant-scoped table"
echo "RLS + FORCE RLS: intact on all tenant-scoped tables"

say "5/5 ready"
cat <<EOF
export DATABASE_URL="postgresql://app_user:app_user@127.0.0.1:${PGPORT}/${DBNAME}"
export MIGRATION_DATABASE_URL="postgresql://migration_owner:migration_owner@127.0.0.1:${PGPORT}/${DBNAME}"
export PYTHONPATH="${REPO_ROOT_NATIVE};${REPO_ROOT_NATIVE}/backend"

Next: python -m pytest backend/tests/trust -q     # expect 314 passed, 73 skipped
EOF
