import pytest

from app.tasks import maintenance as m


def test_validated_matview_identifier_rejects_non_registry():
    with pytest.raises(ValueError):
        m._validated_matview_identifier("not_a_view", task_id="t", tenant_id=None)


def test_validated_matview_identifier_quotes_registry_member():
    ident = m._validated_matview_identifier("mv_allocation_summary", task_id="t", tenant_id=None)
    # IdentifierPreparer may not add quotes for simple lowercase identifiers, but it must round-trip safely.
    assert ident == "mv_allocation_summary"


@pytest.mark.parametrize(
    "bad_name",
    [
        "mv_realtime_revenue;DROP TABLE worker_failed_jobs;--",
        "public.mv_realtime_revenue",
        "mv_realtime_revenue;select 1",
    ],
)
def test_validated_matview_identifier_rejects_injection_candidates(bad_name: str):
    with pytest.raises(ValueError):
        m._validated_matview_identifier(bad_name, task_id="t", tenant_id=None)


def test_qualified_identifier_includes_public_schema():
    qualified = m._qualified_matview_identifier("mv_allocation_summary", task_id="t", tenant_id=None)
    assert qualified.startswith("public.")
    assert qualified.endswith("mv_allocation_summary")
