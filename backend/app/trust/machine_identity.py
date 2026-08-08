"""B2.5-P9 machine-caller identity, scopes, replay, and rate-limit skeleton.

This module implements the adversarial machine-caller gateway substrate that
safely mounts the B2.5-P10 Trust API Read Surface. It is strictly the gateway
substrate: NO P10 route logic lives here.

Physics guarantees (per B2.5-P9 Remediation Directive):
- H-P9-02/H-P9-05: Credentials are generated with ``secrets.token_urlsafe``
  (CSPRNG) and hashed-at-rest with SHA-256. ``bcrypt``/``argon2``/``uuid4``/
  ``random`` are BANNED in the trust credential path. Machine tokens are
  high-entropy: slow KDFs become CPU-exhaustion DoS vectors and timing
  oracles (missing prefix = fast DB miss; valid prefix + wrong secret = slow
  bcrypt compute). SHA-256 gives constant-time verification.
- H-P9-03: Replay protection uses the atomic UNIQUE(tenant_id, nonce_value)
  constraint via INSERT ... ON CONFLICT DO NOTHING. No application-level
  exists()->insert() TOCTOU race.
- H-P9-06: The scope registry is a governed enum. B5.2 reserved action scopes
  (``trust.action.*``, ``auto_executable_within_policy``) are physically
  un-issuable at the DB level (CHECK constraint + trigger).
- H-P9-04: Denial audit writes go through the P7 autonomous session seam
  (``record_trust_audit_event_durable``) so they survive FastAPI exception
  rollbacks. See ``machine_auth.py``.
"""

from __future__ import annotations

import hashlib
import hmac
import secrets
from dataclasses import dataclass
from enum import StrEnum
from typing import Final

# ---------------------------------------------------------------------------
# CSPRNG credential physics (H-P9-02, H-P9-05)
# ---------------------------------------------------------------------------

#: Number of bytes of entropy in the plaintext token. ``token_urlsafe(32)``
#: yields ~43 chars of URL-safe base64, which is well above the 128-bit
#: security margin. ``secrets`` is Python's CSPRNG module backed by the OS
#: entropy source.
TOKEN_ENTROPY_BYTES: Final[int] = 32

#: Length of the stored token prefix used for O(1) indexed lookup before the
#: SHA-256 comparison. 8 chars of base64 = ~48 bits of index entropy, which is
#: enough to avoid prefix collisions at design-partner scale while not leaking
#: the full secret.
TOKEN_PREFIX_LENGTH: Final[int] = 8

#: The only permitted hash algorithm for machine service credentials.
TOKEN_HASH_ALGORITHM: Final[str] = "sha256"

#: The plaintext token is returned to the operator exactly once at issuance.
#: It is never stored, never logged, and never recoverable. The DB stores only
#: ``token_prefix`` (for O(1) lookup) and ``token_hash`` (SHA-256 of the full
#: plaintext). This eliminates the timing oracle described in H-P9-02:
#: lookup is O(1) by prefix, and verification is a constant-time SHA-256
#: comparison via ``hmac.compare_digest``.


class MachineTokenError(ValueError):
    """Raised when machine token generation or verification is unsafe."""


class ReservedScopeError(ValueError):
    """Raised when a reserved B5.2 action scope is requested for issuance."""


@dataclass(frozen=True)
class MachineTokenSecret:
    """Issued plaintext token + derived storage material.

    The ``plaintext`` field MUST be returned to the operator exactly once and
    never persisted. Only ``token_prefix`` and ``token_hash`` are stored.
    """

    plaintext: str
    token_prefix: str
    token_hash: str
    hash_algorithm: str = TOKEN_HASH_ALGORITHM

    def __post_init__(self) -> None:
        if len(self.token_prefix) != TOKEN_PREFIX_LENGTH:
            raise MachineTokenError(
                f"token_prefix_length_mismatch:{len(self.token_prefix)}"
            )
        if len(self.token_hash) != 64:
            raise MachineTokenError(
                f"token_hash_length_mismatch:{len(self.token_hash)}"
            )
        if self.hash_algorithm != TOKEN_HASH_ALGORITHM:
            raise MachineTokenError(
                f"hash_algorithm_forbidden:{self.hash_algorithm}"
            )

    def storage_projection(self) -> dict[str, str]:
        """Material safe to persist. Excludes ``plaintext``."""
        return {
            "token_prefix": self.token_prefix,
            "token_hash": self.token_hash,
            "hash_algorithm": self.hash_algorithm,
        }


def generate_machine_token() -> MachineTokenSecret:
    """Generate a CSPRNG machine token and its SHA-256 storage material.

    Uses ``secrets.token_urlsafe`` (the CSPRNG). ``uuid4`` and ``random`` are
    BANNED for trust credentials: they are not cryptographically secure.
    """
    plaintext = secrets.token_urlsafe(TOKEN_ENTROPY_BYTES)
    token_prefix = plaintext[:TOKEN_PREFIX_LENGTH]
    token_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return MachineTokenSecret(
        plaintext=plaintext,
        token_prefix=token_prefix,
        token_hash=token_hash,
    )


def derive_token_storage(plaintext: str) -> MachineTokenSecret:
    """Derive prefix + SHA-256 hash from an externally-supplied plaintext.

    Used by the validator negative controls and the verification path. The
    plaintext is never persisted.
    """
    if not plaintext or len(plaintext) < TOKEN_PREFIX_LENGTH:
        raise MachineTokenError("plaintext_too_short")
    token_prefix = plaintext[:TOKEN_PREFIX_LENGTH]
    token_hash = hashlib.sha256(plaintext.encode("utf-8")).hexdigest()
    return MachineTokenSecret(
        plaintext=plaintext,
        token_prefix=token_prefix,
        token_hash=token_hash,
    )


def verify_machine_token(
    presented_plaintext: str,
    stored_token_hash: str,
    stored_hash_algorithm: str = TOKEN_HASH_ALGORITHM,
) -> bool:
    """Constant-time verification of a presented token against the stored hash.

    ``hmac.compare_digest`` is used to prevent comparison timing attacks.
    Returns ``False`` on any mismatch, wrong algorithm, or malformed input —
    never raises on a verification mismatch (callers map the False result to
    the P6 reason code).
    """
    if stored_hash_algorithm != TOKEN_HASH_ALGORITHM:
        return False
    if not presented_plaintext or not stored_token_hash:
        return False
    computed = hashlib.sha256(presented_plaintext.encode("utf-8")).hexdigest()
    return hmac.compare_digest(computed, stored_token_hash)


# ---------------------------------------------------------------------------
# Governed scope registry (H-P9-06)
# ---------------------------------------------------------------------------


class AgentScope(StrEnum):
    """Design Partner Mode machine-caller scopes.

    These are the ONLY scopes that may be granted to an ``agent_client`` under
    B2.5-P9. Forward-reserved B5.2 action scopes are physically un-issuable at
    the DB level and rejected here at the application layer before any DB write.
    """

    ENVELOPE_READ = "trust.envelope.read"
    ENVELOPE_VERIFY = "trust.envelope.verify"
    AUDIT_READ = "trust.audit.read"
    KEYS_READ = "trust.keys.read"
    EXPORT_CREATE_LIMITED = "trust.export.create_limited"


#: The complete set of scopes permitted in Design Partner Mode.
DESIGN_PARTNER_SCOPES: Final[frozenset[AgentScope]] = frozenset(AgentScope)

#: B5.2 forward-reserved action scopes. These are PHYSICALLY UN-ISSUABLE.
#: The DB CHECK constraint and trigger reject them; this set lets the
#: application layer reject them before the DB write with a typed error.
RESERVED_ACTION_SCOPES: Final[frozenset[str]] = frozenset(
    {
        "trust.action.propose",
        "trust.action.execute",
        "trust.action.approve",
        "trust.action.reject",
        "auto_executable_within_policy",
    }
)


def assert_scope_issuable(scope_value: str) -> AgentScope:
    """Ingress-only conversion that rejects reserved/un-issuable scopes.

    Raises :class:`ReservedScopeError` for any B5.2 reserved action scope
    *before* any DB write, so the audit trail records the typed rejection.
    """
    if scope_value in RESERVED_ACTION_SCOPES:
        raise ReservedScopeError(
            f"reserved_action_scope_unissuable:{scope_value}"
        )
    try:
        return AgentScope(scope_value)
    except ValueError as exc:
        raise ReservedScopeError(
            f"scope_value_not_in_design_partner_registry:{scope_value}"
        ) from exc


def coerce_scope(scope_value: str | AgentScope) -> AgentScope:
    """Safe coercion used by the middleware and validator."""
    if isinstance(scope_value, AgentScope):
        return scope_value
    return assert_scope_issuable(scope_value)


# ---------------------------------------------------------------------------
# Forbidden entropy/hash primitives (AST-banned by the CI validator)
# ---------------------------------------------------------------------------

#: These names are BANNED in the trust credential path. The P9 CI validator
#: performs an AST scan of ``backend/app/trust/machine_identity.py`` and
#: ``machine_auth.py`` to ensure none are imported or called. ``secrets`` is
#: the ONLY permitted entropy source; ``hashlib.sha256`` is the ONLY permitted
#: token hash; ``hmac.compare_digest`` is the ONLY permitted comparison.
FORBIDDEN_ENTROPY_SOURCES: Final[frozenset[str]] = frozenset(
    {"uuid.uuid4", "uuid4", "random", "random.random", "random.choice"}
)
FORBIDDEN_TOKEN_HASHES: Final[frozenset[str]] = frozenset(
    {"bcrypt", "argon2", "passlib", "pbkdf2"}
)
