"""B2.6-P1 Corrective-XI consequence proof battery.

Defect classes XI-A (transform semantic drift), XI-B (canonical authority
capability escape), and XI-C (validate-A/return-B divergence). The two
governing properties:

PROPERTY 1 -- EXECUTABLE EXTERNAL SEMANTIC CONTRACT: every external value
equals the execution of its frozen transform over its declared sovereign
source attribute (``external_semantics.EXTERNAL_SEMANTICS``), pinned by the
semantic contract (AST identity), by value-blind lineage data, and by the
absolute-value cells below on physical B2.3 fixtures.

PROPERTY 2 -- GOVERNED CANONICAL EGRESS CAPABILITY: canonical external
authority is a sealed exact type (``CanonicalExternalTruth``) issued only
inside the governed egress module; admission accepts only that type, so
reproducing the lawful bytes -- by ANY construction primitive -- is
ordinary data and never authority.

Cells P-XI-1..P-XI-14. Every expectation below is hard-coded evidence
data, never derived from the modules under proof.
"""

from __future__ import annotations

import ast
import inspect
import json
import re
from datetime import datetime, timedelta, timezone
from decimal import Decimal
from types import MappingProxyType
from typing import Any
from uuid import UUID

import pytest

from app.finance_reconciliation.authoritative_fields import (
    EXTERNAL_FIELD_RENDER_ATTRS,
    EXTERNAL_FIELD_SOURCES,
    GOVERNED_EXTERNAL_KEYS,
    assert_external_keys_derive_from_registry,
    validate_external_rendering,
)
from app.finance_reconciliation.canonical_sink import (
    CANONICAL_OUTPUT_AUTHORITY,
    GOVERNED_EGRESS_SURFACES,
    CanonicalExternalTruth,
    CanonicalSinkError,
    admit_canonical_external,
    assert_canonical_external_semantics,
    render_governed_external,
)
from app.finance_reconciliation.external_semantics import (
    EXTERNAL_SEMANTICS,
    EXTERNAL_SEMANTIC_KEYS,
    ExternalSemanticsError,
    external_semantics_ast_sha256,
    project_external_fields,
)
from app.finance_reconciliation.semantic_contract import (
    B26_P1_CONTRACT_VERSION,
    load_b26_p1_semantic_contract,
)
from test_b26_p1_corrective_v_consequence import (
    _auth_token,
    _execute,
    _scope,
    _seed_ratio_tenant,
)

PINNED_EXTERNAL_KEYS = frozenset(
    {
        "authority",
        "sink_id",
        "contract_version",
        "tenant_id_hash",
        "currency_code",
        "window_start",
        "window_end",
        "supported_platforms",
        "matched_minor",
        "connected_minor",
        "coverage_percent",
        "zero_denominator",
        "provenance_mode",
        "sovereign_producer",
    }
)

# Independent, value-blind lineage data: the external key -> sovereign
# source attribute map, pinned here as evidence (a wrong source carrying an
# equal value cannot pass a data pin that compares identity, not values).
PINNED_SOURCE_ATTRS = {
    "authority": "authority",
    "sink_id": "sink_id",
    "contract_version": "contract_version",
    "tenant_id_hash": "tenant_id_hash",
    "currency_code": "currency_code",
    "window_start": "window_start",
    "window_end": "window_end",
    "supported_platforms": "supported_platforms",
    "matched_minor": "matched_minor",
    "connected_minor": "connected_minor",
    "coverage_percent": "coverage_percent",
    "zero_denominator": "zero_denominator",
    "provenance_mode": "provenance_mode",
    "sovereign_producer": "sovereign_producer",
}

# The full-instant external window law (timezone mandatory).
FULL_INSTANT = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$")

LAWFUL_EXTERNAL = {
    "authority": "canonical_B2.6_financial_truth",
    "sink_id": "future_finance_projection",
    "contract_version": B26_P1_CONTRACT_VERSION,
    "tenant_id_hash": "sha256:" + "ab" * 32,
    "currency_code": "USD",
    "window_start": "2026-01-01T00:00:00+00:00",
    "window_end": "2026-02-01T12:30:05+02:00",
    "supported_platforms": ("paypal", "stripe"),
    "matched_minor": 76000,
    "connected_minor": 80000,
    "coverage_percent": "95.00",
    "zero_denominator": False,
    "provenance_mode": "RE_DERIVE_ON_READ",
    "sovereign_producer": (
        "app.revenue_verification.verification_coverage."
        "fetch_verification_coverage_aggregate"
        "+app.revenue_verification.verification_coverage."
        "VERIFICATION_COVERAGE.compute"
    ),
}


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


# ---------------------------------------------------------------------------
# P-XI-1 -- transform-contract unity and frozen-contract pin (unit).
# ---------------------------------------------------------------------------


def test_pxi1_transform_contract_unity_and_pin() -> None:
    assert set(EXTERNAL_SEMANTICS) == set(PINNED_EXTERNAL_KEYS)
    assert set(EXTERNAL_SEMANTIC_KEYS) == set(PINNED_EXTERNAL_KEYS)
    assert set(GOVERNED_EXTERNAL_KEYS) == set(PINNED_EXTERNAL_KEYS)
    assert_external_keys_derive_from_registry()
    for key, attr in PINNED_SOURCE_ATTRS.items():
        assert EXTERNAL_SEMANTICS[key].source_attr == attr
        assert EXTERNAL_FIELD_RENDER_ATTRS[key] == attr
        assert EXTERNAL_FIELD_SOURCES[key]["render_attr"] == attr
    contract = load_b26_p1_semantic_contract()
    section = contract["external_semantics_authority"]
    assert section["module"] == "app.finance_reconciliation.external_semantics"
    assert section["ast_sha256"] == external_semantics_ast_sha256()
    assert set(section["governed_external_keys"]) == set(PINNED_EXTERNAL_KEYS)
    assert set(GOVERNED_EGRESS_SURFACES) == {"render_governed_external"}
    assert B26_P1_CONTRACT_VERSION == "b2.6-p1-semantic-authority-v6"
    assert contract["supersession"]["supersedes"] == "b2.6-p1-semantic-authority-v5"


# ---------------------------------------------------------------------------
# P-XI-2 -- executable semantic law: lawful mapping passes, corruptions
# refuse (unit; every corruption is a real class-XI-A representative).
# ---------------------------------------------------------------------------


def test_pxi2_executable_law_refuses_semantic_corruption() -> None:
    assert_canonical_external_semantics(dict(LAWFUL_EXTERNAL))
    corruptions = (
        ("window_start", "2026-01-01"),
        ("window_start", "2026-01-01T00:00:00"),
        ("window_end", "2026-02-01"),
        ("matched_minor", "76000"),
        ("matched_minor", 76000.0),
        ("matched_minor", -76000),
        ("matched_minor", True),
        ("connected_minor", -1),
        ("coverage_percent", "95.0"),
        ("coverage_percent", "9.500"),
        ("coverage_percent", 95.00),
        ("supported_platforms", ["paypal", "stripe"]),
        ("supported_platforms", ["paypal", 1]),
        ("supported_platforms", ("paypal", 1)),
        ("supported_platforms", ("",)),
        ("supported_platforms", {"paypal"}),
        ("tenant_id_hash", "ab" * 31),
        ("tenant_id_hash", "ab" * 32),
        ("currency_code", "usd"),
        ("authority", "canonical_B2.6_financial_truth "),
        ("zero_denominator", 0),
        ("zero_denominator", "false"),
        ("provenance_mode", "DURABLE_SOURCE_BINDING"),
        ("sovereign_producer", "app.services.revenue_reconciliation"),
        ("contract_version", "b2.6-p1-semantic-authority-v5"),
        ("sink_id", ""),
    )
    for key, bad in corruptions:
        probe = dict(LAWFUL_EXTERNAL)
        probe[key] = bad
        with pytest.raises(ValueError):
            assert_canonical_external_semantics(probe)


# ---------------------------------------------------------------------------
# P-XI-3 -- transform vectors: execution and refusal, independently pinned
# (unit).
# ---------------------------------------------------------------------------


def test_pxi3_transform_vectors_execution_and_refusal() -> None:
    instant = EXTERNAL_SEMANTICS["window_start"].transform
    assert instant(datetime(2026, 1, 1, tzinfo=timezone.utc)) == (
        "2026-01-01T00:00:00+00:00"
    )
    assert instant(datetime(2026, 1, 15, 12, 30, 5, tzinfo=timezone.utc)) == (
        "2026-01-15T12:30:05+00:00"
    )
    with pytest.raises(ExternalSemanticsError):
        instant(datetime(2026, 1, 1))  # naive: timezone semantics lost
    money = EXTERNAL_SEMANTICS["matched_minor"].transform
    assert money(76000) == 76000
    assert type(money(76000)) is int
    for bad in (True, 76000.0, "76000", -5):
        with pytest.raises(ExternalSemanticsError):
            money(bad)
    platforms = EXTERNAL_SEMANTICS["supported_platforms"].transform
    assert platforms(("paypal", "stripe")) == ("paypal", "stripe")
    assert platforms(()) == ()
    for bad in (["paypal"], "paypal", ("paypal", 1), {"paypal"}):
        with pytest.raises(ExternalSemanticsError):
            platforms(bad)
    percent = EXTERNAL_SEMANTICS["coverage_percent"].transform
    assert percent(Decimal("95.00")) == "95.00"
    assert percent(Decimal("0.00")) == "0.00"
    for bad in (Decimal("95.005"), Decimal("-1.00"), "95.00", 95.00):
        with pytest.raises(ExternalSemanticsError):
            percent(bad)
    boolean = EXTERNAL_SEMANTICS["zero_denominator"].transform
    assert boolean(True) is True and boolean(False) is False
    with pytest.raises(ExternalSemanticsError):
        boolean(1)
    # Projection equivalence: the serializer produces exactly the pinned
    # lawful mapping from the sovereign source shapes.
    from types import SimpleNamespace

    sovereign = SimpleNamespace(
        authority="canonical_B2.6_financial_truth",
        sink_id="future_finance_projection",
        contract_version=B26_P1_CONTRACT_VERSION,
        tenant_id_hash="sha256:" + "ab" * 32,
        currency_code="USD",
        window_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        window_end=datetime(
            2026, 2, 1, 12, 30, 5,
            tzinfo=timezone(timedelta(hours=2)),
        ),
        supported_platforms=("paypal", "stripe"),
        matched_minor=76000,
        connected_minor=80000,
        coverage_percent=Decimal("95.00"),
        zero_denominator=False,
        provenance_mode="RE_DERIVE_ON_READ",
        sovereign_producer=LAWFUL_EXTERNAL["sovereign_producer"],
    )
    assert project_external_fields(sovereign) == LAWFUL_EXTERNAL


# ---------------------------------------------------------------------------
# P-XI-4 -- lawful render emits the absolute governed matrix (DB).
# ---------------------------------------------------------------------------


async def test_pxi4_lawful_render_absolute_matrix() -> None:
    tenant_id = _seed_ratio_tenant(76000, 80000, "xi4")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert type(rendered) is CanonicalExternalTruth
    assert set(rendered.keys()) == set(PINNED_EXTERNAL_KEYS)
    assert rendered["authority"] == "canonical_B2.6_financial_truth"
    assert rendered["sink_id"] == "future_finance_projection"
    assert rendered["contract_version"] == B26_P1_CONTRACT_VERSION
    assert rendered["currency_code"] == "USD"
    # Full governed instant, timezone preserved (the entering G-3 survivor
    # emitted "2026-01-01" here with every governing proof GREEN).
    assert rendered["window_start"] == "2026-01-01T00:00:00+00:00"
    assert rendered["window_end"] == "2026-02-01T00:00:00+00:00"
    assert FULL_INSTANT.match(rendered["window_start"])
    assert FULL_INSTANT.match(rendered["window_end"])
    assert rendered["supported_platforms"] == ("stripe",)
    assert type(rendered["matched_minor"]) is int and rendered["matched_minor"] == 76000
    assert type(rendered["connected_minor"]) is int and rendered["connected_minor"] == 80000
    assert rendered["coverage_percent"] == "95.00"
    assert re.match(r"^\d+\.\d{2}$", rendered["coverage_percent"])
    assert rendered["zero_denominator"] is False
    assert rendered["provenance_mode"] == "RE_DERIVE_ON_READ"
    assert rendered["sovereign_producer"] == LAWFUL_EXTERNAL["sovereign_producer"]
    from app.trust.refusal import tenant_hash

    assert rendered["tenant_id_hash"] == tenant_hash(tenant_id)
    assert re.match(r"^sha256:[0-9a-f]{64}$", rendered["tenant_id_hash"])
    validate_external_rendering(rendered)
    assert admit_canonical_external(rendered) is rendered
    assert "tenant_id" not in rendered
    assert str(tenant_id) not in json.dumps(dict(rendered.items()))


# ---------------------------------------------------------------------------
# P-XI-5 -- lookalike non-authority: byte-identical representations are
# ordinary data and refuse admission (unit).
# ---------------------------------------------------------------------------


def test_pxi5_lookalikes_never_acquire_authority() -> None:
    for lookalike in (
        dict(LAWFUL_EXTERNAL),
        MappingProxyType(dict(LAWFUL_EXTERNAL)),
        type("Lookalike", (dict,), {})(dict(LAWFUL_EXTERNAL)),
        json.loads(json.dumps(dict(LAWFUL_EXTERNAL))),
        {**dict(LAWFUL_EXTERNAL), "verified_revenue_minor": 76000},
        {k: v for k, v in LAWFUL_EXTERNAL.items()},
    ):
        with pytest.raises(CanonicalSinkError):
            admit_canonical_external(lookalike)
    # Subclass forgery refuses: admission is exact-type identity.
    forged = object.__new__(type("Forged", (CanonicalExternalTruth,), {}))
    with pytest.raises(CanonicalSinkError):
        admit_canonical_external(forged)


# ---------------------------------------------------------------------------
# P-XI-6 -- representation sweep: every ordinary emitter shape can produce
# a canonical-LABELLED finance mapping, and none of them is authority
# (unit). Emission is lawful data; admission is the authority boundary.
# ---------------------------------------------------------------------------


def test_pxi6_representation_sweep_emits_but_never_confers() -> None:
    marker = "canonical_B2.6_" + "financial_truth"  # concatenated form
    finance = {"matched_minor": 76000, "connected_minor": 80000}

    def construct_then_return() -> dict[str, Any]:  # J1
        payload = {"authority": marker, **finance}
        return payload

    def dict_call() -> dict[str, Any]:  # J2
        return dict(authority=marker, **finance)

    class WrapperDict(dict):  # J8
        pass

    def wrapper() -> WrapperDict:
        return WrapperDict({"authority": marker, **finance})

    from dataclasses import asdict, dataclass

    from dataclasses import asdict as xg_serialize  # renamed serializer

    @dataclass
    class _Carrier:
        authority: str
        matched_minor: int
        connected_minor: int
        coverage_percent: str

    def serializer_target() -> Any:
        return _Carrier(
            authority=marker, matched_minor=76000, connected_minor=80000,
            coverage_percent="95.00",
        )

    emitters: tuple[tuple[str, Any], ...] = (
        ("construct_then_return", construct_then_return()),
        ("dict_call", dict_call()),
        ("wrapper_dict", wrapper()),
        ("renamed_serializer", xg_serialize(serializer_target())),
        ("lambda", (lambda record: {"authority": marker, **record})(finance)),
        ("json_round_trip", json.loads(json.dumps({"authority": marker, **finance}))),
        ("nested_helper", (lambda: (lambda: {"authority": marker, **finance})())()),
        ("callable_object", (type("E", (), {"__call__": lambda self: {"authority": marker, **finance}})())()),
    )
    for name, emitted in emitters:
        # The representation is trivially producible and carries the label:
        assert emitted["authority"] == "canonical_B2.6_financial_truth", name
        assert "matched_minor" in emitted, name
        # ...and it is ordinary data: no admission path accepts it.
        with pytest.raises(CanonicalSinkError):
            admit_canonical_external(emitted)


# ---------------------------------------------------------------------------
# P-XI-7 -- value-degenerate lineage: when the wrong source carries an equal
# value, identity pins (not values) govern lineage (DB + unit).
# ---------------------------------------------------------------------------


async def test_pxi7_value_degenerate_lineage_pinned_by_identity() -> None:
    tenant_id = _seed_ratio_tenant(80000, 80000, "xi7")  # matched == connected
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert rendered["matched_minor"] == 80000
    assert rendered["connected_minor"] == 80000
    assert rendered["coverage_percent"] == "100.00"
    # The lineage law is value-blind: source identity is pinned as data in
    # the contract, the CI validator, and here -- never derived from values.
    for key, attr in PINNED_SOURCE_ATTRS.items():
        assert EXTERNAL_SEMANTICS[key].source_attr == attr


# ---------------------------------------------------------------------------
# P-XI-8 -- validated == returned, and the capability is immutable (unit).
# ---------------------------------------------------------------------------


def test_pxi8_validated_is_returned_and_immutable() -> None:
    from app.finance_reconciliation.canonical_sink import (
        _EGRESS_ISSUANCE,
        _issue_canonical_external,
    )

    capability = CanonicalExternalTruth(dict(LAWFUL_EXTERNAL), _EGRESS_ISSUANCE)
    assert admit_canonical_external(capability) is capability
    with pytest.raises(TypeError):
        capability["matched_minor"] = 0  # type: ignore[index]
    with pytest.raises(TypeError):
        capability["verified_revenue_minor"] = 1  # type: ignore[index]
    with pytest.raises(ValueError):
        CanonicalExternalTruth(dict(LAWFUL_EXTERNAL), object())  # wrong proof
    with pytest.raises(ValueError):
        CanonicalExternalTruth(
            {**dict(LAWFUL_EXTERNAL), "verified_revenue_minor": 76000},
            _EGRESS_ISSUANCE,
        )  # extra key refused at issuance: validate-A/return-B unrepresentable
    # The issuer is exactly: contract projection then sealed issuance.
    source = inspect.getsource(_issue_canonical_external)
    assert "project_external_fields(output)" in source
    assert "CanonicalExternalTruth(fields, _EGRESS_ISSUANCE)" in source
    assert "return " in source


# ---------------------------------------------------------------------------
# P-XI-9 -- egress registry: closed set, lawful bindings (unit).
# ---------------------------------------------------------------------------


def test_pxi9_egress_registry_closed_set() -> None:
    assert set(GOVERNED_EGRESS_SURFACES) == {"render_governed_external"}
    surface = GOVERNED_EGRESS_SURFACES["render_governed_external"]
    assert surface.callable_path == (
        "app.finance_reconciliation.canonical_sink.render_governed_external"
    )
    assert surface.serializer == (
        "app.finance_reconciliation.external_semantics.project_external_fields"
    )
    assert surface.capability_type == (
        "app.finance_reconciliation.canonical_sink.CanonicalExternalTruth"
    )
    assert surface.admission == (
        "app.finance_reconciliation.canonical_sink.admit_canonical_external"
    )
    assert surface.egress_kind == "FUTURE_ONLY_CANONICAL"
    capability = CanonicalExternalTruth(
        dict(LAWFUL_EXTERNAL),
        _egress_proof(),
    )
    assert capability.issued_by == "render_governed_external"
    assert admit_canonical_external(capability) is capability


def _egress_proof() -> object:
    from app.finance_reconciliation.canonical_sink import _EGRESS_ISSUANCE

    return _EGRESS_ISSUANCE


# ---------------------------------------------------------------------------
# P-XI-10 -- IX/X preservation spots: census refusal and immutable alias
# law still hold (unit + DB).
# ---------------------------------------------------------------------------


def test_pxi10_census_refusal_preserved() -> None:
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(
            {**dict(LAWFUL_EXTERNAL), "settled_revenue_minor": 1}
        )
    missing = dict(LAWFUL_EXTERNAL)
    del missing["matched_minor"]
    with pytest.raises(ValueError, match="canonical_external_required_key_missing"):
        validate_external_rendering(missing)


async def test_pxi10_preservation_spots() -> None:
    from app.finance_reconciliation.authoritative_fields import (
        freeze_platform_scope,
    )
    from app.finance_reconciliation.canonical_sink import (
        SuccessorProvenanceError,
        authorize_successor_persistence,
        deregister_successor_persistence,
        register_successor_persistence,
    )

    # IX: the freeze boundary still normalizes mutable scope to tuples:
    # ordered inputs keep their governed order, unordered inputs sort
    # deterministically.
    assert freeze_platform_scope(["b", "a"]) == ("b", "a")
    assert freeze_platform_scope({"b", "a"}) == ("a", "b")
    assert freeze_platform_scope(("stripe",)) == ("stripe",)
    # Successor persistence remains unauthorized in P1.
    register_successor_persistence(
        registration_id="pxi10_probe",
        provenance_mode="RE_DERIVE_ON_READ",
        required_runtime_proof_ids=("VI-6",),
    )
    try:
        with pytest.raises(SuccessorProvenanceError):
            authorize_successor_persistence("pxi10_probe")
    finally:
        deregister_successor_persistence("pxi10_probe")


# ---------------------------------------------------------------------------
# P-XI-11 -- ontological isolation: adjacent-domain payloads cannot reach
# external fields, and the transform contract is pure (DB + unit).
# ---------------------------------------------------------------------------


async def test_pxi11_adjacent_domains_confined() -> None:
    from app.finance_reconciliation.canonical_sink import (
        SINK_REGISTRY,
        _SINK_IMPLEMENTATIONS,
        _implementation_hash,
    )
    from app.finance_reconciliation.canonical_sink import (
        SinkRegistration as _SinkRegistration,
    )

    async def _llm_adjunct(context: Any) -> dict[str, Any]:
        return {
            "llm_summary": "seventy-six thousand",
            "b2_4_estimate": "94.00",
            "b2_13_counterfactual": "5000",
        }

    sink_id = "future_finance_projection"
    pristine_registration = SINK_REGISTRY[sink_id]
    pristine_implementation = _SINK_IMPLEMENTATIONS[sink_id]
    evil_registration = _SinkRegistration(
        sink_id=sink_id,
        implementation=f"{_llm_adjunct.__module__}.{_llm_adjunct.__qualname__}",
        implementation_hash=_implementation_hash(_llm_adjunct),
        contract_version=pristine_registration.contract_version,
        output_contract=pristine_registration.output_contract,
        sovereign_source=pristine_registration.sovereign_source,
        tenant_authority_mode=pristine_registration.tenant_authority_mode,
        database_capability_mode=pristine_registration.database_capability_mode,
        provenance_mode=pristine_registration.provenance_mode,
        projection_policy=pristine_registration.projection_policy,
        version="v9.9-xi11-probe",
        required_runtime_proof_ids=pristine_registration.required_runtime_proof_ids,
    )
    tenant_id = _seed_ratio_tenant(76000, 80000, "xi11")
    SINK_REGISTRY[sink_id] = evil_registration
    _SINK_IMPLEMENTATIONS[sink_id] = _llm_adjunct
    try:
        poisoned = await render_governed_external(
            sink_id, auth_token=_auth_token(tenant_id), **_scope()
        )
    finally:
        SINK_REGISTRY[sink_id] = pristine_registration
        _SINK_IMPLEMENTATIONS[sink_id] = pristine_implementation
    assert poisoned["matched_minor"] == 76000
    assert poisoned["coverage_percent"] == "95.00"
    assert set(poisoned.keys()) == set(PINNED_EXTERNAL_KEYS)


def test_pxi11_transform_contract_is_pure() -> None:
    import app.finance_reconciliation.external_semantics as semantics_module

    source = inspect.getsource(semantics_module)
    tree = ast.parse(source)
    imported = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
    assert imported <= {"__future__", "ast", "hashlib", "re", "dataclasses", "datetime", "decimal", "pathlib", "types", "typing"}
    assert "os.environ" not in source
    assert "__import__" not in source
    assert "open(" not in source


# ---------------------------------------------------------------------------
# P-XI-12 -- auth/tenant preservation spots: ghost refuses, expired refuses
# (DB).
# ---------------------------------------------------------------------------


async def test_pxi12_ghost_and_expired_refuse() -> None:
    from app.finance_reconciliation.tenant_authority import UnknownTenantError

    ghost = UUID("12345678-1234-5678-1234-567812345678")
    with pytest.raises(UnknownTenantError):
        await render_governed_external(
            "future_finance_projection",
            auth_token=_auth_token(ghost),
            **_scope(),
        )
    tenant_id = _seed_ratio_tenant(76000, 80000, "xi12")
    from app.security.auth import InvalidTokenError
    from test_b26_p1_corrective_vii_consequence import _mint_custom

    expired = _mint_custom(
        tenant_id=tenant_id, user_id=UUID(int=1), expired=True
    )
    with pytest.raises((CanonicalSinkError, InvalidTokenError)):
        await render_governed_external(
            "future_finance_projection", auth_token=expired, **_scope()
        )


# ---------------------------------------------------------------------------
# P-XI-13 -- capability census at test level: the sealed type is not
# constructible through any public surface (unit).
# ---------------------------------------------------------------------------


def test_pxi13_public_surface_has_no_forging_path() -> None:
    import app.finance_reconciliation.canonical_sink as sink_module

    # The public API exposes admission and the renderer -- never a
    # constructor, factory, or serializer that mints capabilities.
    for forbidden in ("make_canonical", "issue_canonical", "mint_canonical"):
        assert not hasattr(sink_module, forbidden)
    # The package re-export surface admits and renders; no object-accepting
    # public renderer exists (VII-B law preserved).
    parameters = set(inspect.signature(render_governed_external).parameters)
    assert "auth_token" in parameters
    assert not (parameters & {"output", "candidate", "dto", "mapping", "value"})


# ---------------------------------------------------------------------------
# P-XI-14 -- external equals internal semantics: every external value is
# the frozen transform of the fresh sovereign execution's fields (DB).
# ---------------------------------------------------------------------------


async def test_pxi14_external_equals_governed_transform_of_internal() -> None:
    tenant_id = _seed_ratio_tenant(50000, 100000, "xi14")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    output = await _execute("future_finance_projection", tenant_id)
    for key, spec in EXTERNAL_SEMANTICS.items():
        source_value = getattr(output, spec.source_attr)
        assert rendered[key] == spec.transform(source_value), key
    assert rendered["matched_minor"] == 50000
    assert rendered["connected_minor"] == 100000
    assert rendered["coverage_percent"] == "50.00"
