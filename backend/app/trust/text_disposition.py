"""Pure B2.5-P3 text disposition functions.

Known instruction-like syntax detection here is a finite risk indicator only.
The safety boundary is field trust classification: provider-controlled text is
never accepted for machine-authority fields, even when it has no detected risk.
"""

from __future__ import annotations

import hashlib
import hmac
import html
import re
from dataclasses import dataclass
from typing import Iterable

from app.trust.opaque_reference import (
    OpaqueReference,
    pseudonymize_provider_reference,
    validate_not_raw_sha256_provider_reference,
)
from app.trust.text_safety_registry import (
    BIDI_CONTROL_CHARACTERS,
    CONTENT_RISK_CLASSES,
    CONTROL_CHARACTERS,
    DISPOSITION_ACTIONS,
    EMIT_UNTRUSTED_DISPLAY_LABEL,
    JSON_XML_MARKDOWN_DELIMITER_BREAKOUT,
    KNOWN_MACHINE_INSTRUCTION_INDICATORS,
    MACHINE_AUTHORITY_CLASSES,
    MARKUP_OR_SCRIPT,
    NULL_BYTE,
    OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA,
    OVERLONG,
    REDACT_WITH_REASON,
    REJECT_OR_REFUSE,
    REPLACE_WITH_KEYED_OPAQUE_REFERENCE,
    SAFE_PRINTABLE,
    TEXT_DISPOSITION_VERSION,
    TOOL_CALL_SYNTAX,
    UNKNOWN_BINARY_OR_INVALID_ENCODING,
    classify_field_path,
    disposition_action_for,
)


MAX_DISPLAY_CHARS = 512
SHA256_PREFIX = "sha256:"
HMAC_SHA256_PREFIX = "hmac-sha256:"

_BIDI_CODEPOINTS = frozenset(
    {
        0x061C,
        0x200E,
        0x200F,
        0x202A,
        0x202B,
        0x202C,
        0x202D,
        0x202E,
        0x2066,
        0x2067,
        0x2068,
        0x2069,
    }
)

_MARKUP_OR_SCRIPT_RE = re.compile(
    r"</?[a-z][a-z0-9:-]*(?:\s[^<>]*)?>|&(?:lt|gt|amp|quot|#x?[0-9a-f]+);",
    re.IGNORECASE,
)
_DELIMITER_BREAKOUT_RE = re.compile(
    r"```|</\s*(?:system|developer|assistant|user)\s*>|"
    r"\{\s*['\"]role['\"]\s*:\s*['\"](?:system|developer|tool)['\"]|"
    r"\[\s*(?:system|developer|tool)\s*\]",
    re.IGNORECASE,
)
_TOOL_SYNTAX_RE = re.compile(
    r"<\s*tool[_-]?[a-z]*\b|"
    r"\{\{\s*#\s*(?:tool|function)\.|"
    r"\b(?:tool|function)[_-]?call\b",
    re.IGNORECASE,
)
_KNOWN_MACHINE_INSTRUCTION_RE = re.compile(
    r"\b(?:ignore|override|disregard|bypass|reveal|exfiltrate)\b"
    r".{0,80}\b(?:instruction|system|developer|policy|secret|tool)\b|"
    r"^\s*(?:system|developer|assistant|tool)\s*:",
    re.IGNORECASE | re.MULTILINE | re.DOTALL,
)


class TextDispositionError(ValueError):
    """Raised when text disposition cannot safely complete."""


@dataclass(frozen=True)
class TextDisposition:
    text_trust_class: str
    content_safety_flags: tuple[str, ...]
    disposition_action: str
    text_disposition_version: str = TEXT_DISPOSITION_VERSION
    display_text: str | None = None
    normalized_display_text: str | None = None
    raw_text_sha256: str | None = None
    raw_text_hmac: str | None = None
    opaque_reference_hash: str | None = None
    opaque_reference_metadata: dict[str, str] | None = None
    redaction_reason: str | None = None

    def external_projection(self) -> dict[str, object]:
        """Return a closed external-safe disposition projection."""
        return {
            "text_trust_class": self.text_trust_class,
            "content_safety_flags": list(self.content_safety_flags),
            "disposition_action": self.disposition_action,
            "display_text": self.display_text,
            "normalized_display_text": self.normalized_display_text,
            "raw_text_sha256": self.raw_text_sha256,
            "raw_text_hmac": self.raw_text_hmac,
            "opaque_reference_hash": self.opaque_reference_hash,
            "opaque_reference_metadata": self.opaque_reference_metadata,
            "redaction_reason": self.redaction_reason,
            "text_disposition_version": self.text_disposition_version,
        }


def _strict_text(raw_text: str | bytes) -> tuple[str | None, bytes]:
    if isinstance(raw_text, str):
        return raw_text, raw_text.encode("utf-8")
    if isinstance(raw_text, bytes):
        try:
            return raw_text.decode("utf-8", errors="strict"), raw_text
        except UnicodeDecodeError:
            return None, raw_text
    raise TextDispositionError("text_disposition_input_not_text_or_bytes")


def _ordered_flags(flags: Iterable[str]) -> tuple[str, ...]:
    flag_set = set(flags)
    unknown = sorted(flag_set - set(CONTENT_RISK_CLASSES))
    if unknown:
        raise TextDispositionError(f"text_disposition_unknown_risk_flags:{unknown}")
    return tuple(risk for risk in CONTENT_RISK_CLASSES if risk in flag_set)


def classify_content_risks(raw_text: str | bytes) -> tuple[str, ...]:
    """Classify deterministic syntactic risk indicators without overclaiming."""
    text, raw_bytes = _strict_text(raw_text)
    flags: set[str] = set()
    if text is None:
        flags.add(UNKNOWN_BINARY_OR_INVALID_ENCODING)
        return _ordered_flags(flags)

    if len(text) > MAX_DISPLAY_CHARS:
        flags.add(OVERLONG)
    if "\x00" in text:
        flags.add(NULL_BYTE)
    if any((ord(char) < 0x20 and char not in "\t\n\r") or ord(char) == 0x7F for char in text):
        flags.add(CONTROL_CHARACTERS)
    if any(ord(char) in _BIDI_CODEPOINTS for char in text):
        flags.add(BIDI_CONTROL_CHARACTERS)
    if _MARKUP_OR_SCRIPT_RE.search(text):
        flags.add(MARKUP_OR_SCRIPT)
    if _DELIMITER_BREAKOUT_RE.search(text):
        flags.add(JSON_XML_MARKDOWN_DELIMITER_BREAKOUT)
    if _TOOL_SYNTAX_RE.search(text):
        flags.add(TOOL_CALL_SYNTAX)
    if _KNOWN_MACHINE_INSTRUCTION_RE.search(text):
        flags.add(KNOWN_MACHINE_INSTRUCTION_INDICATORS)
    if not raw_bytes:
        flags.add(SAFE_PRINTABLE)
    if not flags:
        flags.add(SAFE_PRINTABLE)
    return _ordered_flags(flags)


def _tagged_sha256(raw_bytes: bytes) -> str:
    return SHA256_PREFIX + hashlib.sha256(raw_bytes).hexdigest()


def _tagged_hmac(raw_bytes: bytes, key_material: bytes) -> str:
    if not isinstance(key_material, bytes) or not key_material:
        raise TextDispositionError("text_disposition_missing_hmac_key_material")
    return HMAC_SHA256_PREFIX + hmac.new(
        key_material,
        raw_bytes,
        hashlib.sha256,
    ).hexdigest()


def _quarantine_hashes(
    raw_bytes: bytes,
    quarantine_key_material: bytes | None,
) -> tuple[str | None, str | None]:
    if quarantine_key_material:
        return None, _tagged_hmac(raw_bytes, quarantine_key_material)
    return _tagged_sha256(raw_bytes), None


def _action_for_flags(trust_class: str, flags: tuple[str, ...]) -> str:
    actions = {disposition_action_for(trust_class, flag) for flag in flags}
    unknown = actions - set(DISPOSITION_ACTIONS)
    if unknown:
        raise TextDispositionError(f"text_disposition_unknown_actions:{sorted(unknown)}")
    precedence = (
        REJECT_OR_REFUSE,
        REDACT_WITH_REASON,
        OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA,
        REPLACE_WITH_KEYED_OPAQUE_REFERENCE,
        EMIT_UNTRUSTED_DISPLAY_LABEL,
    )
    for action in precedence:
        if action in actions:
            return action
    raise TextDispositionError("text_disposition_no_action")


def dispose_text_for_field(
    *,
    field_path: str,
    raw_text: str | bytes,
    source: str,
    tenant_scope: str | None = None,
    provider: str | None = None,
    key_version: str | None = None,
    key_material: bytes | None = None,
    quarantine_key_material: bytes | None = None,
) -> TextDisposition:
    """Disposition one text value for a declared TrustEnvelope field path."""
    trust_class = classify_field_path(field_path)
    flags = classify_content_risks(raw_text)
    text, raw_bytes = _strict_text(raw_text)
    provider_controlled = source == "provider"

    if provider_controlled and trust_class in MACHINE_AUTHORITY_CLASSES:
        return TextDisposition(
            text_trust_class=trust_class,
            content_safety_flags=flags,
            disposition_action=REJECT_OR_REFUSE,
            redaction_reason="provider_text_forbidden_in_machine_authority",
        )

    action = _action_for_flags(trust_class, flags)
    if action == REJECT_OR_REFUSE:
        return TextDisposition(
            text_trust_class=trust_class,
            content_safety_flags=flags,
            disposition_action=REJECT_OR_REFUSE,
            redaction_reason="field_policy_rejected",
        )

    if action == REPLACE_WITH_KEYED_OPAQUE_REFERENCE:
        if key_material is None or tenant_scope is None or provider is None or key_version is None:
            raise TextDispositionError("opaque_reference_requires_keyed_context")
        opaque = pseudonymize_provider_reference(
            raw_reference=raw_text,
            tenant_scope=tenant_scope,
            provider=provider,
            source_field_path=field_path,
            key_version=key_version,
            key_material=key_material,
        )
        validate_not_raw_sha256_provider_reference(
            candidate_reference_hash=opaque.opaque_reference_hash,
            raw_reference=raw_text,
        )
        return _opaque_reference_disposition(trust_class, flags, opaque)

    if action == EMIT_UNTRUSTED_DISPLAY_LABEL:
        if text is None:
            raise TextDispositionError("display_label_invalid_text")
        escaped = html.escape(text, quote=True)
        return TextDisposition(
            text_trust_class=trust_class,
            content_safety_flags=flags,
            disposition_action=EMIT_UNTRUSTED_DISPLAY_LABEL,
            display_text=escaped,
            normalized_display_text=escaped,
        )

    if action == OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA:
        raw_text_sha256, raw_text_hmac = _quarantine_hashes(
            raw_bytes,
            quarantine_key_material,
        )
        return TextDisposition(
            text_trust_class=trust_class,
            content_safety_flags=flags,
            disposition_action=OMIT_RAW_TEXT_AND_EMIT_QUARANTINE_METADATA,
            raw_text_sha256=raw_text_sha256,
            raw_text_hmac=raw_text_hmac,
            redaction_reason="unsafe_untrusted_text_quarantined",
        )

    if action == REDACT_WITH_REASON:
        return TextDisposition(
            text_trust_class=trust_class,
            content_safety_flags=flags,
            disposition_action=REDACT_WITH_REASON,
            redaction_reason="field_policy_redacted",
        )

    raise TextDispositionError(f"text_disposition_unhandled_action:{action}")


def _opaque_reference_disposition(
    trust_class: str,
    flags: tuple[str, ...],
    opaque: OpaqueReference,
) -> TextDisposition:
    return TextDisposition(
        text_trust_class=trust_class,
        content_safety_flags=flags,
        disposition_action=REPLACE_WITH_KEYED_OPAQUE_REFERENCE,
        opaque_reference_hash=opaque.opaque_reference_hash,
        opaque_reference_metadata=opaque.external_metadata(),
    )
