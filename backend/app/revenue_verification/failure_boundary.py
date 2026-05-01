"""B2.3-P2 failure-boundary classification and durable outcome contract."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum


class B23FailureBoundaryClass(str, Enum):
    UNAUTHENTICATED_MALFORMED_WEBHOOK = "unauthenticated_malformed_webhook"
    AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD = (
        "authenticated_malformed_canonical_payload"
    )
    VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY = (
        "valid_post_capture_unresolved_order_identity"
    )
    UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE = (
        "unsupported_authenticated_provider_event_type"
    )


@dataclass(frozen=True)
class B23FailureBoundaryDecision:
    boundary_class: B23FailureBoundaryClass
    durable_outcome: str
    b23_authority_allowed: bool
    requires_exception_record: bool
    requires_ingestion_failure_telemetry: bool


_BOUNDARY_DECISIONS: dict[B23FailureBoundaryClass, B23FailureBoundaryDecision] = {
    B23FailureBoundaryClass.UNAUTHENTICATED_MALFORMED_WEBHOOK: B23FailureBoundaryDecision(
        boundary_class=B23FailureBoundaryClass.UNAUTHENTICATED_MALFORMED_WEBHOOK,
        durable_outcome="b22_auth_rejection_or_failure_telemetry",
        b23_authority_allowed=False,
        requires_exception_record=False,
        requires_ingestion_failure_telemetry=False,
    ),
    B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD: B23FailureBoundaryDecision(
        boundary_class=B23FailureBoundaryClass.AUTHENTICATED_MALFORMED_CANONICAL_PAYLOAD,
        durable_outcome="durable_ingestion_failure_telemetry",
        b23_authority_allowed=False,
        requires_exception_record=False,
        requires_ingestion_failure_telemetry=True,
    ),
    B23FailureBoundaryClass.VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY: B23FailureBoundaryDecision(
        boundary_class=B23FailureBoundaryClass.VALID_POST_CAPTURE_UNRESOLVED_ORDER_IDENTITY,
        durable_outcome="b23_exception_plus_ingestion_failure",
        b23_authority_allowed=False,
        requires_exception_record=True,
        requires_ingestion_failure_telemetry=True,
    ),
    B23FailureBoundaryClass.UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE: B23FailureBoundaryDecision(
        boundary_class=B23FailureBoundaryClass.UNSUPPORTED_AUTHENTICATED_PROVIDER_EVENT_TYPE,
        durable_outcome="durable_ingestion_failure_telemetry_or_exception",
        b23_authority_allowed=False,
        requires_exception_record=False,
        requires_ingestion_failure_telemetry=True,
    ),
}


def classify_b23_failure_boundary(
    boundary_class: B23FailureBoundaryClass,
) -> B23FailureBoundaryDecision:
    return _BOUNDARY_DECISIONS[boundary_class]
