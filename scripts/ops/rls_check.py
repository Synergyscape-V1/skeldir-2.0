"""RLS/GUC positive and negative controls for M4 diagnostics."""

from __future__ import annotations

from common import connect_runtime, emit, read_fixture_state


def _visible_fixture_rows(cur, task_ids: tuple[str, str]) -> list[dict]:
    cur.execute(
        """
        SELECT task_id, tenant_id::text AS tenant_id
        FROM public.worker_failed_jobs
        WHERE task_id IN (%s, %s)
        ORDER BY task_id
        """,
        task_ids,
    )
    return [dict(row) for row in cur.fetchall()]


def main() -> None:
    state = read_fixture_state()
    tenant_id = state["tenant_id"]
    peer_tenant_id = state["rls_peer_tenant_id"]
    dlq_task_id = state["dlq_task_id"]
    peer_dlq_task_id = state["rls_peer_dlq_task_id"]
    task_ids = (dlq_task_id, peer_dlq_task_id)

    with connect_runtime() as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute(
                """
                SELECT
                  current_user AS role_name,
                  r.rolsuper AS role_is_superuser,
                  r.rolbypassrls AS role_bypasses_rls,
                  c.relrowsecurity AS table_rls_enabled,
                  c.relforcerowsecurity AS table_force_rls,
                  pg_get_userbyid(c.relowner) AS table_owner
                FROM pg_class c
                JOIN pg_namespace n ON n.oid = c.relnamespace
                JOIN pg_roles r ON r.rolname = current_user
                WHERE n.nspname = 'public'
                  AND c.relname = 'worker_failed_jobs'
                """
            )
            boundary = dict(cur.fetchone())

            cur.execute("RESET app.current_tenant_id")
            cur.execute("SELECT current_setting('app.current_tenant_id', true) AS tenant_context")
            missing_context = cur.fetchone()["tenant_context"]
            missing_rows = _visible_fixture_rows(cur, task_ids)

            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false) AS tenant_context",
                (tenant_id,),
            )
            positive_context = cur.fetchone()["tenant_context"]
            tenant_a_rows = _visible_fixture_rows(cur, task_ids)

            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false) AS tenant_context",
                (peer_tenant_id,),
            )
            peer_context = cur.fetchone()["tenant_context"]
            tenant_b_rows = _visible_fixture_rows(cur, task_ids)

    role_uses_rls = (
        boundary["table_rls_enabled"]
        and not boundary["role_is_superuser"]
        and not boundary["role_bypasses_rls"]
        and (boundary["role_name"] != boundary["table_owner"] or boundary["table_force_rls"])
    )
    tenant_a_ok = tenant_a_rows == [{"task_id": dlq_task_id, "tenant_id": tenant_id}]
    tenant_b_ok = tenant_b_rows == [{"task_id": peer_dlq_task_id, "tenant_id": peer_tenant_id}]
    missing_ok = missing_rows == []
    status = "ok" if role_uses_rls and tenant_a_ok and tenant_b_ok and missing_ok else "failed"

    proof_query_shape = (
        "SELECT task_id, tenant_id FROM public.worker_failed_jobs "
        "WHERE task_id IN (<tenant_a_task>, <tenant_b_task>); no tenant_id predicate"
    )
    emit(
        {
            "status": status,
            "database_boundary": boundary,
            "guc_binding_proof": {
                "tenant_a_context": positive_context,
                "tenant_b_context": peer_context,
                "missing_context": missing_context,
            },
            "physical_rls_enforcement_proof": {
                "fixture": "m4-rls-bare-select-isolation",
                "query_shape": proof_query_shape,
                "tenant_a_visible_rows": tenant_a_rows,
                "tenant_b_visible_rows": tenant_b_rows,
                "missing_context_visible_rows": missing_rows,
                "role_uses_rls": role_uses_rls,
            },
            "positive_control": {
                "fixture": "m4-rls-positive",
                "tenant_context": positive_context,
                "visible_seeded_dlq_rows": len(tenant_a_rows),
            },
            "negative_control": {
                "fixture": "m4-rls-missing-context",
                "tenant_context": missing_context,
                "visible_seeded_dlq_rows": len(missing_rows),
                "interpretation": "zero rows are accepted only because this bare SELECT runs under an RLS-applicable role and reports current_setting beside the row count",
            },
        }
    )
    if status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
