#!/bin/bash
# Phase 1 Validation Script
# Validates: Alembic setup, no hardcoded credentials, baseline migration, templates

set -e

echo "Validating Phase 1: Migration System Initialization..."

# Check 1: No hardcoded credentials in alembic.ini
if grep -riE "password|secret|token|key" alembic.ini alembic/env.py 2>/dev/null | grep -vE "^#|DATABASE_URL|placeholder|os.environ|os.getenv"; then
    echo "FAIL: Hardcoded credentials found in Alembic config"
    exit 1
fi
echo "✓ No hardcoded credentials in Alembic config"

# Check 2: Environment parameterization
if ! grep -qE "DATABASE_URL|os.environ|os.getenv" alembic/env.py; then
    echo "FAIL: alembic/env.py does not use environment variables"
    exit 1
fi
echo "✓ Environment parameterization confirmed"

# Check 3: Baseline migration exists
BASELINE_MIGRATION=$(find alembic/versions -name "*baseline.py" | head -1)
if [ -z "$BASELINE_MIGRATION" ]; then
    echo "FAIL: Baseline migration not found"
    exit 1
fi
echo "✓ Baseline migration exists: $BASELINE_MIGRATION"

# Check 4: Baseline migration has required fields
if ! grep -qE "revision.*=|down_revision|def upgrade|def downgrade" "$BASELINE_MIGRATION"; then
    echo "FAIL: Baseline migration missing required Alembic fields"
    exit 1
fi
echo "✓ Baseline migration has required fields"

# Check 5: Migration templates exist
if [ ! -f "db/migrations/templates/versioned_migration.py.template" ]; then
    echo "FAIL: Versioned migration template not found"
    exit 1
fi
if [ ! -f "db/migrations/templates/repeatable_migration.py.template" ]; then
    echo "FAIL: Repeatable migration template not found"
    exit 1
fi
echo "✓ Migration templates exist"

# Check 6: Templates contain required fields
if ! grep -qE "revision|down_revision|upgrade|downgrade" db/migrations/templates/versioned_migration.py.template; then
    echo "FAIL: Versioned template missing required fields"
    exit 1
fi
if ! grep -qE "revision|down_revision|upgrade|downgrade" db/migrations/templates/repeatable_migration.py.template; then
    echo "FAIL: Repeatable template missing required fields"
    exit 1
fi
echo "✓ Templates contain required fields"

# Check 7: Migration system documentation exists
if [ ! -f "db/docs/MIGRATION_SYSTEM.md" ]; then
    echo "FAIL: Migration system documentation not found"
    exit 1
fi
echo "✓ Migration system documentation exists"

# Note: Alembic functionality tests (alembic --help, alembic check, etc.) require
# Python environment and database connection. These are deferred to manual testing.

echo "Phase 1: PASS (static checks complete, runtime tests deferred)"





