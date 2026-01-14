from __future__ import annotations

from app.matviews import registry


def test_matview_refresh_sql_invariant():
    for entry in registry.all_entries():
        assert entry.refresh_fn is None
        assert entry.refresh_sql is not None
        normalized = entry.refresh_sql.strip().upper()
        assert normalized.startswith("REFRESH MATERIALIZED VIEW")
        for keyword in ("INSERT ", "UPDATE ", "DELETE ", "MERGE "):
            assert keyword not in normalized
from __future__ import annotations

from app.matviews import registry


def test_matview_refresh_sql_invariant():
    for entry in registry.all_entries():
        assert entry.refresh_fn is None
        assert entry.refresh_sql is not None
        normalized = entry.refresh_sql.strip().upper()
        assert normalized.startswith("REFRESH MATERIALIZED VIEW")
        for keyword in ("INSERT ", "UPDATE ", "DELETE ", "MERGE "):
            assert keyword not in normalized
