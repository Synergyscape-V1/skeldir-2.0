"""B2.5-P13 C8 canonical model-identity authority.

`model_type` and `model_version` were carrying two different concepts in one
pair of columns. A dirty event populated them as *the scope of a source change*;
the Trust confidence read model consumed them as *the identity of the fit
authority that change affects*. Because the two were never reconciled, source
invalidation and signed confidence ran in disjoint identity domains:

    triggers / dirty producers  ->  ('mmm', 'b24-p3-orchestration-v1')
    Trust read model accepts    ->   'bayesian_attribution_confidence'
    freshness predicates        ->   exact equality on both columns

so no committed source change could ever make a Trust-projectable fit stale.

This module is the single authority that resolves that. It declares what each
identifier semantically names, which identity production must emit, which
identities Trust may project, and which are retired. Nothing downstream is
permitted to invent an identity by defaulting a parameter.

Semantics, stated once:

    model_type      the statistical model FAMILY. It selects which feature
                    dimensions the fit may use (see model_family_contract) and
                    therefore which source columns are decision-relevant.

    model_version   the version of the PRODUCING PIPELINE for that family. It
                    identifies how a fit was computed, not what it is about.

A source change is scoped by tenant, family and time interval. It is deliberately
NOT scoped by model_version: a change to the underlying financial truth
invalidates an affected fit regardless of which pipeline version produced it.
That is why staleness joins on family and window overlap, never on pipeline
version -- see ``b24_dirty_event_stales_fit`` in the C8 migration.
"""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType


MODEL_IDENTITY_REGISTRY_VERSION = "b25-p13-c8-model-identity-v1"


@dataclass(frozen=True)
class ModelIdentity:
    """One governed (family, pipeline) identity and everything it authorises."""

    model_type: str
    model_version: str
    status: str  # "active" | "retired"
    trust_eligible: bool
    purpose: str

    @property
    def is_active(self) -> bool:
        return self.status == "active"


# The one statistical family Skeldir produces confidence for. `model_spec` names
# the same pair as the real B2.4-P6 fit specification; this registry is what
# makes that binding authoritative rather than coincidental.
CONFIDENCE_MODEL_TYPE = "bayesian_attribution_confidence"
CONFIDENCE_MODEL_VERSION = "b24-p6-real-fit-v1"

# Retired. `mmm` was the B2.4-P3 orchestration-era default on
# ``append_dirty_event`` and was never migrated when P6 introduced the real
# model specification. It is registered so historical rows remain legal and so
# the identity is named rather than merely absent -- it is NOT Trust-eligible
# and production may not emit it.
LEGACY_ORCHESTRATION_MODEL_TYPE = "mmm"
LEGACY_ORCHESTRATION_MODEL_VERSION = "b24-p3-orchestration-v1"

MODEL_IDENTITY_REGISTRY: tuple[ModelIdentity, ...] = (
    ModelIdentity(
        model_type=CONFIDENCE_MODEL_TYPE,
        model_version=CONFIDENCE_MODEL_VERSION,
        status="active",
        trust_eligible=True,
        purpose=(
            "B2.4 Bayesian attribution confidence. Produced by the real P6 fit "
            "worker, projected by the Trust confidence read model, and the "
            "identity every source-invalidation obligation must resolve to."
        ),
    ),
    ModelIdentity(
        model_type=LEGACY_ORCHESTRATION_MODEL_TYPE,
        model_version=LEGACY_ORCHESTRATION_MODEL_VERSION,
        status="retired",
        trust_eligible=False,
        purpose=(
            "B2.4-P3 orchestration-era dirty-marker default. Retired by C8: it "
            "named no statistical authority Trust could consume, so every "
            "obligation carrying it terminated in a fit the read model refused. "
            "Registered so pre-C8 rows stay legal and the identity is governed "
            "rather than merely unused."
        ),
    ),
)

_BY_TYPE = MappingProxyType(
    {identity.model_type: identity for identity in MODEL_IDENTITY_REGISTRY}
)


class ModelIdentityError(ValueError):
    """An identity was used outside the authority this registry grants it."""


def registered_model_types() -> tuple[str, ...]:
    """Every family the database is permitted to store, active or retired."""

    return tuple(sorted(_BY_TYPE))


def active_identity() -> ModelIdentity:
    """The single identity production is permitted to newly emit."""

    active = [item for item in MODEL_IDENTITY_REGISTRY if item.is_active]
    if len(active) != 1:
        raise ModelIdentityError(
            "exactly one active model identity is supported; found "
            + ",".join(item.model_type for item in active)
        )
    return active[0]


def trust_eligible_model_types() -> frozenset[str]:
    """Families the Trust confidence projection may serve."""

    return frozenset(
        identity.model_type
        for identity in MODEL_IDENTITY_REGISTRY
        if identity.trust_eligible
    )


def resolve(model_type: str) -> ModelIdentity:
    try:
        return _BY_TYPE[model_type]
    except KeyError as exc:
        raise ModelIdentityError(
            f"unregistered model identity: {model_type!r}; register it in "
            "MODEL_IDENTITY_REGISTRY before producing or projecting it"
        ) from exc


def assert_producible(model_type: str, model_version: str) -> None:
    """Fail closed when production would emit a non-active identity.

    A retired family may exist in historical rows and may still be read. It may
    never be newly produced, because an obligation carrying it can never reach
    a fit the Trust read model will project.
    """

    identity = resolve(model_type)
    if not identity.is_active:
        raise ModelIdentityError(
            f"model identity {model_type!r} is {identity.status}; production "
            f"must emit {active_identity().model_type!r}"
        )
    if model_version != identity.model_version:
        raise ModelIdentityError(
            f"model_version {model_version!r} is not the governed pipeline "
            f"version for {model_type!r} (expected {identity.model_version!r})"
        )
