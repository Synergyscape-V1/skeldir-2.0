"""Read-only worker_failed_jobs inspection for M4 runbooks."""

from __future__ import annotations

import argparse

from common import connect, emit, read_fixture_state, set_tenant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--task-id", default=None)
    parser.add_argument("--missing-control", action="store_true")
    args = parser.parse_args()

    state = read_fixture_state()
    tenant_id = state["tenant_id"]
    task_id = args.task_id or state["dlq_task_id"]
    if args.missing_control:
        task_id = "m4-dlq-missing-control"

    with connect() as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            set_tenant(cur, tenant_id)
            cur.execute(
                """
                SELECT
                  task_id,
                  task_name,
                  queue,
                  tenant_id,
                  error_type,
                  exception_class,
                  left(error_message, 180) AS error_message,
                  retry_count,
                  status,
                  correlation_id,
                  failed_at
                FROM public.worker_failed_jobs
                WHERE task_id = %s
                ORDER BY failed_at DESC
                LIMIT 1
                """,
                (task_id,),
            )
            row = cur.fetchone()

    if row is None:
        emit(
            {
                "status": "not_found",
                "diagnostic": "no worker_failed_jobs row matched task_id under the seeded tenant context",
                "task_id": task_id,
                "tenant_id": tenant_id,
            }
        )
        return
    emit({"status": "found", "fixture": "m4-dlq-positive", "row": dict(row)})


if __name__ == "__main__":
    main()
