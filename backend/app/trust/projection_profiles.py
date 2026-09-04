"""B2.5-P14 downstream projection profile registry.

P14's governing law is that downstream authority may never exceed source
authority::

    A(y) <= A(x)   for a projection y of source authority x

A projection profile is the machine-readable statement of that bound for one
downstream consumer class. It answers two questions that P14 requires to remain
formally separate:

* **Truth correspondence.** Which source fields may appear downstream at all.
  Not every field must; a field that does may not be mutated. The registry
  answers with an explicit allowlist, so a value absent from the allowlist has
  no lawful downstream existence rather than a defaulted one.
* **Authority monotonicity.** Which *position* a projected value may occupy in
  the consumer -- display, evidence, policy, tool context, instruction,
  execution. A faithful copy of ``verified_revenue_minor`` placed in an
  instruction position is truth-correspondent and still unlawful.

Everything here fails closed. An unknown profile id, an unknown field path, an
unknown text trust class, an unknown position, a profile that admits a provider
label above ``display_only``, or a profile that claims any judge authority is an
error at load time, not a defaulted value at call time.

The identity of a profile is content-addressed. ``profile_hash`` is a tagged
SHA-256 over the profile's canonical form, so a persisted explanation or
simulation names the exact bytes of the contract it was produced under. Editing
a profile changes its hash, and a stored artifact then no longer claims to have
been produced under the edited rule -- which is what makes Gate 12's
reconstruction requirement a property of the data rather than of a convention.
"""

from __future__ import annotations

from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Mapping

import yaml

from app.trust.canonicalization import canonicalize_json_document
from app.trust.refusal import tagged_sha256


ROOT = Path(__file__).resolve().parents[3]
PROJECTION_PROFILE_REGISTRY_PATH = (
    ROOT / "contracts/trust-api/projection-profiles.v1.yaml"
)

REGISTRY_VERSION = "b25-p14-projection-profiles-v1"

# P14-G1 names these four profiles explicitly. A registry that does not carry
# all four is not a P14 contract floor, so absence is an error rather than a
# smaller registry.
REQUIRED_PROFILE_IDS: tuple[str, ...] = (
    "llm_explanation_projection_safe",
    "optimization_projection_safe",
    "audit_projection_internal",
    "display_projection_untrusted_labels_allowed",
)

# The profile a machine consumer gets when it does not name one. P14-G2 is the
# proposition that this default excludes untrusted labels.
DEFAULT_LLM_PROFILE_ID = "llm_explanation_projection_safe"

# Positions weaker than or equal to `evidence` carry no capacity to direct the
# consumer. `execution` exists in the order so the order is total over the
# positions the system can name, and is forbidden to every P14 profile.
FORBIDDEN_POSITIONS: frozenset[str] = frozenset({"execution"})

# P14-G3. A projected policy state stays a member of the source enum. Free text
# is not a policy state, and neither is a model's paraphrase of one.
TYPED_POLICY_STATES: tuple[str, ...] = (
    "blocked",
    "read_only",
    "simulation_only",
    "proposal_required",
    "approval_required",
)

# The authority partial order over policy states, weakest first. P14 §0.2:
# downstream authority may remain equal or become more restrictive, never
# stronger.
POLICY_STATE_AUTHORITY_ORDER: tuple[str, ...] = (
    "blocked",
    "read_only",
    "simulation_only",
    "proposal_required",
    "approval_required",
)

# Provider-controlled classes. A signature over these authenticates that
# Skeldir received those bytes; it never authenticates that the bytes are true
# or safe to obey.
UNTRUSTED_TEXT_CLASSES: frozenset[str] = frozenset(
    {
        "untrusted_display_label",
        "quarantined_text_hash",
        "provider_controlled_quarantined",
        "operator_controlled_safe_label",
        "redacted_text",
    }
)


class ProjectionProfileError(ValueError):
    """Raised when the projection contract floor cannot be established."""


@dataclass(frozen=True)
class ProjectedField:
    """One allowlisted source path and the strongest position it may occupy."""

    path: str
    position: str
    trust_class: str


@dataclass(frozen=True)
class ProjectionProfile:
    """A versioned, content-addressed downstream projection contract."""

    profile_id: str
    profile_version: str
    status: str
    purpose: str
    untrusted_labels_admitted: bool
    machine_consumption_permitted: bool
    policy_authority_projection: str
    judge_authority: str
    max_action_authority: str
    llm_authority_over_projected_values: str
    fields: tuple[ProjectedField, ...]
    profile_hash: str

    @property
    def identity(self) -> str:
        """The identity a downstream artifact records to name this contract."""
        return f"{self.profile_id}@{self.profile_version}"

    def field_paths(self) -> tuple[str, ...]:
        return tuple(field.path for field in self.fields)

    def position_of(self, path: str) -> str:
        for field in self.fields:
            if field.path == path:
                return field.position
        raise ProjectionProfileError(
            f"projection_field_not_in_profile:{self.profile_id}:{path}"
        )


def policy_state_authority_rank(policy_state: str) -> int:
    """Rank a typed policy state within the authority order."""
    try:
        return POLICY_STATE_AUTHORITY_ORDER.index(policy_state)
    except ValueError as exc:
        raise ProjectionProfileError(
            f"policy_state_untyped:{policy_state!r}"
        ) from exc


@lru_cache(maxsize=1)
def _read_registry() -> dict[str, Any]:
    if not PROJECTION_PROFILE_REGISTRY_PATH.exists():
        raise ProjectionProfileError(
            "projection_profile_registry_missing:"
            f"{PROJECTION_PROFILE_REGISTRY_PATH.as_posix()}"
        )
    with PROJECTION_PROFILE_REGISTRY_PATH.open(encoding="utf-8") as fh:
        data = yaml.safe_load(fh)
    if not isinstance(data, dict):
        raise ProjectionProfileError("projection_profile_registry_not_object")
    if data.get("registry_version") != REGISTRY_VERSION:
        raise ProjectionProfileError(
            f"projection_registry_version_unsupported:{data.get('registry_version')!r}"
        )
    return data


@lru_cache(maxsize=1)
def _position_order() -> tuple[str, ...]:
    order = _read_registry().get("position_authority_order")
    if not isinstance(order, list) or not order:
        raise ProjectionProfileError("projection_position_order_missing")
    if len(set(order)) != len(order):
        raise ProjectionProfileError("projection_position_order_not_unique")
    for entry in order:
        if not isinstance(entry, str) or not entry:
            raise ProjectionProfileError("projection_position_order_invalid")
    return tuple(order)


@lru_cache(maxsize=1)
def _trust_class_max_position() -> Mapping[str, str]:
    table = _read_registry().get("text_trust_class_max_position")
    if not isinstance(table, dict) or not table:
        raise ProjectionProfileError("projection_trust_class_table_missing")
    order = _position_order()
    for trust_class, position in table.items():
        if position not in order:
            raise ProjectionProfileError(
                f"projection_trust_class_position_unknown:{trust_class}:{position}"
            )
    return dict(table)


def position_rank(position: str) -> int:
    """Rank a consumer position within the declared authority order."""
    try:
        return _position_order().index(position)
    except ValueError as exc:
        raise ProjectionProfileError(f"projection_position_unknown:{position}") from exc


def _canonical_profile_form(raw: Mapping[str, Any]) -> dict[str, Any]:
    """The exact bytes a profile's identity is computed over.

    ``purpose`` is prose for a reader and deliberately excluded: an editorial
    clarification must not change the identity a stored artifact was produced
    under, while any change to what the profile *permits* must.
    """

    return {
        "registry_version": REGISTRY_VERSION,
        "profile_id": raw["profile_id"],
        "profile_version": raw["profile_version"],
        "status": raw["status"],
        "untrusted_labels_admitted": bool(raw["untrusted_labels_admitted"]),
        "machine_consumption_permitted": bool(
            raw.get("machine_consumption_permitted", True)
        ),
        "policy_authority_projection": raw["policy_authority_projection"],
        "judge_authority": raw["judge_authority"],
        "max_action_authority": raw["max_action_authority"],
        "llm_authority_over_projected_values": raw[
            "llm_authority_over_projected_values"
        ],
        "fields": [
            {
                "path": field["path"],
                "position": field["position"],
                "trust_class": field["trust_class"],
            }
            for field in raw["fields"]
        ],
    }


def _build_profile(raw: Mapping[str, Any]) -> ProjectionProfile:
    for key in (
        "profile_id",
        "profile_version",
        "status",
        "purpose",
        "untrusted_labels_admitted",
        "policy_authority_projection",
        "judge_authority",
        "max_action_authority",
        "llm_authority_over_projected_values",
        "fields",
    ):
        if key not in raw:
            raise ProjectionProfileError(
                f"projection_profile_incomplete:{raw.get('profile_id')!r}:{key}"
            )

    profile_id = str(raw["profile_id"])
    fields_raw = raw["fields"]
    if not isinstance(fields_raw, list) or not fields_raw:
        raise ProjectionProfileError(f"projection_profile_no_fields:{profile_id}")

    # P14-G4. A judge may assess presentation quality. It may never hold
    # authority over financial truth, confidence, causal status or policy.
    if raw["judge_authority"] != "none":
        raise ProjectionProfileError(
            f"projection_judge_authority_forbidden:{profile_id}:{raw['judge_authority']!r}"
        )
    if raw["llm_authority_over_projected_values"] != "none":
        raise ProjectionProfileError(
            f"projection_llm_authority_forbidden:{profile_id}:"
            f"{raw['llm_authority_over_projected_values']!r}"
        )
    # P14-G3. Typed or omitted; never degraded into free text.
    if raw["policy_authority_projection"] not in ("typed", "omitted"):
        raise ProjectionProfileError(
            f"projection_policy_authority_untyped:{profile_id}:"
            f"{raw['policy_authority_projection']!r}"
        )
    # P14 remains READ / COMPUTE / PROPOSE. `approval_required` and anything
    # executable are not projection-reachable authorities.
    if raw["max_action_authority"] not in ("blocked", "read_only", "simulation_only"):
        raise ProjectionProfileError(
            f"projection_action_authority_forbidden:{profile_id}:"
            f"{raw['max_action_authority']!r}"
        )

    seen: set[str] = set()
    fields: list[ProjectedField] = []
    max_positions = _trust_class_max_position()
    admits_untrusted = bool(raw["untrusted_labels_admitted"])
    for entry in fields_raw:
        if not isinstance(entry, dict):
            raise ProjectionProfileError(f"projection_field_not_object:{profile_id}")
        path = str(entry.get("path", ""))
        position = str(entry.get("position", ""))
        trust_class = str(entry.get("trust_class", ""))
        if not path:
            raise ProjectionProfileError(f"projection_field_path_missing:{profile_id}")
        if path in seen:
            raise ProjectionProfileError(
                f"projection_field_duplicate:{profile_id}:{path}"
            )
        seen.add(path)
        if position in FORBIDDEN_POSITIONS:
            raise ProjectionProfileError(
                f"projection_position_forbidden:{profile_id}:{path}:{position}"
            )
        rank = position_rank(position)
        if trust_class not in max_positions:
            raise ProjectionProfileError(
                f"projection_trust_class_unknown:{profile_id}:{path}:{trust_class}"
            )
        ceiling = position_rank(max_positions[trust_class])
        if rank > ceiling:
            # This is P14-G2 expressed as arithmetic rather than as a policy
            # sentence: a provider-controlled class has a display-only ceiling,
            # so any attempt to seat one above that ceiling fails at load.
            raise ProjectionProfileError(
                f"projection_position_exceeds_trust_class:{profile_id}:{path}:"
                f"{position}>{max_positions[trust_class]}"
            )
        if trust_class in UNTRUSTED_TEXT_CLASSES and not admits_untrusted:
            raise ProjectionProfileError(
                f"projection_untrusted_label_not_admitted:{profile_id}:{path}"
            )
        fields.append(
            ProjectedField(path=path, position=position, trust_class=trust_class)
        )

    canonical = _canonical_profile_form(raw)
    profile_hash = tagged_sha256(
        canonicalize_json_document(canonical).decode("utf-8")
    )
    return ProjectionProfile(
        profile_id=profile_id,
        profile_version=str(raw["profile_version"]),
        status=str(raw["status"]),
        purpose=str(raw["purpose"]).strip(),
        untrusted_labels_admitted=admits_untrusted,
        machine_consumption_permitted=bool(
            raw.get("machine_consumption_permitted", True)
        ),
        policy_authority_projection=str(raw["policy_authority_projection"]),
        judge_authority=str(raw["judge_authority"]),
        max_action_authority=str(raw["max_action_authority"]),
        llm_authority_over_projected_values=str(
            raw["llm_authority_over_projected_values"]
        ),
        fields=tuple(fields),
        profile_hash=profile_hash,
    )


@lru_cache(maxsize=1)
def load_projection_profiles() -> Mapping[str, ProjectionProfile]:
    """Load, validate and content-address every supported projection profile."""
    registry = _read_registry()
    raw_profiles = registry.get("profiles")
    if not isinstance(raw_profiles, list) or not raw_profiles:
        raise ProjectionProfileError("projection_profiles_missing")

    profiles: dict[str, ProjectionProfile] = {}
    for raw in raw_profiles:
        if not isinstance(raw, dict):
            raise ProjectionProfileError("projection_profile_not_object")
        if str(raw.get("status")) != "supported":
            continue
        profile = _build_profile(raw)
        if profile.profile_id in profiles:
            raise ProjectionProfileError(
                f"projection_profile_duplicate:{profile.profile_id}"
            )
        profiles[profile.profile_id] = profile

    missing = [pid for pid in REQUIRED_PROFILE_IDS if pid not in profiles]
    if missing:
        raise ProjectionProfileError(f"projection_profile_required_missing:{missing}")

    # P14-G2 as a registry-level proposition, not only a per-field one: the
    # default LLM projection must admit no provider-controlled class at all.
    default = profiles[DEFAULT_LLM_PROFILE_ID]
    if default.untrusted_labels_admitted:
        raise ProjectionProfileError(
            "projection_default_llm_admits_untrusted_labels"
        )
    for field in default.fields:
        if field.trust_class in UNTRUSTED_TEXT_CLASSES:
            raise ProjectionProfileError(
                f"projection_default_llm_untrusted_field:{field.path}"
            )
    return profiles


def get_projection_profile(profile_id: str) -> ProjectionProfile:
    """Return one supported profile, failing closed on an unknown identity."""
    profiles = load_projection_profiles()
    try:
        return profiles[profile_id]
    except KeyError as exc:
        raise ProjectionProfileError(
            f"projection_profile_unsupported:{profile_id!r}"
        ) from exc


def get_machine_projection_profile(profile_id: str) -> ProjectionProfile:
    """Return a profile a machine consumer may lawfully read.

    The display profile exists so a human surface can render a provider label.
    A machine consumer selecting it would be reading provider-controlled text
    into a reasoning path, so selection is refused rather than sanitized.
    """

    profile = get_projection_profile(profile_id)
    if not profile.machine_consumption_permitted:
        raise ProjectionProfileError(
            f"projection_profile_not_machine_consumable:{profile_id}"
        )
    return profile


def projection_registry_identity() -> dict[str, Any]:
    """A reconstructable identity for the whole contract floor."""
    profiles = load_projection_profiles()
    return {
        "registry_version": REGISTRY_VERSION,
        "profiles": {
            profile_id: {
                "profile_version": profile.profile_version,
                "profile_hash": profile.profile_hash,
                "field_count": len(profile.fields),
                "untrusted_labels_admitted": profile.untrusted_labels_admitted,
                "policy_authority_projection": profile.policy_authority_projection,
                "judge_authority": profile.judge_authority,
                "max_action_authority": profile.max_action_authority,
            }
            for profile_id, profile in sorted(profiles.items())
        },
    }
