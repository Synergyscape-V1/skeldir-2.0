"""B2.6-P2 Corrective XXV sovereign source-money attestation.

Why this module exists
----------------------
Every pre-XXV protection over "the amount the provider actually sent" lived
*inside* the database: an immutability trigger on the authenticated ingress
row, an append-only attribution event, a supersession ledger, and a
conservation function that compares those rows to each other. All of them are
owned by ``migration_owner`` -- the login the repository's own runbook uses to
apply migrations -- which may ``ALTER TABLE ... NO FORCE ROW LEVEL SECURITY``,
``DISABLE TRIGGER USER`` and ``CREATE OR REPLACE FUNCTION`` at will. Both
independent XXIV audits used exactly that capability to rewrite three agreeing
representations and have the reconciliation API serve the forged figure as
current money, while the governing composition proof printed PASS.

Agreement among rows one principal can rewrite is not evidence. So the
authority for "this is the provider's amount" is moved out of the database:

1. The authentication root -- the only process that ever sees the provider's
   signed bytes, running as ``app_ingress`` -- signs a canonical statement
   over the amount, currency, scale, tenant, source identity, event instant
   and body digest, in the same transaction that persists the authenticated
   ingress row. The Ed25519 seed is mounted into that process only.
2. The statement and its signature are stored next to the ingress row. A
   maintenance principal may still rewrite or delete that row -- and it gains
   nothing, because it cannot produce a signature for a different amount.
3. Every authoritative reader verifies the signature against a public key
   whose SHA-256 fingerprint is **compiled into the deployed image**, so
   swapping the key file on disk is refused as well. Rebuilding the image is a
   different principal in a different frame (directive XXV section 4.3).

Inside/outside frame (directive XXV section 8.1)
-----------------------------------------------
* Outside the frame of ``migration_owner`` and of the platform superuser:
  neither holds the attestation seed, and neither can rebuild the compiled
  anchor in the running image.
* Inside the frame of the deployment-image builder and the attestation key
  custodian: those principals are the declared root, exactly as the historical
  witness anchor's builder is.

Predecessor generations
-----------------------
Rows authenticated before the XXV watermark cannot be retro-attested: no key
existed when they were authenticated, and the provider's signed bytes are not
retained (only their digest), so the amount cannot be re-derived from provider
evidence either. They are therefore reported as unqualified
(``unverifiable:attestation_missing``) rather than as current finance, and
the signed path refuses them. An earlier revision granted them a
"predecessor generation" exemption keyed to a watermark row; that exemption
was owner-controlled and has been removed -- see the note on
``read_verdict_source_attestation_status`` and the falsifier
``xxv-hb03-predecessor-escape``. The residual is recorded as a
DEVIATION-FOR-AUDIT with its physical reason; the supported remedy for
inherited data is provider replay, which re-authenticates the events through
the shipping surface and produces ordinary attestations.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

#: Statement version. A change in the signed field set requires a bump, and a
#: statement whose version this build does not know is refused rather than
#: interpreted.
ATTESTATION_STATEMENT_VERSION = 1

#: The signed fields, in the exact order the canonical form serialises them.
ATTESTATION_FIELDS = (
    "authority_universe",
    "body_sha256",
    "event_timestamp",
    "normalized_commerce_reference_kind",
    "normalized_commerce_reference_value",
    "provider",
    "provider_native_commerce_reference",
    "provider_native_event_reference",
    "tenant_id",
    "verified_amount_currency",
    "verified_amount_minor",
    "verified_amount_scale",
    "version",
    "webhook_ingress_identity_id",
)

DEFAULT_ATTESTATION_KEY_ID = "kid:b26-p2-source-attestation-v1"

#: Machine-readable attestation outcomes. ``unverifiable:<reason>`` is the only
#: shape a failure may take, so no consumer can mistake a failure for a state.
#: XXV: the predecessor-generation exemption is GONE. ``STATUS_PREDECESSOR`` now
#: means only "attestation enforcement is disabled by configuration", which
#: production refuses to start with -- it is not a currency grant.
STATUS_ATTESTED = "xxv_attested"
STATUS_PREDECESSOR = "attestation_not_required_by_configuration"
STATUS_UNVERIFIABLE_PREFIX = "unverifiable"


class SourceAttestationError(ValueError):
    """Governed refusal while signing or verifying a source attestation."""


@dataclass(frozen=True)
class SourceAttestationStatus:
    """One reader's verdict about one financial fact's source authority."""

    status: str
    reason: str
    attested_amount_minor: int | None
    attested_currency: str | None
    key_sha256: str | None

    @property
    def attested(self) -> bool:
        return self.status == STATUS_ATTESTED

    @property
    def unverifiable(self) -> bool:
        return self.status.startswith(STATUS_UNVERIFIABLE_PREFIX)

    def external_projection(self) -> dict[str, object]:
        return {
            "source_attestation_status": self.status,
            "source_attestation_reason": self.reason,
        }


def _b64u_encode(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def _b64u_decode(value: str) -> bytes:
    padding = "=" * (-len(value) % 4)
    return base64.urlsafe_b64decode(value + padding)


def canonical_statement_bytes(statement: Mapping[str, Any]) -> bytes:
    """Deterministic signing material: sorted keys, no insignificant bytes."""
    missing = [field for field in ATTESTATION_FIELDS if field not in statement]
    if missing:
        raise SourceAttestationError(
            f"attestation_statement_incomplete:{','.join(sorted(missing))}"
        )
    unknown = sorted(set(statement) - set(ATTESTATION_FIELDS))
    if unknown:
        raise SourceAttestationError(
            f"attestation_statement_unknown_fields:{','.join(unknown)}"
        )
    return json.dumps(
        {field: statement[field] for field in ATTESTATION_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def public_key_fingerprint_from_raw(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


#: Parsed signing keys by path. The auth root signs every authenticated fact;
#: re-reading and decoding the mounted seed per request added avoidable disk
#: work to the 46 rps profile. The stat identity invalidates on rotation.
_PRIVATE_KEY_CACHE: dict[str, tuple[int, int, object]] = {}


def load_private_key(path: str | os.PathLike[str]):
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PrivateKey,
    )

    key_path = Path(path)
    cache_key = str(key_path)
    try:
        before_path = key_path.stat()
        cached = _PRIVATE_KEY_CACHE.get(cache_key)
        if (
            cached is not None
            and cached[0] == before_path.st_size
            and cached[1] == before_path.st_mtime_ns
        ):
            return cached[2]
        for _attempt in range(3):
            with key_path.open("rb") as handle:
                before = os.fstat(handle.fileno())
                data = handle.read()
                after = os.fstat(handle.fileno())
            if (
                before.st_ino == after.st_ino
                and before.st_size == after.st_size
                and before.st_mtime_ns == after.st_mtime_ns
            ):
                break
        else:
            raise SourceAttestationError("attestation_private_key_changed_during_read")
        raw = _b64u_decode(data.decode("utf-8").strip())
    except (OSError, ValueError) as exc:
        raise SourceAttestationError("attestation_private_key_unreadable") from exc
    if len(raw) != 32:
        raise SourceAttestationError("attestation_private_key_wrong_length")
    private_key = Ed25519PrivateKey.from_private_bytes(raw)
    _PRIVATE_KEY_CACHE[cache_key] = (
        after.st_size,
        after.st_mtime_ns,
        private_key,
    )
    return private_key


def load_public_key_raw(path: str | os.PathLike[str]) -> bytes:
    try:
        raw = _b64u_decode(Path(path).read_text(encoding="utf-8").strip())
    except (OSError, ValueError) as exc:
        raise SourceAttestationError("attestation_public_key_unreadable") from exc
    if len(raw) != 32:
        raise SourceAttestationError("attestation_public_key_wrong_length")
    return raw


def generate_keypair() -> tuple[str, str]:
    """Create an attestation keypair as (private_seed_b64url, public_b64url)."""
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PrivateKey,
    )

    private_key = Ed25519PrivateKey.generate()
    private_raw = private_key.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return _b64u_encode(private_raw), _b64u_encode(public_raw)


def build_statement(
    *,
    tenant_id: UUID | str,
    webhook_ingress_identity_id: UUID | str,
    provider: str,
    provider_native_event_reference: str,
    provider_native_commerce_reference: str,
    normalized_commerce_reference_kind: str | None,
    normalized_commerce_reference_value: str | None,
    verified_amount_minor: int,
    verified_amount_currency: str,
    verified_amount_scale: int,
    event_timestamp: datetime | str,
    body_sha256: str,
    authority_universe: str | None,
) -> dict[str, Any]:
    if isinstance(event_timestamp, datetime):
        instant = event_timestamp
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        event_value = (
            instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        )
    else:
        event_value = str(event_timestamp)
    return {
        "version": ATTESTATION_STATEMENT_VERSION,
        "tenant_id": str(tenant_id),
        "webhook_ingress_identity_id": str(webhook_ingress_identity_id),
        "provider": str(provider),
        "provider_native_event_reference": str(provider_native_event_reference),
        "provider_native_commerce_reference": str(
            provider_native_commerce_reference
        ),
        "normalized_commerce_reference_kind": (
            None
            if normalized_commerce_reference_kind is None
            else str(normalized_commerce_reference_kind)
        ),
        "normalized_commerce_reference_value": (
            None
            if normalized_commerce_reference_value is None
            else str(normalized_commerce_reference_value)
        ),
        "verified_amount_minor": int(verified_amount_minor),
        "verified_amount_currency": str(verified_amount_currency),
        "verified_amount_scale": int(verified_amount_scale),
        "event_timestamp": event_value,
        "body_sha256": str(body_sha256).lower(),
        "authority_universe": (
            None if authority_universe is None else str(authority_universe)
        ),
    }


def sign_statement(
    statement: Mapping[str, Any], *, private_key_path: str | os.PathLike[str]
) -> tuple[str, str]:
    """Sign one statement. Returns (signature, public_key_sha256)."""
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415

    private_key = load_private_key(private_key_path)
    signature = private_key.sign(canonical_statement_bytes(statement))
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        f"ed25519:{_b64u_encode(signature)}",
        public_key_fingerprint_from_raw(public_raw),
    )


def compiled_attestation_anchor() -> str | None:
    from app.trust.witness_anchor import (  # noqa: PLC0415
        COMPILED_SOURCE_ATTESTATION_PUBLIC_KEY_SHA256,
    )

    return COMPILED_SOURCE_ATTESTATION_PUBLIC_KEY_SHA256


def verify_signature(
    statement: Mapping[str, Any],
    signature: str,
    *,
    public_key_path: str | os.PathLike[str],
) -> str:
    """Verify one statement signature. Returns the verifying key fingerprint.

    The key on disk must match the fingerprint compiled into this image
    whenever the image carries one. That comparison is unconditional: an
    environment predicate here would be the same defect class that disabled
    the historical-root guard for all of corrective XXIV.
    """
    from cryptography.exceptions import InvalidSignature  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PublicKey,
    )

    if int(statement.get("version", 0)) != ATTESTATION_STATEMENT_VERSION:
        raise SourceAttestationError(
            f"attestation_statement_version_unsupported:{statement.get('version')}"
        )
    raw_public = load_public_key_raw(public_key_path)
    fingerprint = public_key_fingerprint_from_raw(raw_public)
    anchor = compiled_attestation_anchor()
    if anchor and fingerprint != anchor:
        raise SourceAttestationError("attestation_key_not_anchored")
    if not signature.startswith("ed25519:"):
        raise SourceAttestationError("attestation_signature_algorithm_unsupported")
    try:
        Ed25519PublicKey.from_public_bytes(raw_public).verify(
            _b64u_decode(signature.split(":", 1)[1]),
            canonical_statement_bytes(statement),
        )
    except InvalidSignature as exc:
        raise SourceAttestationError("attestation_signature_invalid") from exc
    except Exception as exc:  # noqa: BLE001 - malformed signature material
        raise SourceAttestationError("attestation_signature_unreadable") from exc
    return fingerprint


async def write_source_attestation(
    session: AsyncSession,
    *,
    statement: Mapping[str, Any],
    private_key_path: str | os.PathLike[str],
    key_id: str = DEFAULT_ATTESTATION_KEY_ID,
) -> dict[str, object]:
    """Persist one attestation inside the caller's transaction.

    Written by the authentication root only; the database grants INSERT on the
    attestation table to ``app_ingress`` alone, so no other runtime principal
    can author one even with a key.
    """
    signature, key_sha256 = sign_statement(
        statement, private_key_path=private_key_path
    )
    await session.execute(
        text(
            "INSERT INTO public.b26_p2_source_money_attestation ("
            " webhook_ingress_identity_id, tenant_id, statement_version,"
            " attested_amount_minor, attested_amount_currency,"
            " attested_amount_scale, statement, signature, key_id, key_sha256"
            ") VALUES (:id, :tenant, :version, :amount, :currency,"
            " :scale, CAST(:statement AS jsonb), :signature, :key_id,"
            " :key_sha256)"
            " ON CONFLICT (webhook_ingress_identity_id) DO NOTHING"
        ),
        {
            "id": statement["webhook_ingress_identity_id"],
            "tenant": statement["tenant_id"],
            "version": int(statement["version"]),
            "amount": int(statement["verified_amount_minor"]),
            "currency": statement["verified_amount_currency"],
            "scale": int(statement["verified_amount_scale"]),
            "statement": json.dumps(dict(statement), sort_keys=True),
            "signature": signature,
            "key_id": key_id,
            "key_sha256": key_sha256,
        },
    )
    from app.revenue_verification.source_evidence_journal import (
        SourceFactJournalError,
        append_source_fact,
    )

    # The transaction identity is only consumed by the append-only journal.
    # Lanes without a journal (for example the R3 ingestion profile) must not
    # pay an extra database round trip per authenticated amount.
    if not (os.getenv("B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH") or "").strip():
        return {
            "webhook_ingress_identity_id": statement[
                "webhook_ingress_identity_id"
            ],
            "signature": signature,
            "key_sha256": key_sha256,
            "key_id": key_id,
        }

    transaction_id = (
        await session.execute(text("SELECT pg_current_xact_id()::text"))
    ).scalar_one_or_none()
    if transaction_id is None:
        raise SourceAttestationError(
            "attestation_transaction_identity_missing"
        )
    try:
        append_source_fact(
            fact_kind="source_money",
            fact_id=str(statement["webhook_ingress_identity_id"]),
            tenant_id=str(statement["tenant_id"]),
            verdict_id="",
            statement=statement,
            signature=signature,
            key_sha256=key_sha256,
            database_transaction_id=str(transaction_id),
        )
    except SourceFactJournalError as exc:
        raise SourceAttestationError(str(exc)) from exc
    return {
        "webhook_ingress_identity_id": statement["webhook_ingress_identity_id"],
        "signature": signature,
        "key_sha256": key_sha256,
        "key_id": key_id,
    }


_VERDICT_SOURCE_SQL = """
SELECT v.canonical_net_verified_amount_minor AS verdict_net,
       v.canonical_captured_gross_amount_minor AS verdict_captured,
       v.verified_amount_minor AS verdict_verified,
       v.currency_code AS verdict_currency,
       v.provider AS verdict_provider,
       v.provider_native_event_reference AS verdict_event_reference,
       v.provider_native_commerce_reference AS verdict_commerce_reference,
       v.webhook_ingress_identity_id AS ingress_id,
       i.verified_amount_minor AS ingress_amount,
       i.verified_amount_currency AS ingress_currency,
       i.verified_amount_scale AS ingress_scale,
       i.provider AS ingress_provider,
       i.provider_native_event_reference AS ingress_event_reference,
       i.provider_native_commerce_reference AS ingress_commerce_reference,
       i.normalized_commerce_reference_kind AS ingress_normalized_kind,
       i.normalized_commerce_reference_value AS ingress_normalized_value,
       i.event_timestamp AS ingress_event_timestamp,
       i.created_at AS ingress_created_at,
       c.body_sha256 AS consequence_body_sha256,
       a.statement AS statement,
       a.signature AS signature,
       a.attested_amount_minor AS attested_amount,
       a.attested_amount_currency AS attested_currency,
       a.key_sha256 AS key_sha256,
       c.recorded_by AS consequence_recorded_by
  FROM public.b23_match_verdicts AS v
  LEFT JOIN public.webhook_ingress_identities AS i
         ON i.id = v.webhook_ingress_identity_id
        AND i.tenant_id = v.tenant_id
  LEFT JOIN public.b26_p2_source_money_attestation AS a
         ON a.webhook_ingress_identity_id = i.id
        AND a.tenant_id = i.tenant_id
  LEFT JOIN public.b26_p2_provider_auth_consequence AS c
         ON c.webhook_ingress_identity_id = i.id
        AND c.tenant_id = i.tenant_id
 WHERE v.tenant_id = :tenant_id AND v.id = :verdict_id
"""


_VERDICT_ADJUSTMENT_SQL = """
SELECT e.id::text AS adjustment_evidence_id,
       e.tenant_id::text AS tenant_id,
       e.verdict_id::text AS verdict_id,
       e.provider,
       e.event_type,
       e.provider_native_event_reference,
       e.provider_native_commerce_reference,
       e.amount_minor,
       e.currency_code,
       e.event_timestamp,
       e.body_sha256,
       a.statement,
       a.signature,
       a.attested_amount_minor,
       a.attested_amount_currency,
       a.attested_amount_scale,
       a.key_sha256
  FROM public.b26_p2_adjustment_evidence AS e
  LEFT JOIN public.b26_p2_adjustment_attestation AS a
         ON a.adjustment_evidence_id = e.id
        AND a.tenant_id = e.tenant_id
 WHERE e.tenant_id = :tenant_id
   AND e.verdict_id = :verdict_id
 ORDER BY e.event_timestamp, e.id
"""


def _unverifiable(reason: str) -> SourceAttestationStatus:
    return SourceAttestationStatus(
        status=f"{STATUS_UNVERIFIABLE_PREFIX}:{reason}",
        reason=reason,
        attested_amount_minor=None,
        attested_currency=None,
        key_sha256=None,
    )


async def read_verdict_source_attestation_status(
    session: AsyncSession,
    *,
    tenant_id: UUID | str,
    verdict_id: UUID | str,
) -> SourceAttestationStatus:
    """Decide whether this verdict's current money is sovereignly attested.

    Called by every authoritative reader. The failure modes are deliberately
    distinct, because a consumer must be able to tell "no attestation exists
    for this row" from "an attestation exists and contradicts the money being
    served".

    XXV (A6/A10, class closure): the ABSENCE of an attestation is never a
    grant. An earlier revision of this module granted a "predecessor
    generation" exemption to rows that had no attestation and were created
    before a watermark instant read from
    ``public.b26_p2_source_attestation_authority``. That exemption was an
    owner-controlled bypass of the only authority the database frame cannot
    forge: the maintenance principal owns the attestation table (so it can
    DELETE the row the authentication root wrote) and it owns the watermark
    table (so it can move the instant), and it can rewrite the row's
    ``created_at``. Deleting the attestation and moving the watermark was
    enough to have a coherently forged amount served as ``current`` money by
    the unsigned reader while the mandatory composition proof printed PASS --
    reproduced physically by falsifier ``xxv-hb03-predecessor-escape``.

    The exemption is therefore removed and the watermark table is deleted
    from the schema. A row without a verified signature is served as
    ``source_attestation_unverifiable`` and the signed path refuses it. Money
    authenticated before the XXV epoch cannot be provider-attested (the
    provider's signed bytes are not retained), so it is reported as
    unqualified rather than as current finance; that residual is recorded as a
    DEVIATION-FOR-AUDIT with its physical reason.
    """
    from app.core.config import settings  # noqa: PLC0415

    if not settings.B26_P2_SOURCE_ATTESTATION_REQUIRED:
        return SourceAttestationStatus(
            status=STATUS_PREDECESSOR,
            reason="attestation_not_required_by_configuration",
            attested_amount_minor=None,
            attested_currency=None,
            key_sha256=None,
        )
    row = (
        (
            await session.execute(
                text(_VERDICT_SOURCE_SQL),
                {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
            )
        )
        .mappings()
        .one_or_none()
    )
    if row is None:
        return _unverifiable("verdict_not_visible")
    if row["ingress_id"] is None or row["ingress_amount"] is None:
        return _unverifiable("source_ingress_missing")

    statement_raw = row["statement"]
    if statement_raw is None:
        return _unverifiable("attestation_missing")

    statement = (
        statement_raw
        if isinstance(statement_raw, dict)
        else json.loads(str(statement_raw))
    )
    try:
        fingerprint = verify_signature(
            statement,
            str(row["signature"] or ""),
            public_key_path=settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH,
        )
    except SourceAttestationError as exc:
        return _unverifiable(str(exc))

    attested_minor = int(statement["verified_amount_minor"])
    attested_currency = str(statement["verified_amount_currency"])
    if str(statement["tenant_id"]) != str(tenant_id):
        return _unverifiable("attestation_tenant_mismatch")
    if str(statement["webhook_ingress_identity_id"]) != str(row["ingress_id"]):
        return _unverifiable("attestation_subject_mismatch")
    if int(row["attested_amount"]) != attested_minor:
        # The indexed column and the signed statement disagree: the row was
        # edited outside the signing path.
        return _unverifiable("attestation_column_diverged_from_statement")
    if int(row["ingress_amount"]) != attested_minor:
        return _unverifiable("ingress_amount_diverged_from_attestation")
    if str(row["ingress_currency"] or "").upper() != attested_currency.upper():
        return _unverifiable("ingress_currency_diverged_from_attestation")
    if str(statement.get("provider") or "").lower() != str(
        row["ingress_provider"] or ""
    ).lower():
        return _unverifiable("attestation_provider_mismatch")
    if str(statement.get("provider_native_event_reference") or "") != str(
        row["ingress_event_reference"] or ""
    ):
        return _unverifiable("attestation_event_reference_mismatch")
    if str(statement.get("provider_native_commerce_reference") or "") != str(
        row["ingress_commerce_reference"] or ""
    ):
        return _unverifiable("attestation_commerce_reference_mismatch")
    if statement.get("normalized_commerce_reference_kind") != row[
        "ingress_normalized_kind"
    ] or statement.get("normalized_commerce_reference_value") != row[
        "ingress_normalized_value"
    ]:
        return _unverifiable("attestation_normalized_reference_mismatch")
    if int(statement.get("verified_amount_scale", -1)) != int(
        row["ingress_scale"]
    ):
        return _unverifiable("attestation_scale_mismatch")
    try:
        statement_instant = datetime.fromisoformat(
            str(statement["event_timestamp"]).replace("Z", "+00:00")
        )
        if statement_instant.tzinfo is None:
            statement_instant = statement_instant.replace(tzinfo=timezone.utc)
        if statement_instant.astimezone(timezone.utc) != row[
            "ingress_event_timestamp"
        ].astimezone(timezone.utc):
            return _unverifiable("attestation_event_timestamp_mismatch")
    except (KeyError, TypeError, ValueError):
        return _unverifiable("attestation_event_timestamp_invalid")
    if str(statement.get("body_sha256") or "").lower() != str(
        row["consequence_body_sha256"] or ""
    ).lower():
        return _unverifiable("attestation_body_digest_mismatch")
    current_universe = (
        await session.execute(
            text("SELECT public.b26_p2_authority_universe()::text")
        )
    ).scalar_one_or_none()
    if current_universe is None or str(
        statement.get("authority_universe") or ""
    ) != str(current_universe):
        return _unverifiable("attestation_authority_universe_mismatch")

    from app.revenue_verification.source_evidence import (  # noqa: PLC0415
        SourceEvidenceError,
        source_fact_currentness,
    )

    if settings.B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH:
        try:
            currentness = await source_fact_currentness(
                session, tenant_id=tenant_id
            )
        except SourceEvidenceError as exc:
            return _unverifiable(f"source_fact_currentness_{exc}")
        current_key = (
            str(row["ingress_provider"] or "").lower()
            + "\x1f"
            + str(row["ingress_commerce_reference"] or "")
        )
        current_source = (currentness.get("current_sources") or {}).get(
            current_key
        )
        if current_source is None:
            return _unverifiable("source_currentness_unresolved")
        if current_source.get("status") != "current":
            return _unverifiable("source_currentness_ambiguous")
        if str(current_source.get("ingress_id")) != str(row["ingress_id"]):
            return _unverifiable("verdict_source_not_current")

    # The verdict's link to the source is owner-writable data. It is not
    # authority by itself: the linked source must still be the signed one.
    # Bind the verdict's provider/event/commerce identity to the signed
    # statement so a relink to a different current source cannot present that
    # source's money under this verdict. This runs after currentness so a
    # relink is refused for the specific currentness cause first.
    if str(row["verdict_provider"] or "").lower() != str(
        statement.get("provider") or ""
    ).lower():
        return _unverifiable("verdict_provider_mismatch")
    if str(row["verdict_event_reference"] or "") != str(
        statement.get("provider_native_event_reference") or ""
    ):
        return _unverifiable("verdict_event_reference_mismatch")
    if str(row["verdict_commerce_reference"] or "") != str(
        statement.get("provider_native_commerce_reference") or ""
    ):
        return _unverifiable("verdict_commerce_reference_mismatch")

    adjustment_rows = (
        (
            await session.execute(
                text(_VERDICT_ADJUSTMENT_SQL),
                {"tenant_id": str(tenant_id), "verdict_id": str(verdict_id)},
            )
        )
        .mappings()
        .all()
    )
    adjustment_net = 0
    adjustment_keys: set[str] = set()
    for adjustment in adjustment_rows:
        if adjustment["statement"] is None:
            return _unverifiable("adjustment_attestation_missing")
        statement = (
            adjustment["statement"]
            if isinstance(adjustment["statement"], dict)
            else json.loads(str(adjustment["statement"]))
        )
        try:
            adjustment_fingerprint = verify_adjustment_signature(
                statement,
                str(adjustment["signature"] or ""),
                public_key_path=settings.B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH,
            )
        except SourceAttestationError as exc:
            return _unverifiable(f"adjustment_{exc}")
        event_type = str(statement.get("event_type") or "").lower()
        expected_sign = ADJUSTMENT_NET_EFFECT_SIGN.get(event_type)
        if expected_sign is None or expected_sign == 0:
            return _unverifiable("adjustment_event_type_not_monetary")
        expected = {
            "adjustment_evidence_id": str(adjustment["adjustment_evidence_id"]),
            "tenant_id": str(tenant_id),
            "verdict_id": str(verdict_id),
            "provider": str(adjustment["provider"]),
            "event_type": event_type,
            "provider_native_event_reference": str(
                adjustment["provider_native_event_reference"]
            ),
            "provider_native_commerce_reference": str(
                adjustment["provider_native_commerce_reference"]
            ),
            "verified_amount_minor": int(adjustment["amount_minor"]),
            "verified_amount_currency": str(
                adjustment["currency_code"]
            ).upper(),
            "verified_amount_scale": int(adjustment["attested_amount_scale"] or 0),
            "event_timestamp": str(adjustment["event_timestamp"]),
            "body_sha256": str(adjustment["body_sha256"]).lower(),
            "net_effect_sign": int(expected_sign),
            "authority_universe": current_universe,
        }
        for key, expected_value in expected.items():
            actual = statement.get(key)
            if key == "verified_amount_currency":
                actual = str(actual or "").upper()
            if key == "net_effect_sign":
                actual = int(actual) if actual is not None else None
            if key == "event_timestamp":
                try:
                    actual_instant = datetime.fromisoformat(
                        str(actual).replace("Z", "+00:00")
                    )
                    expected_instant = datetime.fromisoformat(
                        str(expected_value).replace("Z", "+00:00")
                    )
                    if actual_instant.tzinfo is None:
                        actual_instant = actual_instant.replace(
                            tzinfo=timezone.utc
                        )
                    if expected_instant.tzinfo is None:
                        expected_instant = expected_instant.replace(
                            tzinfo=timezone.utc
                        )
                    actual = actual_instant.astimezone(timezone.utc)
                    expected_value = expected_instant.astimezone(timezone.utc)
                except (TypeError, ValueError):
                    return _unverifiable(
                        "adjustment_statement_event_timestamp_invalid"
                    )
            if actual != expected_value:
                return _unverifiable(
                    f"adjustment_statement_{key}_mismatch"
                )
        if str(statement.get("tenant_id")) != str(tenant_id):
            return _unverifiable("adjustment_tenant_mismatch")
        if int(adjustment["attested_amount_minor"] or -1) != int(
            adjustment["amount_minor"]
        ):
            return _unverifiable("adjustment_column_diverged_from_statement")
        if (
            str(adjustment["attested_amount_currency"] or "").upper()
            != str(adjustment["currency_code"] or "").upper()
        ):
            return _unverifiable("adjustment_currency_diverged_from_statement")
        adjustment_net += int(expected_sign) * int(adjustment["amount_minor"])
        adjustment_keys.add(adjustment_fingerprint)

    expected_net = attested_minor + adjustment_net
    if int(row["verdict_captured"] or 0) != attested_minor:
        return _unverifiable("verdict_captured_unsupported_by_attestation")
    if int(row["verdict_verified"] or 0) != attested_minor:
        return _unverifiable("verdict_verified_unsupported_by_attestation")
    if int(row["verdict_net"] or 0) != expected_net:
        return _unverifiable("verdict_net_unsupported_by_attestation")
    if str(row["verdict_currency"] or "").upper() != attested_currency.upper():
        return _unverifiable("verdict_currency_unsupported_by_attestation")
    if any(key != fingerprint for key in adjustment_keys):
        return _unverifiable("adjustment_attestation_key_mismatch")

    return SourceAttestationStatus(
        status=STATUS_ATTESTED,
        reason="sovereign_source_attestation_verified",
        attested_amount_minor=expected_net,
        attested_currency=attested_currency,
        key_sha256=fingerprint,
    )


ADJUSTMENT_STATEMENT_VERSION = 2
ADJUSTMENT_NET_EFFECT_SIGN = {
    "partial_refund": -1,
    "full_refund": -1,
    "chargeback_lost": -1,
    "chargeback_won": 1,
    "reversal": 1,
    "chargeback_opened": 0,
}
ADJUSTMENT_ATTESTATION_FIELDS = (
    "version",
    "tenant_id",
    "adjustment_evidence_id",
    "verdict_id",
    "provider",
    "event_type",
    "provider_native_event_reference",
    "provider_native_commerce_reference",
    "verified_amount_minor",
    "verified_amount_currency",
    "verified_amount_scale",
    "event_timestamp",
    "body_sha256",
    "net_effect_sign",
    "authority_universe",
)


def canonical_adjustment_statement_bytes(statement: Mapping[str, Any]) -> bytes:
    missing = [
        field for field in ADJUSTMENT_ATTESTATION_FIELDS if field not in statement
    ]
    if missing:
        raise SourceAttestationError(
            f"adjustment_statement_incomplete:{','.join(sorted(missing))}"
        )
    unknown = sorted(set(statement) - set(ADJUSTMENT_ATTESTATION_FIELDS))
    if unknown:
        raise SourceAttestationError(
            f"adjustment_statement_unknown_fields:{','.join(unknown)}"
        )
    return json.dumps(
        {field: statement[field] for field in ADJUSTMENT_ATTESTATION_FIELDS},
        sort_keys=True,
        separators=(",", ":"),
        default=str,
    ).encode("utf-8")


def build_adjustment_statement(
    *,
    tenant_id: UUID | str,
    adjustment_evidence_id: UUID | str,
    verdict_id: UUID | str,
    provider: str,
    event_type: str,
    provider_native_event_reference: str,
    provider_native_commerce_reference: str,
    verified_amount_minor: int,
    verified_amount_currency: str,
    verified_amount_scale: int,
    event_timestamp: datetime | str,
    body_sha256: str,
    authority_universe: str | None,
) -> dict[str, Any]:
    normalized_type = str(event_type).strip().lower()
    sign = ADJUSTMENT_NET_EFFECT_SIGN.get(normalized_type)
    if sign is None or sign == 0:
        raise SourceAttestationError(
            f"adjustment_event_type_not_monetary:{normalized_type}"
        )
    if isinstance(event_timestamp, datetime):
        instant = event_timestamp
        if instant.tzinfo is None:
            instant = instant.replace(tzinfo=timezone.utc)
        event_value = (
            instant.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
        )
    else:
        event_value = str(event_timestamp)
    return {
        "version": ADJUSTMENT_STATEMENT_VERSION,
        "tenant_id": str(tenant_id),
        "adjustment_evidence_id": str(adjustment_evidence_id),
        "verdict_id": str(verdict_id),
        "provider": str(provider),
        "event_type": normalized_type,
        "provider_native_event_reference": str(provider_native_event_reference),
        "provider_native_commerce_reference": str(
            provider_native_commerce_reference
        ),
        "verified_amount_minor": int(verified_amount_minor),
        "verified_amount_currency": str(verified_amount_currency).upper(),
        "verified_amount_scale": int(verified_amount_scale),
        "event_timestamp": event_value,
        "body_sha256": str(body_sha256).lower(),
        "net_effect_sign": int(sign),
        "authority_universe": (
            None if authority_universe is None else str(authority_universe)
        ),
    }


def sign_adjustment_statement(
    statement: Mapping[str, Any], *, private_key_path: str | os.PathLike[str]
) -> tuple[str, str]:
    from cryptography.hazmat.primitives import serialization  # noqa: PLC0415

    private_key = load_private_key(private_key_path)
    signature = private_key.sign(canonical_adjustment_statement_bytes(statement))
    public_raw = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    return (
        f"ed25519:{_b64u_encode(signature)}",
        public_key_fingerprint_from_raw(public_raw),
    )


def verify_adjustment_signature(
    statement: Mapping[str, Any],
    signature: str,
    *,
    public_key_path: str | os.PathLike[str],
) -> str:
    from cryptography.exceptions import InvalidSignature  # noqa: PLC0415
    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PublicKey,
    )

    if int(statement.get("version", 0)) != ADJUSTMENT_STATEMENT_VERSION:
        raise SourceAttestationError(
            f"adjustment_statement_version_unsupported:{statement.get('version')}"
        )
    raw_public = load_public_key_raw(public_key_path)
    fingerprint = public_key_fingerprint_from_raw(raw_public)
    anchor = compiled_attestation_anchor()
    if anchor and fingerprint != anchor:
        raise SourceAttestationError("attestation_key_not_anchored")
    if not signature.startswith("ed25519:"):
        raise SourceAttestationError("attestation_signature_algorithm_unsupported")
    try:
        Ed25519PublicKey.from_public_bytes(raw_public).verify(
            _b64u_decode(signature.split(":", 1)[1]),
            canonical_adjustment_statement_bytes(statement),
        )
    except InvalidSignature as exc:
        raise SourceAttestationError("attestation_signature_invalid") from exc
    return fingerprint


async def write_adjustment_attestation(
    session: AsyncSession,
    *,
    statement: Mapping[str, Any],
    private_key_path: str | os.PathLike[str],
    key_id: str = DEFAULT_ATTESTATION_KEY_ID,
) -> dict[str, object]:
    signature, key_sha256 = sign_adjustment_statement(
        statement, private_key_path=private_key_path
    )
    await session.execute(
        text(
            "INSERT INTO public.b26_p2_adjustment_attestation ("
            " adjustment_evidence_id, tenant_id, statement_version,"
            " attested_amount_minor, attested_amount_currency, attested_amount_scale,"
            " statement, signature, key_id, key_sha256"
            ") VALUES (:id, :tenant, :version, :amount, :currency, :scale,"
            " CAST(:statement AS jsonb), :signature, :key_id, :key_sha256)"
            " ON CONFLICT (adjustment_evidence_id) DO NOTHING"
        ),
        {
            "id": statement["adjustment_evidence_id"],
            "tenant": statement["tenant_id"],
            "version": int(statement["version"]),
            "amount": int(statement["verified_amount_minor"]),
            "currency": statement["verified_amount_currency"].upper(),
            "scale": int(statement["verified_amount_scale"]),
            "statement": json.dumps(dict(statement), sort_keys=True),
            "signature": signature,
            "key_id": key_id,
            "key_sha256": key_sha256,
        },
    )
    from app.revenue_verification.source_evidence_journal import (
        SourceFactJournalError,
        append_source_fact,
    )

    transaction_id = (
        await session.execute(text("SELECT pg_current_xact_id()::text"))
    ).scalar_one_or_none()
    if transaction_id is None:
        raise SourceAttestationError(
            "attestation_transaction_identity_missing"
        )
    try:
        append_source_fact(
            fact_kind="adjustment",
            fact_id=str(statement["adjustment_evidence_id"]),
            tenant_id=str(statement["tenant_id"]),
            verdict_id=str(statement["verdict_id"]),
            statement=statement,
            signature=signature,
            key_sha256=key_sha256,
            database_transaction_id=str(transaction_id),
        )
    except SourceFactJournalError as exc:
        raise SourceAttestationError(str(exc)) from exc
    return {
        "adjustment_evidence_id": statement["adjustment_evidence_id"],
        "signature": signature,
        "key_sha256": key_sha256,
        "key_id": key_id,
    }


__all__ = (
    "ATTESTATION_FIELDS",
    "ATTESTATION_STATEMENT_VERSION",
    "DEFAULT_ATTESTATION_KEY_ID",
    "STATUS_ATTESTED",
    "STATUS_PREDECESSOR",
    "STATUS_UNVERIFIABLE_PREFIX",
    "SourceAttestationError",
    "SourceAttestationStatus",
    "ADJUSTMENT_ATTESTATION_FIELDS",
    "ADJUSTMENT_NET_EFFECT_SIGN",
    "ADJUSTMENT_STATEMENT_VERSION",
    "build_adjustment_statement",
    "build_statement",
    "canonical_adjustment_statement_bytes",
    "canonical_statement_bytes",
    "compiled_attestation_anchor",
    "generate_keypair",
    "load_private_key",
    "load_public_key_raw",
    "public_key_fingerprint_from_raw",
    "read_verdict_source_attestation_status",
    "sign_adjustment_statement",
    "sign_statement",
    "verify_adjustment_signature",
    "verify_signature",
    "write_adjustment_attestation",
    "write_source_attestation",
)
