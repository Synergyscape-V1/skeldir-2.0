"""RLS/GUC positive and negative controls for M4 diagnostics."""

from __future__ import annotations

from common import connect, emit, read_fixture_state


def main() -> None:
    state = read_fixture_state()
    tenant_id = state["tenant_id"]
    dlq_task_id = state["dlq_task_id"]

    with connect() as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            cur.execute("RESET app.current_tenant_id")
            cur.execute("SELECT current_setting('app.current_tenant_id', true) AS tenant_context")
            missing_context = cur.fetchone()["tenant_context"]
            cur.execute(
                "SELECT COUNT(*) AS visible_rows FROM public.worker_failed_jobs WHERE task_id = %s",
                (dlq_task_id,),
            )
            missing_visible = int(cur.fetchone()["visible_rows"])

            cur.execute(
                "SELECT set_config('app.current_tenant_id', %s, false) AS tenant_context",
                (tenant_id,),
            )
            positive_context = cur.fetchone()["tenant_context"]
            cur.execute(
                """
                SELECT COUNT(*) AS visible_rows
                FROM public.worker_failed_jobs
                WHERE task_id = %s
                  AND tenant_id = %s
                """,
                (dlq_task_id, tenant_id),
            )
            positive_visible = int(cur.fetchone()["visible_rows"])

    status = (
        "ok"
        if positive_context == tenant_id and positive_visible == 1 and missing_visible == 0
        else "failed"
    )
    emit(
        {
            "status": status,
            "positive_control": {
                "fixture": "m4-rls-positive",
                "tenant_context": positive_context,
                "visible_seeded_dlq_rows": positive_visible,
            },
            "negative_control": {
                "fixture": "m4-rls-missing-context",
                "tenant_context": missing_context,
                "visible_seeded_dlq_rows": missing_visible,
                "interpretation": "zero rows under missing context is fail-visible only because the command reports current_setting beside the row count",
            },
        }
    )
    if status != "ok":
        raise SystemExit(1)


if __name__ == "__main__":
    main()
