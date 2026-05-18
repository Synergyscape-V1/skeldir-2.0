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
    tenant_ids = [state["tenant_id"]]
    if state.get("rls_peer_tenant_id"):
        tenant_ids.append(state["rls_peer_tenant_id"])
    deleted: dict[str, int] = {}
    with connect() as conn:
        with conn.cursor() as cur:
            for tenant_id in tenant_ids:
                set_tenant(cur, tenant_id)
                for table in TABLE_ORDER:
                    if table == "tenants":
                        continue
                    cur.execute(f"DELETE FROM public.{table} WHERE tenant_id = %s", (tenant_id,))
                    deleted[table] = deleted.get(table, 0) + int(cur.rowcount)

            cur.execute("DELETE FROM public.tenants WHERE id = ANY(%s::uuid[])", (tenant_ids,))
            deleted["tenants"] = int(cur.rowcount)
    FIXTURE_STATE_PATH.unlink(missing_ok=True)
    emit(
        {
            "status": "cleared",
            "fixture_class": "local_fixture_only",
            "tenant_ids": tenant_ids,
            "deleted": deleted,
        }
    )


if __name__ == "__main__":
    main()
