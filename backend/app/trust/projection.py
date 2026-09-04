"""B2.5-P14 downstream projection of a signed TrustEnvelope.

This is the only lawful way a P14 consumer obtains source truth. It is a pure
function of (envelope, profile): no database read, no clock, no configuration,
so a projection is reproducible from the artifact identity alone -- which is
what Gate 12's reconstruction requirement needs.

Three properties are enforced here rather than asserted elsewhere:

* **Allowlist, not denylist.** A field absent from the profile is absent from
  the projection. Adding a field to the TrustEnvelope schema therefore cannot
  silently widen a downstream surface; it has to be added to a profile, which
  changes that profile's content-addressed hash.
* **No semantic mutation.** A projected value is the source value, copied. The
  projection never rounds, re-derives, re-buckets or re-words. Money stays an
  integer in minor units; a float anywhere on this path is refused rather than
  coerced, because a float that reaches here has already lost the property the
  money contract exists to preserve.
* **Positions travel with values.** The result carries, per field, the position
  the profile authorized. A consumer that seats a value in a stronger position
  than the projection declares is violating P14-G2/G3 in a way the projection
  itself makes visible -- ``authority_positions`` is the evidence, not a
  comment.
"""

from __future__ import annotations

from dataclasses import dataclass, field as dataclass_field
from typing import Any, Mapping

from app.trust.projection_profiles import (
    UNTRUSTED_TEXT_CLASSES,
    ProjectionProfile,
    ProjectionProfileError,
    get_machine_projection_profile,
    get_projection_profile,
    policy_state_authority_rank,
)


class TrustProjectionError(ValueError):
    """Raised when a TrustEnvelope cannot be projected without inventing truth."""


@dataclass(frozen=True)
class TrustProjection:
    """A downstream-safe view of one signed TrustEnvelope."""

    profile_id: str
    profile_version: str
    profile_hash: str
    envelope_id: str
    tenant_id_hash: str
    semantic_truth_hash: str
    source_policy_state: str
    projected: Mapping[str, Any]
    authority_positions: Mapping[str, str]
    untrusted_label_paths: tuple[str, ...] = dataclass_field(default=())

    @property
    def profile_identity(self) -> str:
        return f"{self.profile_id}@{self.profile_version}"

    def value(self, path: str) -> Any:
        """Return a projected value, refusing paths the profile excluded."""
        if path not in self.projected:
            raise TrustProjectionError(f"projection_path_absent:{path}")
        return self.projected[path]

    def has(self, path: str) -> bool:
        return path in self.projected


def _resolve(payload: Mapping[str, Any], path: str) -> tuple[bool, Any]:
    """Resolve a dotted source path, distinguishing absent from null."""
    current: Any = payload
    for segment in path.split("."):
        if not isinstance(current, Mapping) or segment not in current:
            return False, None
        current = current[segment]
    return True, current


def _assert_no_float(path: str, value: Any) -> None:
    """Refuse IEEE-754 anywhere on an authoritative projection path.

    H-RC7. A type annotation is not proof; a float that arrived from a display
    layer is indistinguishable from one that arrived from a solver, so the
    boundary refuses the type outright rather than inspecting its provenance.
    """

    if isinstance(value, float):
        raise TrustProjectionError(f"projection_float_forbidden:{path}")
    if isinstance(value, list):
        for item in value:
            _assert_no_float(path, item)
    elif isinstance(value, Mapping):
        for item in value.values():
            _assert_no_float(path, item)


def project_trust_envelope(
    envelope: Mapping[str, Any],
    *,
    profile_id: str,
    machine_consumer: bool = True,
) -> TrustProjection:
    """Project a signed TrustEnvelope through one versioned P14 profile."""
    if not isinstance(envelope, Mapping):
        raise TrustProjectionError("projection_source_not_object")

    profile: ProjectionProfile
    try:
        profile = (
            get_machine_projection_profile(profile_id)
            if machine_consumer
            else get_projection_profile(profile_id)
        )
    except ProjectionProfileError as exc:
        raise TrustProjectionError(str(exc)) from exc

    for required in ("envelope_id", "tenant_id_hash", "semantic_truth_hash"):
        if not isinstance(envelope.get(required), str) or not envelope[required]:
            # Source Trust identity is a precondition of projection, not an
            # optional decoration: an artifact that cannot name its source is
            # not a projection of anything.
            raise TrustProjectionError(f"projection_source_identity_missing:{required}")

    policy_authority = envelope.get("policy_action_authority")
    if not isinstance(policy_authority, Mapping):
        raise TrustProjectionError("projection_source_policy_authority_missing")
    source_policy_state = policy_authority.get("policy_state")
    if not isinstance(source_policy_state, str):
        raise TrustProjectionError("projection_source_policy_state_missing")
    # Fails closed on an unknown state rather than passing it through as text.
    policy_state_authority_rank(source_policy_state)

    projected: dict[str, Any] = {}
    positions: dict[str, str] = {}
    untrusted_paths: list[str] = []

    for spec in profile.fields:
        present, value = _resolve(envelope, spec.path)
        if not present:
            # An optional source field that is absent stays absent. The
            # projection never substitutes a default, because a default is an
            # invented fact wearing the shape of a real one.
            continue
        _assert_no_float(spec.path, value)
        projected[spec.path] = value
        positions[spec.path] = spec.position
        if spec.trust_class in UNTRUSTED_TEXT_CLASSES:
            untrusted_paths.append(spec.path)

    if untrusted_paths and not profile.untrusted_labels_admitted:
        raise TrustProjectionError(
            f"projection_untrusted_label_leaked:{profile.profile_id}:{untrusted_paths}"
        )

    return TrustProjection(
        profile_id=profile.profile_id,
        profile_version=profile.profile_version,
        profile_hash=profile.profile_hash,
        envelope_id=str(envelope["envelope_id"]),
        tenant_id_hash=str(envelope["tenant_id_hash"]),
        semantic_truth_hash=str(envelope["semantic_truth_hash"]),
        source_policy_state=source_policy_state,
        projected=dict(projected),
        authority_positions=dict(positions),
        untrusted_label_paths=tuple(untrusted_paths),
    )


def assert_authority_monotonic(
    *,
    source_policy_state: str,
    downstream_policy_state: str,
) -> None:
    """Refuse a downstream state stronger than its source (P14 §0.2).

    Equality and reduction are lawful; escalation is not. The comparison is over
    the declared authority order rather than over string identity, so
    ``simulation_only -> read_only`` passes and ``simulation_only ->
    approval_required`` does not.
    """

    source_rank = policy_state_authority_rank(source_policy_state)
    downstream_rank = policy_state_authority_rank(downstream_policy_state)
    if downstream_rank > source_rank:
        raise TrustProjectionError(
            "authority_escalation_forbidden:"
            f"{source_policy_state}->{downstream_policy_state}"
        )
