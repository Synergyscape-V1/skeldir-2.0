"""Compiled root of trust for the B2.6-P2 history witness.

XXIV (A1/A5): environment variables alone cannot establish the witness
root, because any principal able to replace the key/journal can also
replace the genesis value. The image build pins the public-key
fingerprint and genesis hash into this module. Production refuses to
issue unless the runtime key and genesis match these compiled values.

The committed defaults are intentionally empty. A production image must
be built with both build arguments; a source checkout can still run
tests and development lanes without them.
"""

from __future__ import annotations

COMPILED_PUBLIC_KEY_SHA256: str | None = None
COMPILED_GENESIS_HASH: str | None = None


def has_compiled_anchor() -> bool:
    return bool(COMPILED_PUBLIC_KEY_SHA256 and COMPILED_GENESIS_HASH)


__all__ = (
    "COMPILED_GENESIS_HASH",
    "COMPILED_PUBLIC_KEY_SHA256",
    "has_compiled_anchor",
)
