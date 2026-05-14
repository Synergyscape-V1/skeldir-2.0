"""Remove local-only M4 diagnostic fixtures for the current run scope."""

from __future__ import annotations

from common import FIXTURE_STATE_PATH, connect, emit, read_fixture_state, set_tenant


TABLE_ORDER = (
    "b23_revenue_events",
    "b23_exception_records",
    "b23_match_task_dispatches",
    "b23_match_verdicts",
    "webhook_ingress_identities",
    "worker_failed_jobs",
    "attribution_events",
    "tenants",
)


def main() -> None:
    state = read_fixture_state()
    tenant_id = state["tenant_id"]
    deleted: dict[str, int] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            set_tenant(cur, tenant_id)
            for table in TABLE_ORDER:
                cur.execute(
                    f"DELETE FROM public.{table} WHERE tenant_id = %s"
                    if table != "tenants"
                    else "DELETE FROM public.tenants WHERE id = %s",
                    (tenant_id,),
                )
                deleted[table] = int(cur.rowcount)
    FIXTURE_STATE_PATH.unlink(missing_ok=True)
    emit(
        {
            "status": "cleared",
            "fixture_class": "local_fixture_only",
            "tenant_id": tenant_id,
            "deleted": deleted,
        }
    )


if __name__ == "__main__":
    main()
