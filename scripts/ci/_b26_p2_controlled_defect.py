#!/usr/bin/env python3
"""Apply one reviewable B2.6-P2 on-disk controlled defect."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPE_MODULE = ROOT / "backend/app/finance_reconciliation/scope_authority.py"
CONDUCTION_MODULE = ROOT / "backend/app/finance_reconciliation/candidate_conduction.py"
DISPATCH_MODULE = ROOT / "backend/app/finance_reconciliation/dispatch_authority.py"
TENANT_MODULE = ROOT / "backend/app/finance_reconciliation/tenant_authority.py"
SCOPE_CONTRACT = ROOT / "contracts/reconciliation/b2.6/scope-policy.v2.yaml"
SCOPE_CONTRACT_V1 = ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
DAY_WINDOW_MODULE = ROOT / "backend/app/core/day_window.py"
RELAY_MODULE = ROOT / "backend/app/tasks/b26_p2_relay.py"
SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
WEBHOOK_MODULE = ROOT / "backend/app/api/webhooks.py"
B23_TASK_MODULE = ROOT / "backend/app/tasks/revenue_verification.py"
PROBE_ALIAS = ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_alias.py"
PROBE_SQL = ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_sql.py"
PROBE_SERIALIZER = (
    ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_serializer.py"
)


def _replace_once(path: Path, old: str, new: str, *, defect: str) -> None:
    text = path.read_text(encoding="utf-8")
    if text.count(old) != 1:
        raise SystemExit(f"{defect}:anchor_count={text.count(old)}")
    path.write_text(text.replace(old, new, 1), encoding="utf-8")


def p2_second_alias_dict() -> None:
    PROBE_ALIAS.write_text(
        '"""P2 negative-control probe: second alias authority (same primitive)."""\n'
        "\n"
        "RAIL_ALIASES = {\n"
        '    "stripe": "stripe",\n'
        '    "shopify": "shopify",\n'
        '    "square": "stripe",\n'
        '    "paypal": "paypal",\n'
        '    "woocommerce": "woocommerce",\n'
        "}\n"
        "\n"
        "\n"
        "def normalize_provider_alias(raw):\n"
        "    return RAIL_ALIASES[str(raw).strip().lower()]\n",
        encoding="utf-8",
    )


def p2_sql_case_normalizer() -> None:
    PROBE_SQL.write_text(
        '"""P2 negative-control probe: SQL CASE normalizer (alternate primitive)."""\n'
        "\n"
        'RAIL_CASE_SQL = """\n'
        "SELECT CASE provider\n"
        "  WHEN 'stripe' THEN 'stripe'\n"
        "  WHEN 'shopify' THEN 'shopify'\n"
        "  WHEN 'paypal' THEN 'paypal'\n"
        "  WHEN 'woocommerce' THEN 'woocommerce'\n"
        "  ELSE 'stripe' END AS rail\n"
        '"""  # NC-P2-SQL-CASE\n'
        "\n"
        "\n"
        "def fetch_rail_scope(conn, provider):\n"
        "    return conn.execute(RAIL_CASE_SQL, {'provider': provider})\n",
        encoding="utf-8",
    )


def p2_serializer_reinterpretation() -> None:
    PROBE_SERIALIZER.write_text(
        '"""P2 negative-control probe: serializer rail labels (out-of-vocabulary)."""\n'
        "\n"
        "RAIL_LABELS = {\n"
        '    "stripe": "stripe",\n'
        '    "shopify": "shopify",\n'
        '    "paypal": "paypal",\n'
        '    "woocommerce": "woocommerce",\n'
        "}\n"
        "\n"
        "\n"
        "def rail_label(value):\n"
        '    """Map one raw rail token without using normalization vocabulary."""\n'
        "    return RAIL_LABELS[str(value).strip().lower()]\n",
        encoding="utf-8",
    )


def p2_unsupported_promotion() -> None:
    _replace_once(
        SCOPE_MODULE,
        "    provider_supported = (\n"
        "        provider_token in _CANONICAL_PROVIDERS\n"
        "        and provider_token in _sovereign_provider_universe()\n"
        "    )\n",
        "    provider_supported = (\n"
        '        provider_token in (_CANONICAL_PROVIDERS | {"square"})\n'
        "    )\n",
        defect="p2_unsupported_promotion",
    )


def p2_currency_silent_promotion() -> None:
    _replace_once(
        SCOPE_MODULE,
        "    currency_supported = currency_token in _sovereign_currency_universe()\n",
        "    currency_supported = True  # NC-P2-CURRENCY-PROMOTION\n",
        defect="p2_currency_silent_promotion",
    )


def p2_window_closed_end() -> None:
    _replace_once(
        SCOPE_MODULE,
        "    if not (start <= occurred < end):\n",
        "    if not (start <= occurred <= end):  # NC-P2-CLOSED-END\n",
        defect="p2_window_closed_end",
    )


def p2_tenant_guc_bypass() -> None:
    _replace_once(
        SCOPE_MODULE,
        "def _parse_tenant(tenant_id: Any) -> UUID:\n",
        "def _parse_tenant(tenant_id: Any) -> UUID:  # set_config probe\n",
        defect="p2_tenant_guc_bypass",
    )


def p2_nondeterministic_identity() -> None:
    _replace_once(
        SCOPE_MODULE,
        "    has_reference = isinstance(source_reference, str) and bool(\n",
        "    from uuid import uuid4 as _nc_uuid4  # NC-P2-NONDETERMINISM\n"
        "    _nc_marker = _nc_uuid4()  # noqa: F841\n"
        "    has_reference = isinstance(source_reference, str) and bool(\n",
        defect="p2_nondeterministic_identity",
    )


def p2_reverse_write() -> None:
    _replace_once(
        SCOPE_MODULE,
        "def validate_window(\n",
        "# NC-P2-REVERSE-WRITE UPDATE probe\n" "def validate_window(\n",
        defect="p2_reverse_write",
    )


def p2_contract_universe_widening() -> None:
    _replace_once(
        SCOPE_CONTRACT,
        "canonical_providers:\n  - paypal\n  - shopify\n  - stripe\n  - woocommerce\n",
        "canonical_providers:\n  - paypal\n  - shopify\n  - stripe\n  - woocommerce\n  - square\n",
        defect="p2_contract_universe_widening",
    )


def p2_scope_policy_version_drift() -> None:
    _replace_once(
        SCOPE_CONTRACT,
        "scope_policy_version: b2.6-p2-scope-policy-v2\n",
        "scope_policy_version: b2.6-p2-scope-policy-v3\n",
        defect="p2_scope_policy_version_drift",
    )


def p2_live_wiring_removal() -> None:
    _replace_once(
        SINK_MODULE,
        "            _p2_scope.assert_aggregate_scope_supported(\n",
        "            _p2_scope.assert_aggregate_scope_supported_DISABLED(\n",
        defect="p2_live_wiring_removal",
    )


def p2_sink_conduction_removal() -> None:
    _replace_once(
        SINK_MODULE,
        "            _p2_scope_result = await _p2_conduction.derive_governed_scope(\n",
        "            _p2_scope_result = await _p2_conduction.derive_governed_scope_DISABLED(\n",
        defect="p2_sink_conduction_removal",
    )


def p2_webhook_phase_violation() -> None:
    text = WEBHOOK_MODULE.read_text(encoding="utf-8")
    marker = "logger = logging.getLogger(__name__)\n"
    if text.count(marker) != 1:
        raise SystemExit("p2_webhook_phase_violation:anchor_count!=1")
    text = text.replace(
        marker,
        marker + "from app.finance_reconciliation import (\n"
        "    candidate_conduction as _p2_nc_phase_probe,  # NC-P2-PHASE-VIOLATION\n"
        ")\n",
        1,
    )
    WEBHOOK_MODULE.write_text(text, encoding="utf-8")


def p2_b23_task_conduction_removal() -> None:
    _replace_once(
        B23_TASK_MODULE,
        "        _derive_p2_scope_for_window(\n",
        "        _derive_p2_scope_for_window_DISABLED(\n",
        defect="p2_b23_task_conduction_removal",
    )


def p2_conduction_prefilter() -> None:
    _replace_once(
        CONDUCTION_MODULE,
        '                    " ORDER BY event_timestamp ASC, id ASC"\n',
        '                    " AND provider IN :supported_platforms"\n'
        '                    " ORDER BY event_timestamp ASC, id ASC"\n',
        defect="p2_conduction_prefilter",
    )


def p2_refusal_law_removal() -> None:
    _replace_once(
        SCOPE_CONTRACT,
        "refusal_representation: exception_fail_closed_never_returned_disposition\n",
        "refusal_representation: returned_object\n",
        defect="p2_refusal_law_removal",
    )


def p2_dispatch_binding_removal() -> None:
    _replace_once(
        B23_TASK_MODULE,
        "        authority = await _p2_dispatch.resolve_dispatch_authority(\n",
        "        authority = await _p2_dispatch.resolve_dispatch_authority_DISABLED(\n",
        defect="p2_dispatch_binding_removal",
    )


def p2_snapshot_isolation_removal() -> None:
    _replace_once(
        TENANT_MODULE,
        'text("SET TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY")',
        'text("SET TRANSACTION ISOLATION LEVEL READ COMMITTED READ ONLY")',
        defect="p2_snapshot_isolation_removal",
    )


def p2_identity_digest_removal() -> None:
    _replace_once(
        CONDUCTION_MODULE,
        "p2_conduction_identity_not_conserved",
        "p2_conduction_identity_removed",
        defect="p2_identity_digest_removal",
    )


def p2_rls_inspection_removal() -> None:
    _replace_once(
        CONDUCTION_MODULE,
        "FROM pg_policies",
        "FROM pg_missing",
        defect="p2_rls_inspection_removal",
    )


def p2_money_semantics_removal() -> None:
    _replace_once(
        SCOPE_CONTRACT,
        "money_semantics: source_verified_gross_not_canonical_net\n",
        "money_semantics: canonical_net_revenue\n",
        defect="p2_money_semantics_removal",
    )


def p2_dead_edge_if_false() -> None:
    _replace_once(
        B23_TASK_MODULE,
        "    p2_scope = run_in_worker_loop(\n",
        "    p2_scope = None  # NC-P2-DEAD-EDGE name-preserving severance\n"
        "    if False:\n"
        "        p2_scope = run_in_worker_loop(\n",
        defect="p2_dead_edge_if_false",
    )


def p2_silent_null_swallow() -> None:
    _replace_once(
        B23_TASK_MODULE,
        "    p2_scope = run_in_worker_loop(\n",
        "    p2_scope: Dict[str, Any] | None = None\n"
        "    p2_scope = run_in_worker_loop(\n",
        defect="p2_silent_null_swallow",
    )


def p2_window_delegation_removal() -> None:
    _replace_once(
        WEBHOOK_MODULE,
        "    from app.core.day_window import (  # noqa: PLC0415\n",
        "    from app.core.day_window_DISABLED import (  # noqa: PLC0415\n",
        defect="p2_window_delegation_removal",
    )


def p2_window_12h_mutation() -> None:
    _replace_once(
        DAY_WINDOW_MODULE,
        "    start = occurred.replace(hour=0, minute=0, second=0, microsecond=0)\n"
        "    return start, start + timedelta(days=1)",
        "    start = occurred.replace(hour=0, minute=0, second=0, microsecond=0)\n"
        "    if occurred.hour >= 12:\n"
        "        start = start.replace(hour=12)  # NC-P2-12H\n"
        "    return start, start + timedelta(hours=12)",
        defect="p2_window_12h_mutation",
    )


def p2_window_local_mutation() -> None:
    _replace_once(
        DAY_WINDOW_MODULE,
        "    if event_time.tzinfo is None or event_time.tzinfo.utcoffset(event_time) is None:\n"
        "        occurred = event_time.replace(tzinfo=timezone.utc)\n"
        "    else:\n"
        "        occurred = event_time.astimezone(timezone.utc)",
        "    if event_time.tzinfo is None or event_time.tzinfo.utcoffset(event_time) is None:\n"
        "        occurred = event_time.replace(tzinfo=timezone.utc)\n"
        "    else:\n"
        "        occurred = event_time  # NC-P2-LOCAL no UTC normalize\n",
        defect="p2_window_local_mutation",
    )


def p2_window_inclusive_mutation() -> None:
    _replace_once(
        SCOPE_MODULE,
        "    if not (start <= occurred < end):\n",
        "    if not (start <= occurred <= end):  # NC-P2-INCLUSIVE\n",
        defect="p2_window_inclusive_mutation",
    )


def p2_identity_provider_blindness() -> None:
    _replace_once(
        CONDUCTION_MODULE,
        '        f"{item.ingress_id}:{item.classification.provider}:"',
        '        f"{item.ingress_id}:constant_provider:"  # NC-P2-PROVIDER-BLIND\n',
        defect="p2_identity_provider_blindness",
    )


def p2_outbox_removal() -> None:
    _replace_once(
        WEBHOOK_MODULE,
        "                INSERT INTO public.b26_p2_execution_outbox (",
        "                INSERT INTO public.b26_p2_execution_outbox_DISABLED (  # NC-P2-OUTBOX\n",
        defect="p2_outbox_removal",
    )


def p2_admission_after_b23() -> None:
    _replace_once(
        B23_TASK_MODULE,
        "    authority = run_in_worker_loop(_admit())\n"
        "    result = run_in_worker_loop(\n"
        "        execute_b23_batch_match_engine(",
        "    result = run_in_worker_loop(\n"
        "        execute_b23_batch_match_engine(  # NC-P2-ADMISSION-AFTER\n",
        defect="p2_admission_after_b23",
    )


def p2_relay_deployment_removal() -> None:
    text = (ROOT / "Procfile").read_text(encoding="utf-8")
    marker = "relay_b26_p2:"
    if text.count(marker) != 1:
        raise SystemExit("p2_relay_deployment_removal:anchor_count!=1")
    (ROOT / "Procfile").write_text(
        text.replace(marker, "relay_b26_p2_DISABLED:", 1), encoding="utf-8"
    )


def p2_rls_singleton_violation() -> None:
    _replace_once(
        CONDUCTION_MODULE,
        '    if len(policy_rows) != 1:\n'
        '        raise ScopeConductionError(\n'
        '            f"p2_rls_completeness_refused:policy_singleton_violated:{len(policy_rows)}"\n'
        "        )",
        '    if len(policy_rows) < 1:  # NC-P2-RLS-SINGLETON allows second policy\n'
        '        raise ScopeConductionError(\n'
        '            f"p2_rls_completeness_refused:policy_singleton_violated:{len(policy_rows)}"\n'
        "        )",
        defect="p2_rls_singleton_violation",
    )


APPLIERS = {
    "p2_second_alias_dict": p2_second_alias_dict,
    "p2_sql_case_normalizer": p2_sql_case_normalizer,
    "p2_serializer_reinterpretation": p2_serializer_reinterpretation,
    "p2_unsupported_promotion": p2_unsupported_promotion,
    "p2_currency_silent_promotion": p2_currency_silent_promotion,
    "p2_window_closed_end": p2_window_closed_end,
    "p2_tenant_guc_bypass": p2_tenant_guc_bypass,
    "p2_nondeterministic_identity": p2_nondeterministic_identity,
    "p2_reverse_write": p2_reverse_write,
    "p2_contract_universe_widening": p2_contract_universe_widening,
    "p2_scope_policy_version_drift": p2_scope_policy_version_drift,
    "p2_live_wiring_removal": p2_live_wiring_removal,
    "p2_sink_conduction_removal": p2_sink_conduction_removal,
    "p2_webhook_phase_violation": p2_webhook_phase_violation,
    "p2_b23_task_conduction_removal": p2_b23_task_conduction_removal,
    "p2_conduction_prefilter": p2_conduction_prefilter,
    "p2_refusal_law_removal": p2_refusal_law_removal,
    "p2_dispatch_binding_removal": p2_dispatch_binding_removal,
    "p2_snapshot_isolation_removal": p2_snapshot_isolation_removal,
    "p2_identity_digest_removal": p2_identity_digest_removal,
    "p2_rls_inspection_removal": p2_rls_inspection_removal,
    "p2_money_semantics_removal": p2_money_semantics_removal,
    "p2_dead_edge_if_false": p2_dead_edge_if_false,
    "p2_silent_null_swallow": p2_silent_null_swallow,
    "p2_window_delegation_removal": p2_window_delegation_removal,
    "p2_window_12h_mutation": p2_window_12h_mutation,
    "p2_window_local_mutation": p2_window_local_mutation,
    "p2_window_inclusive_mutation": p2_window_inclusive_mutation,
    "p2_identity_provider_blindness": p2_identity_provider_blindness,
    "p2_outbox_removal": p2_outbox_removal,
    "p2_admission_after_b23": p2_admission_after_b23,
    "p2_relay_deployment_removal": p2_relay_deployment_removal,
    "p2_rls_singleton_violation": p2_rls_singleton_violation,
}


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("name", choices=sorted(APPLIERS))
    args = parser.parse_args()
    APPLIERS[args.name]()
    print(f"applied:{args.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
