"""Read-only B2.3 causal trace diagnostic."""

from __future__ import annotations

import argparse

from common import connect, emit, read_fixture_state, set_tenant


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--reference", default=None)
    parser.add_argument("--unknown-control", action="store_true")
    args = parser.parse_args()

    state = read_fixture_state()
    tenant_id = state["tenant_id"]
    reference = args.reference or state["stripe_payment_intent_id"].replace("pi_m4replay", "pi_m4diag")
    if args.unknown_control:
        reference = "m4-b23-unknown-control"

    with connect() as conn:
        conn.set_session(readonly=True, autocommit=True)
        with conn.cursor() as cur:
            set_tenant(cur, tenant_id)
            cur.execute(
                """
                SELECT
                  wi.id AS webhook_ingress_identity_id,
                  wi.event_id AS attribution_event_id,
                  wi.provider,
                  wi.provider_native_event_reference,
                  wi.provider_native_commerce_reference,
                  wi.normalized_commerce_reference_value,
                  wi.verified_commerce_ingress_state,
                  d.task_id,
                  d.task_name,
                  d.queue,
                  d.routing_key,
                  d.status AS dispatch_status,
                  v.id AS match_verdict_id,
                  v.status AS verdict_status,
                  v.match_quality,
                  v.verified_amount_minor,
                  v.attributed_amount_minor,
                  v.last_transition_at
                FROM public.webhook_ingress_identities wi
                LEFT JOIN public.b23_match_task_dispatches d
                  ON d.webhook_ingress_identity_id = wi.id
                 AND d.tenant_id = wi.tenant_id
                LEFT JOIN public.b23_match_verdicts v
                  ON v.webhook_ingress_identity_id = wi.id
                 AND v.tenant_id = wi.tenant_id
                WHERE wi.tenant_id = %s
                  AND (
                    wi.normalized_commerce_reference_value = %s
                    OR wi.provider_native_event_reference = %s
                    OR d.task_id = %s
                  )
                ORDER BY wi.created_at DESC
                LIMIT 1
                """,
                (tenant_id, reference, reference, reference),
            )
            row = cur.fetchone()

    if row is None:
        emit(
            {
                "status": "not_found",
                "diagnostic": "no linked task/verdict found",
                "reference": reference,
                "tenant_id": tenant_id,
            }
        )
        return
    emit(
        {
            "status": "found",
            "fixture": "m4-b23-trace-positive",
            "causal_spine": [
                "webhook_ingress_identities",
                "b23_match_task_dispatches",
                "app.tasks.revenue_verification.execute_b23_batch_match_engine",
                "b23_match_verdicts",
            ],
            "row": dict(row),
        }
    )


if __name__ == "__main__":
    main()
