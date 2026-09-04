"""B2.5-P14 canonical contract floor: P14-G1 through P14-G4.

These four gates are the part of P14 the original B2.5 hierarchy defines, and
they are propositions about a *registry*, not about a code path -- so they are
proved by loading the real contract file and interrogating it, and falsified by
mutating that file and requiring the loader to refuse.

The falsifiers here are real file mutations applied to a copy of the registry
that the loader is then pointed at. A test that asserted "the loader would
reject X" without ever handing it X would be a restatement of the loader's
docstring; these hand it X.
"""

from __future__ import annotations

import copy
from pathlib import Path
from typing import Any

import pytest
import yaml

from app.trust import projection_profiles as profiles_module
from app.trust.projection import (
    TrustProjectionError,
    assert_authority_monotonic,
    project_trust_envelope,
)
from app.trust.projection_profiles import (
    DEFAULT_LLM_PROFILE_ID,
    REQUIRED_PROFILE_IDS,
    UNTRUSTED_TEXT_CLASSES,
    ProjectionProfileError,
    get_machine_projection_profile,
    get_projection_profile,
    load_projection_profiles,
    position_rank,
    projection_registry_identity,
)


REPO_ROOT = Path(__file__).resolve().parents[3]
EXAMPLES = REPO_ROOT / "contracts/trust-api/examples"


def _load_example(name: str) -> dict[str, Any]:
    import json

    return json.loads((EXAMPLES / f"{name}.json").read_text(encoding="utf-8"))


def _clear_registry_caches() -> None:
    profiles_module._read_registry.cache_clear()
    profiles_module._position_order.cache_clear()
    profiles_module._trust_class_max_position.cache_clear()
    profiles_module.load_projection_profiles.cache_clear()


@pytest.fixture()
def mutable_registry(tmp_path, monkeypatch):
    """Point the loader at a writable copy of the real registry.

    The controlled defects below are applied to this copy, so a falsifier can
    physically change the contract, observe the loader refuse, and restore --
    without leaving residue in the repository.
    """

    source = profiles_module.PROJECTION_PROFILE_REGISTRY_PATH
    target = tmp_path / "projection-profiles.v1.yaml"
    target.write_text(source.read_text(encoding="utf-8"), encoding="utf-8")

    def _install(document: dict[str, Any]) -> None:
        target.write_text(yaml.safe_dump(document, sort_keys=False), encoding="utf-8")
        _clear_registry_caches()

    monkeypatch.setattr(
        profiles_module, "PROJECTION_PROFILE_REGISTRY_PATH", target, raising=True
    )
    _clear_registry_caches()
    original = yaml.safe_load(source.read_text(encoding="utf-8"))
    yield original, _install
    monkeypatch.undo()
    _clear_registry_caches()


# ---------------------------------------------------------------------------
# P14-G1 -- the four profiles exist, are versioned and are reconstructable.
# ---------------------------------------------------------------------------


def test_p14_g1_all_required_projection_profiles_exist_and_are_versioned() -> None:
    loaded = load_projection_profiles()
    for profile_id in REQUIRED_PROFILE_IDS:
        assert profile_id in loaded, profile_id
        profile = loaded[profile_id]
        assert profile.status == "supported"
        assert profile.profile_version, profile_id
        assert profile.fields, profile_id
        # Identity has to be reconstructable from the contract bytes alone.
        assert profile.profile_hash.startswith("sha256:")
        assert profile.identity == f"{profile_id}@{profile.profile_version}"


def test_p14_g1_profile_identity_is_content_addressed_and_change_sensitive(
    mutable_registry,
) -> None:
    """Editing what a profile permits must change the identity it claims."""

    original, install = mutable_registry
    before = get_projection_profile(DEFAULT_LLM_PROFILE_ID).profile_hash

    # An editorial change to prose must not move the identity...
    prose_only = copy.deepcopy(original)
    for profile in prose_only["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["purpose"] = profile["purpose"] + " (clarified)"
    install(prose_only)
    assert get_projection_profile(DEFAULT_LLM_PROFILE_ID).profile_hash == before

    # ...but removing a permitted field must.
    narrowed = copy.deepcopy(original)
    for profile in narrowed["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["fields"] = [
                field for field in profile["fields"] if field["path"] != "currency"
            ]
    install(narrowed)
    assert get_projection_profile(DEFAULT_LLM_PROFILE_ID).profile_hash != before


def test_p14_g1_removing_a_required_profile_fails_the_contract_floor(
    mutable_registry,
) -> None:
    """Gate 1's active falsifier: remove one required profile, require refusal."""

    original, install = mutable_registry
    assert set(REQUIRED_PROFILE_IDS) <= set(load_projection_profiles())

    defective = copy.deepcopy(original)
    defective["profiles"] = [
        profile
        for profile in defective["profiles"]
        if profile["profile_id"] != "optimization_projection_safe"
    ]
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "projection_profile_required_missing" in str(excinfo.value)

    # Exact restoration -> green again.
    install(original)
    assert set(REQUIRED_PROFILE_IDS) <= set(load_projection_profiles())


# ---------------------------------------------------------------------------
# P14-G2 -- the default LLM projection excludes untrusted labels.
# ---------------------------------------------------------------------------


def test_p14_g2_default_llm_projection_admits_no_provider_controlled_class() -> None:
    profile = get_projection_profile(DEFAULT_LLM_PROFILE_ID)
    assert profile.untrusted_labels_admitted is False
    for field in profile.fields:
        assert field.trust_class not in UNTRUSTED_TEXT_CLASSES, field.path
        # And nothing at all in the safe profile reaches an instruction or tool
        # position, regardless of how trusted its class is.
        assert position_rank(field.position) <= position_rank("policy"), field.path


def test_p14_g2_quarantined_provider_text_never_reaches_the_llm_projection() -> None:
    """A real quarantined-label envelope must project without the label."""

    envelope = _load_example("prompt_control_string_quarantined")
    untrusted = envelope["untrusted_display_data"]
    assert untrusted["text_trust_class"] != "none", untrusted

    projection = project_trust_envelope(
        envelope, profile_id=DEFAULT_LLM_PROFILE_ID, machine_consumer=True
    )
    assert projection.untrusted_label_paths == ()
    for path in projection.projected:
        assert not path.startswith("untrusted_display_data"), path

    # The audit profile is the one that may see it -- as evidence of what was
    # received, in a display-only position.
    audit = project_trust_envelope(
        envelope, profile_id="audit_projection_internal", machine_consumer=True
    )
    for path in audit.untrusted_label_paths:
        assert audit.authority_positions[path] == "display_only", path


def test_p14_g2_seating_a_provider_label_in_the_safe_profile_fails_closed(
    mutable_registry,
) -> None:
    """Gate 1's second falsifier: place a quarantined label in the LLM profile."""

    original, install = mutable_registry
    defective = copy.deepcopy(original)
    for profile in defective["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["fields"].append(
                {
                    "path": "untrusted_display_data.display_text",
                    "position": "display_only",
                    "trust_class": "untrusted_display_label",
                }
            )
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "untrusted" in str(excinfo.value)

    install(original)
    assert load_projection_profiles()[DEFAULT_LLM_PROFILE_ID]


def test_p14_g2_promoting_a_provider_label_above_display_fails_closed(
    mutable_registry,
) -> None:
    """Even the profile that admits labels may not seat one above display."""

    original, install = mutable_registry
    defective = copy.deepcopy(original)
    for profile in defective["profiles"]:
        if profile["profile_id"] == "audit_projection_internal":
            for field in profile["fields"]:
                if field["path"] == "untrusted_display_data.display_text":
                    field["position"] = "instruction"
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "projection_position_exceeds_trust_class" in str(excinfo.value)

    install(original)
    assert load_projection_profiles()["audit_projection_internal"]


def test_p14_g2_display_profile_is_not_machine_consumable() -> None:
    profile = get_projection_profile("display_projection_untrusted_labels_allowed")
    assert profile.untrusted_labels_admitted is True
    assert profile.machine_consumption_permitted is False
    with pytest.raises(ProjectionProfileError):
        get_machine_projection_profile("display_projection_untrusted_labels_allowed")


# ---------------------------------------------------------------------------
# P14-G3 -- policy authority stays typed, and monotonic.
# ---------------------------------------------------------------------------


def test_p14_g3_every_profile_projects_policy_authority_as_typed() -> None:
    for profile in load_projection_profiles().values():
        assert profile.policy_authority_projection in ("typed", "omitted")
        for field in profile.fields:
            if field.path.startswith("policy_action_authority"):
                assert field.position == "policy", field.path
                assert field.trust_class == "machine_authority_enum", field.path


def test_p14_g3_an_untyped_policy_state_is_refused_at_projection_time() -> None:
    envelope = copy.deepcopy(_load_example("deterministic_only_verified"))
    envelope["policy_action_authority"]["policy_state"] = "whatever the model said"
    with pytest.raises(ProjectionProfileError) as excinfo:
        project_trust_envelope(envelope, profile_id=DEFAULT_LLM_PROFILE_ID)
    assert "policy_state_untyped" in str(excinfo.value)


def test_p14_g3_authority_monotonicity_permits_reduction_and_refuses_escalation() -> None:
    # Lawful reductions.
    assert_authority_monotonic(
        source_policy_state="approval_required",
        downstream_policy_state="simulation_only",
    )
    assert_authority_monotonic(
        source_policy_state="proposal_required", downstream_policy_state="blocked"
    )
    assert_authority_monotonic(
        source_policy_state="read_only", downstream_policy_state="read_only"
    )
    # Forbidden escalations, exactly as the directive enumerates them.
    for source, downstream in (
        ("simulation_only", "approval_required"),
        ("simulation_only", "proposal_required"),
        ("blocked", "simulation_only"),
        ("read_only", "approval_required"),
    ):
        with pytest.raises(TrustProjectionError) as excinfo:
            assert_authority_monotonic(
                source_policy_state=source, downstream_policy_state=downstream
            )
        assert "authority_escalation_forbidden" in str(excinfo.value)


def test_p14_g3_no_profile_may_declare_an_executable_action_authority(
    mutable_registry,
) -> None:
    original, install = mutable_registry
    defective = copy.deepcopy(original)
    for profile in defective["profiles"]:
        if profile["profile_id"] == "optimization_projection_safe":
            profile["max_action_authority"] = "approval_required"
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "projection_action_authority_forbidden" in str(excinfo.value)

    install(original)
    assert load_projection_profiles()["optimization_projection_safe"]


# ---------------------------------------------------------------------------
# P14-G4 -- an LLM judge holds no authority anywhere in the registry.
# ---------------------------------------------------------------------------


def test_p14_g4_no_profile_grants_judge_or_model_authority() -> None:
    for profile_id, profile in load_projection_profiles().items():
        assert profile.judge_authority == "none", profile_id
        assert profile.llm_authority_over_projected_values == "none", profile_id


def test_p14_g4_granting_judge_authority_fails_the_contract_floor(
    mutable_registry,
) -> None:
    original, install = mutable_registry
    defective = copy.deepcopy(original)
    for profile in defective["profiles"]:
        if profile["profile_id"] == DEFAULT_LLM_PROFILE_ID:
            profile["judge_authority"] = "may_override_confidence"
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "projection_judge_authority_forbidden" in str(excinfo.value)

    install(original)
    assert load_projection_profiles()[DEFAULT_LLM_PROFILE_ID].judge_authority == "none"


def test_p14_g4_no_execution_position_exists_in_any_profile(mutable_registry) -> None:
    for profile in load_projection_profiles().values():
        for field in profile.fields:
            assert field.position != "execution", field.path

    original, install = mutable_registry
    defective = copy.deepcopy(original)
    for profile in defective["profiles"]:
        if profile["profile_id"] == "optimization_projection_safe":
            profile["fields"][0]["position"] = "execution"
    install(defective)
    with pytest.raises(ProjectionProfileError) as excinfo:
        load_projection_profiles()
    assert "projection_position_forbidden" in str(excinfo.value)

    install(original)
    assert load_projection_profiles()["optimization_projection_safe"]


# ---------------------------------------------------------------------------
# Projection mechanics: allowlist, no mutation, no floats, identity.
# ---------------------------------------------------------------------------


def test_projection_is_an_allowlist_and_never_mutates_a_projected_value() -> None:
    envelope = _load_example("revenue_claim_valid_with_verified_revenue_minor")
    projection = project_trust_envelope(envelope, profile_id=DEFAULT_LLM_PROFILE_ID)
    allowed = set(get_projection_profile(DEFAULT_LLM_PROFILE_ID).field_paths())
    assert set(projection.projected) <= allowed

    # Fields outside the profile are absent, not defaulted.
    assert "signature" not in projection.projected
    assert "provenance_chain" not in projection.projected

    # Every projected value equals its source exactly.
    assert projection.value("verified_revenue_minor") == envelope["verified_revenue_minor"]
    assert isinstance(projection.value("verified_revenue_minor"), int)
    assert projection.value("currency") == envelope["currency"]
    assert projection.semantic_truth_hash == envelope["semantic_truth_hash"]


def test_projection_refuses_float_money_on_the_authoritative_path() -> None:
    """H-RC7. A float here means the value passed through a layer that may not
    define it, so the boundary refuses the type rather than coercing it back."""

    envelope = copy.deepcopy(
        _load_example("revenue_claim_valid_with_verified_revenue_minor")
    )
    envelope["verified_revenue_minor"] = 123.45
    with pytest.raises(TrustProjectionError) as excinfo:
        project_trust_envelope(envelope, profile_id=DEFAULT_LLM_PROFILE_ID)
    assert "projection_float_forbidden" in str(excinfo.value)


def test_projection_requires_source_trust_identity() -> None:
    envelope = copy.deepcopy(_load_example("deterministic_only_verified"))
    del envelope["semantic_truth_hash"]
    with pytest.raises(TrustProjectionError) as excinfo:
        project_trust_envelope(envelope, profile_id=DEFAULT_LLM_PROFILE_ID)
    assert "projection_source_identity_missing" in str(excinfo.value)


def test_registry_identity_is_reconstructable_evidence() -> None:
    identity = projection_registry_identity()
    assert identity["registry_version"] == profiles_module.REGISTRY_VERSION
    assert set(identity["profiles"]) >= set(REQUIRED_PROFILE_IDS)
    for row in identity["profiles"].values():
        assert row["judge_authority"] == "none"
        assert row["profile_hash"].startswith("sha256:")
