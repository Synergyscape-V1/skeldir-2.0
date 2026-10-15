"""Unit tests for the owner-custodied ledger grant-shape rule.

scripts/security/phase4_enforcement_probe._ledger_owner_custody_grants_ok
must PASS only when no non-owner, non-superuser principal (including
PUBLIC and roles created later) holds any privilege on the ledger, and
must go RED on any grant. Fake connections keep this hermetic: it runs
on every CI lane without a database.
"""

from scripts.security.phase4_enforcement_probe import (
    LEDGER_CUSTODY_COLUMN_PRIVILEGES,
    LEDGER_CUSTODY_PRIVILEGES,
    OWNER_CUSTODIED_LEDGER_TABLES,
    _ledger_owner_custody_grants_ok,
)

TABLE = "b26_p2_verdict_supersession_ledger"
PRIVS = list(LEDGER_CUSTODY_PRIVILEGES)
COLUMNS = ["id", "tenant_id", "seq"]


class _FakeCursor:
    def __init__(self, grants, owner, columns):
        # grants: {(role_or_PUBLIC, priv): bool} for table-level, plus
        # {(role, column, priv): bool} for column-scoped grants.
        self._grants = dict(grants)
        self._owner = owner
        self._columns = list(columns)
        self._last = None

    def execute(self, sql, params=None):
        self._last = (sql, params)

    def fetchone(self):
        sql, params = self._last
        if "pg_get_userbyid(c.relowner)" in sql:
            return (self._owner,)
        if "FROM pg_roles" in sql:
            return None
        if "grantee = 0" in sql:
            return (bool(self._grants.get(("PUBLIC", "ANY"), False)),)
        if "has_column_privilege" in sql:
            role, _qualified, column, priv = (
                params[0],
                params[1],
                params[2],
                params[3],
            )
            return (bool(self._grants.get((role, column, priv), False)),)
        if len(params) == 2:
            _qualified, priv = params[0], params[1]
            role = "PUBLIC"
        else:
            role, _qualified, priv = params[0], params[1], params[2]
        return (bool(self._grants.get((role, priv), False)),)

    def fetchall(self):
        sql, _params = self._last
        if "FROM pg_roles" in sql:
            return list(self._roles)
        if "FROM pg_attribute" in sql:
            return [(c,) for c in self._columns]
        return []

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


class _FakeConn:
    def __init__(self, grants, owner, roles, columns=None):
        self._grants = grants
        self._owner = owner
        self._roles = roles
        self._columns = COLUMNS if columns is None else columns

    def cursor(self):
        cur = _FakeCursor(self._grants, self._owner, self._columns)
        cur._roles = self._roles
        return cur


def _clean_grants(owner, roles):
    return {}, owner, roles


def test_ledger_table_is_governed():
    assert TABLE in OWNER_CUSTODIED_LEDGER_TABLES
    assert set(PRIVS) >= {"SELECT", "INSERT", "UPDATE", "DELETE"}


def test_clean_lane_passes():
    roles = [("migration_owner", False), ("app_user", False), ("app_worker", False)]
    conn = _FakeConn(*_clean_grants("migration_owner", roles))
    assert _ledger_owner_custody_grants_ok(conn, TABLE) == []


def test_select_grant_to_runtime_role_reds():
    roles = [("migration_owner", False), ("app_user", False)]
    conn = _FakeConn({("app_user", "SELECT"): True}, "migration_owner", roles)
    problems = _ledger_owner_custody_grants_ok(conn, TABLE)
    assert len(problems) == 1
    assert "app_user" in problems[0] and "SELECT" in problems[0]


def test_insert_grant_to_public_reds():
    roles = [("migration_owner", False)]
    conn = _FakeConn({("PUBLIC", "ANY"): True}, "migration_owner", roles)
    problems = _ledger_owner_custody_grants_ok(conn, TABLE)
    assert len(problems) == 1
    assert "PUBLIC" in problems[0]


def test_future_role_with_update_reds():
    roles = [("migration_owner", False), ("app_future", False)]
    conn = _FakeConn({("app_future", "UPDATE"): True}, "migration_owner", roles)
    problems = _ledger_owner_custody_grants_ok(conn, TABLE)
    assert len(problems) == 1
    assert "app_future" in problems[0]


def test_owner_and_superuser_exempt():
    roles = [("migration_owner", False), ("postgres", True)]
    grants = {("migration_owner", p): True for p in PRIVS}
    grants.update({("postgres", p): True for p in PRIVS})
    conn = _FakeConn(grants, "migration_owner", roles)
    assert _ledger_owner_custody_grants_ok(conn, TABLE) == []


def test_column_privilege_surface_is_complete():
    assert set(LEDGER_CUSTODY_COLUMN_PRIVILEGES) == {
        "SELECT",
        "INSERT",
        "UPDATE",
        "REFERENCES",
    }


def test_column_select_grant_to_runtime_role_reds():
    # The gap this rule closes: has_table_privilege is blind to
    # column-scoped grants, so a table-clean lane with one column
    # grant must still go RED, naming the column.
    roles = [("migration_owner", False), ("app_user", False)]
    conn = _FakeConn(
        {("app_user", "seq", "SELECT"): True}, "migration_owner", roles
    )
    problems = _ledger_owner_custody_grants_ok(conn, TABLE)
    assert len(problems) == 1
    assert "app_user" in problems[0]
    assert "seq" in problems[0]
    assert "SELECT" in problems[0]


def test_column_update_grant_to_future_role_reds():
    roles = [("migration_owner", False), ("app_future", False)]
    conn = _FakeConn(
        {("app_future", "tenant_id", "UPDATE"): True},
        "migration_owner",
        roles,
    )
    problems = _ledger_owner_custody_grants_ok(conn, TABLE)
    assert len(problems) == 1
    assert "app_future" in problems[0] and "tenant_id" in problems[0]


def test_clean_lane_with_columns_passes():
    roles = [("migration_owner", False), ("app_user", False), ("app_worker", False)]
    conn = _FakeConn(*_clean_grants("migration_owner", roles))
    assert _ledger_owner_custody_grants_ok(conn, TABLE) == []
