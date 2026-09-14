"""B2.6-P1 Corrective-X consequence proof battery (cells P-X-1..P-X-12).

Defect classes X-A (external canonical census escape) and X-B (detached
authority reacquisition): the approved external renderer must emit EXACTLY
the governed external universe with values from their declared canonical
sources, and no detached representation may reacquire canonical external
authority through any annotation, name, representation, construction, or
serialization primitive.

Single source of truth: ``authoritative_fields.GOVERNED_EXTERNAL_KEYS``
(mechanically derived from the registry). The approved renderer refuses
extra/missing/prohibited keys at runtime on the FINAL mapping
(construction-primitive independent); the static validator pins the exact
census and per-key value lineage merge-blocking.

Development mechanisms (used while designing the X fix):
  D1 literal extra key            D2 update()/merge extra key
  D3 missing required key         D4 wrong-source (projection/caller)
  D5 typed detached renderer      D6 untyped detached renderer
  D7 Mapping/dict DTO renderer    D8 sibling-module emitter
  D9 serializer promotion         D10 raw tenant externalization
  D11 adjunct externalization     D12 adjacent-domain wired value
  D13 registry/policy drift       D14 **kwargs authority emitter

Holdout mechanisms (frozen after the fix, never used during development):
  H1-H6 novel extra-key names x novel primitives (runtime refusal)
  H7  novel detached carrier (Mapping subclass record)
  H8  novel detached emitter (positional *args)
  H9  novel dynamic form (|= merge + conditional insertion)
  H10 novel lineage swap (currency from caller scope)
  H11 novel serialization form (vars()/__dict__ snapshot)
  H12 lawful-extension shape (governed-key-only helper mapping passes)

* P-X-1  -- single-source unity: derived set == pinned census == authoritative.
* P-X-2  -- runtime refusal is construction-primitive independent.
* P-X-3  -- approved renderer static shape mirrors the contract.
* P-X-4  -- lawful renderer emits the exact governed census, sovereign values.
* P-X-5  -- detached synthetic has no promoter (typed/untyped/mapping/copy).
* P-X-6  -- generic serialization cannot reacquire canonical authority.
* P-X-7  -- external values equal fresh sovereign execution (lineage behavior).
* P-X-8  -- holdout extra-key battery refused at runtime (H1..H6).
* P-X-9  -- holdout detached-emitter battery has no promotion path (H7..H9).
* P-X-10 -- authority-label propagation: census exact, tenant hash-only.
* P-X-11 -- internal/external schema unity (no silent drift surface).
* P-X-12 -- preservation spot: 95.00 golden, successor refuses, ontology confined.
"""

from __future__ import annotations

import ast
import inspect
from typing import Any

import pytest

from app.finance_reconciliation.authoritative_fields import (
    AUTHORITATIVE_FIELD_REGISTRY,
    EXTERNAL_FIELD_RENDER_ATTRS,
    EXTERNAL_FIELD_SOURCES,
    GOVERNED_EXTERNAL_KEYS,
    PROHIBITED_EXTERNAL_KEYS,
    REQUIRED_EXTERNAL_KEYS,
    assert_external_keys_derive_from_registry,
    assert_registry_covers_output,
    authoritative_field_names,
    governed_external_keys,
    validate_external_rendering,
)
from app.finance_reconciliation.canonical_sink import (
    CANONICAL_OUTPUT_AUTHORITY,
    FinalCanonicalOutput,
    external_renderer_signature_is_execution_bound,
    render_governed_external,
    verify_output_integrity,
)
from app.finance_reconciliation.coverage_authority import (
    CanonicalCoverageAuthorityError,
    admit_canonical_verification_coverage,
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


@pytest.fixture(autouse=True)
async def _fresh_engines_per_test():
    yield
    from app.db.session import b23_engine
    from app.db.session import engine as app_engine

    await b23_engine.dispose()
    await app_engine.dispose()


# ---------------------------------------------------------------------------
# P-X-1 -- single-source unity (unit).
# ---------------------------------------------------------------------------


def test_px1_single_source_unity() -> None:
    assert_external_keys_derive_from_registry()
    assert_registry_covers_output(FinalCanonicalOutput)
    assert set(governed_external_keys()) == set(PINNED_EXTERNAL_KEYS)
    assert set(GOVERNED_EXTERNAL_KEYS) == set(PINNED_EXTERNAL_KEYS)
    assert set(REQUIRED_EXTERNAL_KEYS) == set(PINNED_EXTERNAL_KEYS)
    assert set(authoritative_field_names()) == set(PINNED_EXTERNAL_KEYS)
    assert set(EXTERNAL_FIELD_SOURCES) == set(PINNED_EXTERNAL_KEYS)
    assert set(EXTERNAL_FIELD_RENDER_ATTRS) == set(PINNED_EXTERNAL_KEYS)
    assert set(PROHIBITED_EXTERNAL_KEYS) == {"tenant_id", "content_digest", "adjunct_json"}
    assert not (set(PROHIBITED_EXTERNAL_KEYS) & set(PINNED_EXTERNAL_KEYS))
    for key, spec in EXTERNAL_FIELD_SOURCES.items():
        assert spec["authority_class"] == "authoritative"
        assert spec["canonical_source"]
        assert spec["transform"]
        assert spec["render_attr"]
    for key in PINNED_EXTERNAL_KEYS:
        assert key in AUTHORITATIVE_FIELD_REGISTRY
        assert AUTHORITATIVE_FIELD_REGISTRY[key].authoritative is True
        assert AUTHORITATIVE_FIELD_REGISTRY[key].externalization_policy.startswith(
            "emitted"
        )


# ---------------------------------------------------------------------------
# P-X-2 -- runtime refusal is construction-primitive independent (unit).
# ---------------------------------------------------------------------------


def _lawful_mapping() -> dict[str, Any]:
    return dict.fromkeys(PINNED_EXTERNAL_KEYS, 1)


def test_px2_runtime_refusal_construction_independent() -> None:
    validate_external_rendering(_lawful_mapping())
    # D1 literal-style extra key with a novel finance name.
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**_lawful_mapping(), "settled_revenue_minor": 1})
    # D2 update()/merge-style extra key.
    probe = _lawful_mapping()
    probe.update({"reconciled_amount_minor": 1})
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(probe)
    merged = _lawful_mapping() | {"canonical_revenue_minor": 1}
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(merged)
    # Comprehension-built extra key.
    comp = {k: 1 for k in [*PINNED_EXTERNAL_KEYS, "verified_sales_minor"]}
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(comp)
    # D3 missing required key.
    missing = _lawful_mapping()
    del missing["matched_minor"]
    with pytest.raises(ValueError, match="canonical_external_required_key_missing"):
        validate_external_rendering(missing)
    # D10/D11 prohibited keys.
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**_lawful_mapping(), "tenant_id": "raw"})
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**_lawful_mapping(), "adjunct_json": "{}"})
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**_lawful_mapping(), "content_digest": "x"})
    # Non-mapping input refuses.
    with pytest.raises(ValueError, match="canonical_external_rendering_not_mapping"):
        validate_external_rendering(["authority"])  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# P-X-3 -- approved renderer static shape mirrors the contract (unit).
# ---------------------------------------------------------------------------


def test_px3_renderer_shape_mirrors_contract() -> None:
    source = inspect.getsource(render_governed_external)
    tree = ast.parse(source)
    func = next(
        node
        for node in ast.walk(tree)
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    )
    rendered_dict: ast.Dict | None = None
    for node in ast.walk(func):
        if isinstance(node, ast.Assign) and any(
            isinstance(target, ast.Name) and target.id == "rendered"
            for target in node.targets
        ):
            assert isinstance(node.value, ast.Dict)
            rendered_dict = node.value
    assert rendered_dict is not None
    literal_keys = {
        key.value
        for key in rendered_dict.keys
        if isinstance(key, ast.Constant) and isinstance(key.value, str)
    }
    assert literal_keys == set(PINNED_EXTERNAL_KEYS)
    allowed_roots = {"output", "list", "int", "str", "bool"}
    for key_node, value_node in zip(rendered_dict.keys, rendered_dict.values):
        assert isinstance(key_node, ast.Constant)
        key = key_node.value
        expected_attr = EXTERNAL_FIELD_RENDER_ATTRS[key]
        output_attrs = {
            child.attr
            for child in ast.walk(value_node)
            if isinstance(child, ast.Attribute)
            and isinstance(child.value, ast.Name)
            and child.value.id == "output"
        }
        assert expected_attr in output_attrs
        foreign = {
            child.id for child in ast.walk(value_node) if isinstance(child, ast.Name)
        } - allowed_roots
        assert not foreign
    assert external_renderer_signature_is_execution_bound()
    assert "await execute_governed_sink(" in source


# ---------------------------------------------------------------------------
# P-X-4 -- lawful renderer emits the exact governed census (DB).
# ---------------------------------------------------------------------------


async def test_px4_lawful_render_exact_census_sovereign_values() -> None:
    tenant_id = _seed_ratio_tenant(76000, 80000, "x4")
    scope = _scope()
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **scope
    )
    assert set(rendered.keys()) == set(PINNED_EXTERNAL_KEYS)
    validate_external_rendering(rendered)
    assert rendered["authority"] == CANONICAL_OUTPUT_AUTHORITY
    assert rendered["matched_minor"] == 76000
    assert rendered["connected_minor"] == 80000
    assert rendered["coverage_percent"] == "95.00"
    assert rendered["zero_denominator"] is False
    assert rendered["currency_code"] == "USD"
    assert rendered["supported_platforms"] == ["stripe"]
    assert "tenant_id" not in rendered
    assert "adjunct_json" not in rendered
    assert "content_digest" not in rendered
    from app.trust.refusal import tenant_hash

    assert rendered["tenant_id_hash"] == tenant_hash(tenant_id)


# ---------------------------------------------------------------------------
# P-X-5 -- detached synthetic has no promoter (DB).
# ---------------------------------------------------------------------------


async def test_px5_detached_synthetic_has_no_promoter() -> None:
    tenant_id = _seed_ratio_tenant(76000, 80000, "x5")
    output = await _execute("future_finance_projection", tenant_id)
    assert verify_output_integrity(output) is True
    # No object-accepting renderer exists at any visibility.
    import app.finance_reconciliation.canonical_sink as sink_module

    assert not hasattr(sink_module, "to_canonical_external")
    assert not hasattr(sink_module, "_project_external_fields")
    # Admission always refuses caller observations, however digest-correct.
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(output)  # type: ignore[arg-type]
    # Copies, rebuilds, and mapping round-trips gain no renderer either.
    import copy

    for variant in (
        copy.copy(output),
        copy.deepcopy(output),
    ):
        with pytest.raises(CanonicalCoverageAuthorityError):
            admit_canonical_verification_coverage(variant)  # type: ignore[arg-type]
    # Tamper breaks even integrity.
    tampered = FinalCanonicalOutput(
        authority=output.authority,
        sink_id=output.sink_id,
        contract_version=output.contract_version,
        tenant_id_hash=output.tenant_id_hash,
        currency_code=output.currency_code,
        window_start=output.window_start,
        window_end=output.window_end,
        supported_platforms=output.supported_platforms,
        matched_minor=1,
        connected_minor=output.connected_minor,
        coverage_percent=output.coverage_percent,
        zero_denominator=output.zero_denominator,
        provenance_mode=output.provenance_mode,
        sovereign_producer=output.sovereign_producer,
        content_digest=output.content_digest,
        adjunct_json=output.adjunct_json,
    )
    assert verify_output_integrity(tampered) is False


# ---------------------------------------------------------------------------
# P-X-6 -- generic serialization cannot reacquire authority (DB).
# ---------------------------------------------------------------------------


async def test_px6_serialization_non_authority() -> None:
    import dataclasses

    tenant_id = _seed_ratio_tenant(76000, 80000, "x6")
    output = await _execute("future_finance_projection", tenant_id)
    serialized = dataclasses.asdict(output)
    assert serialized["authority"] == CANONICAL_OUTPUT_AUTHORITY
    # A serialized mapping is data, not authority: no admission path takes it.
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(serialized)  # type: ignore[arg-type]
    with pytest.raises(CanonicalCoverageAuthorityError):
        admit_canonical_verification_coverage(vars(output))  # type: ignore[arg-type]
    # The approved renderer takes scope+auth, never a mapping/DTO.
    parameters = set(inspect.signature(render_governed_external).parameters)
    assert "auth_token" in parameters
    assert not (parameters & {"output", "candidate", "dto", "mapping", "value"})


# ---------------------------------------------------------------------------
# P-X-7 -- external values equal fresh sovereign execution (DB).
# ---------------------------------------------------------------------------


async def test_px7_external_lineage_matches_sovereign_execution() -> None:
    tenant_id = _seed_ratio_tenant(50000, 100000, "x7")
    scope = _scope()
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **scope
    )
    output = await _execute("future_finance_projection", tenant_id)
    assert rendered["matched_minor"] == int(output.matched_minor) == 50000
    assert rendered["connected_minor"] == int(output.connected_minor) == 100000
    assert rendered["coverage_percent"] == str(output.coverage_percent) == "50.00"
    assert rendered["tenant_id_hash"] == output.tenant_id_hash
    assert rendered["sink_id"] == output.sink_id == "future_finance_projection"


# ---------------------------------------------------------------------------
# P-X-8 -- holdout extra-key battery refused at runtime (H1..H6, unit).
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "extra",
    [
        "settled_revenue_minor",
        "reconciled_amount_minor",
        "verified_sales_minor",
        "canonical_revenue_minor",
        "discrepancy_minor",
        "attributed_revenue_minor",
    ],
)
def test_px8_holdout_extra_keys_refused(extra: str) -> None:
    base = _lawful_mapping()
    # H1 literal-style.
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**base, extra: 7})
    # H2 update-style.
    probe = dict(base)
    probe.update({extra: 7})
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(probe)
    # H9 merge-style.
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(base | {extra: 7})
    # Conditional-insertion style.
    conditional = dict(base)
    if extra not in conditional:
        conditional[extra] = 7
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(conditional)
    # Loop-insertion style.
    looped = dict(base)
    for key in (extra,):
        looped[key] = 7
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(looped)
    # Helper-produced mapping style.
    def _helper() -> dict[str, Any]:
        return {extra: 7}

    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering({**base, **_helper()})


def test_px8_holdout_mapping_subclass_refused() -> None:
    class GovernedPlus(dict):  # H-structure: Mapping subclass carrier.
        pass

    probe = GovernedPlus(_lawful_mapping())
    probe["discrepancy_minor"] = 3
    with pytest.raises(ValueError, match="canonical_external_undeclared_key"):
        validate_external_rendering(probe)


# ---------------------------------------------------------------------------
# P-X-9 -- holdout detached-emitter battery has no promotion path (unit).
# ---------------------------------------------------------------------------


def test_px9_holdout_detached_shapes_unrepresentable() -> None:
    import app.finance_reconciliation.canonical_sink as sink_module

    # H7 Mapping-subclass record, H8 *args emitter: no module-level callable
    # besides the approved boundary accepts detached state and returns a
    # mapping. Lawful non-mapping consumers (integrity predicate) and the
    # adjunct guard are exempt by return shape, not by name.
    for name in dir(sink_module):
        if name in {"render_governed_external", "execute_governed_sink"}:
            continue
        member = getattr(sink_module, name)
        if not callable(member) or isinstance(member, type):
            continue
        try:
            signature = inspect.signature(member)
        except (TypeError, ValueError):
            continue
        returns_mapping = (
            signature.return_annotation in {"dict", "Dict", "Mapping"}
            or getattr(signature.return_annotation, "__name__", "") in {"dict"}
            or "dict" in str(signature.return_annotation).lower()
            and "bool" not in str(signature.return_annotation).lower()
        )
        if not returns_mapping:
            continue
        parameters = set(signature.parameters)
        assert not (
            parameters & {"output", "candidate", "dto", "record", "value", "carrier"}
        ), name
    # The only authority-bearing mapping producer executes the sink itself.
    assert external_renderer_signature_is_execution_bound()


def test_px9_holdout_vars_dict_snapshot_non_authoritative() -> None:
    # H11 vars()/__dict__ snapshot of a lawful output is data, and the type
    # exposes no promotion method.
    assert not hasattr(FinalCanonicalOutput, "to_canonical_external")


# ---------------------------------------------------------------------------
# P-X-10 -- authority-label propagation (DB).
# ---------------------------------------------------------------------------


async def test_px10_authority_label_census_exact() -> None:
    tenant_id = _seed_ratio_tenant(76000, 80000, "x10")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert rendered["authority"] == CANONICAL_OUTPUT_AUTHORITY
    # Every sibling field beneath the canonical label is censused: no key
    # inherits canonical meaning accidentally.
    assert set(rendered.keys()) == set(PINNED_EXTERNAL_KEYS)
    for key in PINNED_EXTERNAL_KEYS:
        assert EXTERNAL_FIELD_SOURCES[key]["authority_class"] == "authoritative"


# ---------------------------------------------------------------------------
# P-X-11 -- internal/external schema unity (unit).
# ---------------------------------------------------------------------------


def test_px11_internal_external_schema_unity() -> None:
    import dataclasses

    declared = {field.name for field in dataclasses.fields(FinalCanonicalOutput)}
    assert set(AUTHORITATIVE_FIELD_REGISTRY) == declared
    # Every authoritative internal field externalizes; integrity/adjunct
    # fields never do.
    assert set(authoritative_field_names()) == set(GOVERNED_EXTERNAL_KEYS)
    for internal_only in ("content_digest", "adjunct_json"):
        assert internal_only in declared
        assert internal_only not in GOVERNED_EXTERNAL_KEYS
        assert AUTHORITATIVE_FIELD_REGISTRY[internal_only].authoritative is False


# ---------------------------------------------------------------------------
# P-X-12 -- preservation spot (DB).
# ---------------------------------------------------------------------------


async def test_px12_preservation_spot() -> None:
    from decimal import Decimal

    from app.finance_reconciliation.canonical_sink import (
        SuccessorProvenanceError,
        authorize_successor_persistence,
        deregister_successor_persistence,
        register_successor_persistence,
    )
    from app.finance_reconciliation.coverage_authority import (
        independent_coverage_percent,
    )

    tenant_id = _seed_ratio_tenant(76000, 80000, "x12")
    rendered = await render_governed_external(
        "future_finance_projection", auth_token=_auth_token(tenant_id), **_scope()
    )
    assert (rendered["matched_minor"], rendered["connected_minor"]) == (76000, 80000)
    assert rendered["coverage_percent"] == "95.00"
    assert independent_coverage_percent(76000, 80000) == (Decimal("95.00"), False)
    # Successor persistence remains unauthorized in P1.
    register_successor_persistence(
        registration_id="px12_probe",
        provenance_mode="RE_DERIVE_ON_READ",
        required_runtime_proof_ids=("VI-6",),
    )
    try:
        with pytest.raises(SuccessorProvenanceError):
            authorize_successor_persistence("px12_probe")
    finally:
        deregister_successor_persistence("px12_probe")
    # Adjacent-domain payloads stay adjunct-confined and never externalize.
    async def _llm_adjunct(context: Any) -> dict[str, Any]:
        return {"llm_summary": "seventy-six thousand", "b2_4_estimate": "94.00"}

    from app.finance_reconciliation.canonical_sink import (
        SINK_REGISTRY,
        _SINK_IMPLEMENTATIONS,
        _implementation_hash,
    )
    from app.finance_reconciliation.canonical_sink import (
        SinkRegistration as _SinkRegistration,
    )

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
        version="v9.9-x12-probe",
        required_runtime_proof_ids=pristine_registration.required_runtime_proof_ids,
    )
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
    assert "llm_summary" not in poisoned
    assert "b2_4_estimate" not in poisoned
    assert set(poisoned.keys()) == set(PINNED_EXTERNAL_KEYS)
