#!/usr/bin/env python3
"""Apply one reviewable B2.6-P2 on-disk controlled defect."""

from __future__ import annotations

import argparse
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
SCOPE_MODULE = ROOT / "backend/app/finance_reconciliation/scope_authority.py"
SCOPE_CONTRACT = ROOT / "contracts/reconciliation/b2.6/scope-policy.v1.yaml"
SINK_MODULE = ROOT / "backend/app/finance_reconciliation/canonical_sink.py"
PROBE_ALIAS = ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_alias.py"
PROBE_SQL = ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_sql.py"
PROBE_SERIALIZER = ROOT / "backend/app/finance_reconciliation/_p2_nc_probe_serializer.py"


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
        "RAIL_CASE_SQL = \"\"\"\n"
        "SELECT CASE provider\n"
        "  WHEN 'stripe' THEN 'stripe'\n"
        "  WHEN 'shopify' THEN 'shopify'\n"
        "  WHEN 'paypal' THEN 'paypal'\n"
        "  WHEN 'woocommerce' THEN 'woocommerce'\n"
        "  ELSE 'stripe' END AS rail\n"
        '\"\"\"  # NC-P2-SQL-CASE\n'
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
        "        provider_token in (_CANONICAL_PROVIDERS | {\"square\"})\n"
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
        'def _parse_tenant(tenant_id: Any) -> UUID:\n',
        'def _parse_tenant(tenant_id: Any) -> UUID:  # set_config probe\n',
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
        'def validate_window(\n',
        '# NC-P2-REVERSE-WRITE UPDATE probe\n'
        'def validate_window(\n',
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
        "scope_policy_version: b2.6-p2-scope-policy-v1\n",
        "scope_policy_version: b2.6-p2-scope-policy-v2\n",
        defect="p2_scope_policy_version_drift",
    )


def p2_live_wiring_removal() -> None:
    _replace_once(
        SINK_MODULE,
        "            _p2_scope.assert_aggregate_scope_supported(\n",
        "            _p2_scope.assert_aggregate_scope_supported_DISABLED(\n",
        defect="p2_live_wiring_removal",
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
