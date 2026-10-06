"""B2.6-P2 Corrective XIX explicit-family mint helper (harness only).

H-XIX-R7: the sovereign transition requires an explicit authenticated
family claim plus its evidence source; provider-default inference is
refused. Harness callers (tests, seeders, proof scripts) that mint
lawful fixtures through ``b26_p2_authenticate_ingress_atomic`` or
``b26_p2_attest_provenance_evidence`` must therefore set the two
transaction/session GUCs before invoking the transition. This module
is the single governed place that maps a provider to its lawful claim;
callers never hand-write family strings.

Production code sets the same GUCs from ``derive_event_family`` /
``derive_event_family_source`` over verified bytes; this helper is
strictly for fixtures whose bytes are test-controlled.
"""

from __future__ import annotations

from typing import Mapping

XIX_FAMILY_CLAIM_BY_PROVIDER: Mapping[str, tuple[str, str]] = {
    "stripe": ("payment_intent.succeeded", "body-signal:type"),
    "shopify": ("orders.create", "transport-topic:x-shopify-topic"),
    "paypal": ("payment.sale.completed", "body-signal:event_type"),
    "woocommerce": ("order.completed", "body-signal:status"),
}


def xix_family_claim(provider: str) -> tuple[str, str] | None:
    """Lawful (family, source) claim for a provider, or None if unsupported."""
    return XIX_FAMILY_CLAIM_BY_PROVIDER.get((provider or "").strip().lower())


def apply_xix_family_gucs_psycopg2(cur, provider: str) -> bool:
    """Set session-scoped family GUCs on a psycopg2 cursor.

    Returns True when a claim was set, False for unsupported providers
    (the transition will then refuse, which is the lawful outcome for
    distractor fixtures).
    """
    claim = xix_family_claim(provider)
    if claim is None:
        return False
    family, source = claim
    cur.execute(
        "SELECT set_config('app.b26_p2_event_family', %s, false)",
        (family,),
    )
    cur.execute(
        "SELECT set_config('app.b26_p2_event_family_source', %s, false)",
        (source,),
    )
    return True


async def apply_xix_family_gucs_sqlalchemy(conn, provider: str) -> bool:
    """Set session-scoped family GUCs over a SQLAlchemy connection/session."""
    from sqlalchemy import text  # noqa: PLC0415

    claim = xix_family_claim(provider)
    if claim is None:
        return False
    family, source = claim
    await conn.execute(
        text("SELECT set_config('app.b26_p2_event_family', :family, false)"),
        {"family": family},
    )
    await conn.execute(
        text(
            "SELECT set_config('app.b26_p2_event_family_source',"
            " :source, false)"
        ),
        {"source": source},
    )
    return True
