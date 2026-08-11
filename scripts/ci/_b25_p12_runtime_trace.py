#!/usr/bin/env python3
"""Fresh-interpreter runtime module trace for B2.5-P12 domain 17.

Why a separate process
----------------------
The previous in-process trace captured its ``sys.modules`` baseline *after*
importing the trust modules it was observing::

    from app.trust.signing import sign_trust_envelope   # forbidden dep loads here
    ...
    before = set(sys.modules)                           # too late to see it
    newly_loaded = set(sys.modules) - before            # always misses it

That construction can only observe *lazy* imports performed during the exercised
calls. A forbidden module pulled in as an import-time transitive dependency is
already resident when the baseline is taken, so it is subtracted away. This was
reproduced: a trust module importing ``app.llm`` at import time left the trace
reporting success while ``app.llm`` was demonstrably in ``sys.modules``.

A fresh interpreter is the cheapest construction that makes the baseline
genuinely precede every first-party import, so import-time and lazy loads are
both observable. The trace emits JSON on stdout for the parent validator.

Environmental stubs
-------------------
The builder paths take a database session. The property under proof here is
*which modules load*, not database behaviour, so an inert session stub is
legitimate under the directive's rule that mocking is permissible when the
mocked dependency is not the property under proof. Route-level and RLS-level
truth is proven by the P13 end-to-end harness against real PostgreSQL, not here.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

FORBIDDEN_MODULE_PREFIXES = (
    "app.llm",
    "app.workers.llm",
    "app.tasks.bayesian",
    "app.bayesian",
)


def _is_forbidden(module: str) -> bool:
    return any(
        module == prefix or module.startswith(prefix + ".")
        for prefix in FORBIDDEN_MODULE_PREFIXES
    )


def _utc(value):
    return (
        value.astimezone(_tz.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
    )


def main() -> int:
    # The baseline is captured before ANY first-party import, which is the whole
    # point of this process existing.
    baseline = set(sys.modules)

    sys.path.insert(0, str(BACKEND))

    import hashlib
    from datetime import datetime, timedelta, timezone

    global _tz
    _tz = timezone

    from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

    from app.trust.export_artifact import (
        build_export_artifact,
        sign_export_artifact,
        verify_export_artifact,
    )
    from app.trust.key_registry import TrustKeyRegistry, TrustSigningKey
    from app.trust.signing import sign_trust_envelope
    from app.trust.verification import verify_trust_envelope

    private = Ed25519PrivateKey.from_private_bytes(
        hashlib.sha256(b"b25-p12-runtime-trace").digest()
    )
    registry = TrustKeyRegistry(
        (
            TrustSigningKey(
                kid="kid:b25-p12-runtime-trace",
                algorithm="ed25519",
                public_key=private.public_key(),
                private_key=private,
                state="active",
                valid_from=datetime(2026, 1, 1, tzinfo=timezone.utc),
            ),
        )
    )

    issued = datetime.now(timezone.utc)
    envelope = json.loads(
        (
            ROOT / "contracts/trust-api/examples/deterministic_only_verified.json"
        ).read_text(encoding="utf-8")
    )
    envelope["created_at"] = _utc(issued)
    envelope["valid_until"] = _utc(issued + timedelta(days=1))

    executed: list[str] = []

    signed = sign_trust_envelope(envelope, key_registry=registry)
    executed.append("sign_envelope")

    verify_trust_envelope(signed, key_registry=registry.public_only())
    executed.append("verify_envelope")

    artifact = sign_export_artifact(
        build_export_artifact(
            envelopes=[signed],
            tenant_id_hash=str(signed["tenant_id_hash"]),
            generated_at=issued,
        ),
        key_registry=registry,
    )
    executed.append("export_issuance")

    tampered = dict(artifact)
    tampered["generated_at"] = _utc(issued + timedelta(hours=1))
    if verify_export_artifact(
        tampered, key_registry=registry.public_only()
    ).verification_status != "rejected":
        return _emit(baseline, executed, error="tamper_not_rejected")
    executed.append("tampered_artifact_rejection")

    unsupported = dict(artifact)
    unsupported["artifact_schema_version"] = "b25-p11-export-artifact-v9"
    unsupported["canonicalization_version"] = "b25-p11-artifact-framing-v9"
    if verify_export_artifact(
        unsupported, key_registry=registry.public_only()
    ).verification_status != "rejected":
        return _emit(baseline, executed, error="unsupported_not_rejected")
    executed.append("unsupported_protocol_refusal")

    # Builder construction paths. The five cryptographic cases above exercise
    # signing, verification and export, but none of them runs the TrustEnvelope
    # *construction* path -- which is where confidence, money and reason-code
    # semantics live, and therefore where a forbidden Bayesian or LLM import is
    # most plausible. Claiming "representative trust runtime paths" while
    # exercising only crypto would inflate five counters into five semantics.
    #
    # The session is inert and raises on any access, so these paths are proven
    # not to touch the database. That is legitimate here because the property
    # under proof is which modules load, not database behaviour; route-level and
    # RLS truth belong to the P13 end-to-end harness against real PostgreSQL.
    import asyncio
    import uuid

    from app.trust.builder import (
        TrustEnvelopeBuildRequest,
        build_unsigned_trust_envelope,
    )
    from app.trust.source_adapters import MatchVerdictSource

    class _InertSession:
        async def execute(self, *args, **kwargs):
            raise AssertionError("runtime trace builder path touched the database")

        async def scalar(self, *args, **kwargs):
            raise AssertionError("runtime trace builder path touched the database")

    def _source(amount):
        now = datetime.now(timezone.utc)
        return MatchVerdictSource(
            id=uuid.uuid4(),
            tenant_id=uuid.uuid4(),
            webhook_ingress_identity_id=None,
            provider="stripe",
            canonical_commerce_reference="cc-runtime-trace",
            provider_native_event_reference="evt_runtime_trace",
            provider_native_commerce_reference="pi_runtime_trace",
            status="matched",
            match_quality="exact",
            canonical_net_verified_amount_minor=amount,
            currency_code="USD",
            last_transition_at=now,
            created_at=now,
            updated_at=now,
        )

    async def _build(amount):
        request = TrustEnvelopeBuildRequest(
            tenant_id=uuid.uuid4(),
            subject_type="commerce_event",
            subject_ref="cc-runtime-trace",
            request_context={"audience_id": "b25-p12-runtime-trace"},
        )
        return await build_unsigned_trust_envelope(
            _InertSession(), request, source=_source(amount)
        )

    asyncio.run(_build(105000))
    executed.append("builder_normal_read")

    # Money authority unavailable: the degraded construction branch, which must
    # stay deterministic rather than reaching for a probabilistic estimate.
    asyncio.run(_build(None))
    executed.append("builder_degraded_money_unavailable")

    return _emit(baseline, executed)


def _emit(baseline: set[str], executed: list[str], error: str | None = None) -> int:
    loaded = sorted(m for m in set(sys.modules) - baseline if _is_forbidden(m))
    json.dump(
        {
            "executed_paths": executed,
            "forbidden_modules_loaded": loaded,
            "error": error,
        },
        sys.stdout,
    )
    sys.stdout.write("\n")
    return 1 if (loaded or error) else 0


if __name__ == "__main__":
    raise SystemExit(main())
