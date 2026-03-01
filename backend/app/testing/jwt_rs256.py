from __future__ import annotations

import json

from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric import rsa


def _generate_test_keypair() -> tuple[str, str]:
    private_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    private_pem = private_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    ).decode("utf-8")
    public_pem = private_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    ).decode("utf-8")
    return private_pem, public_pem


TEST_PRIVATE_KEY_PEM, TEST_PUBLIC_KEY_PEM = _generate_test_keypair()


def private_ring_payload(*, kid: str = "kid-1") -> str:
    return json.dumps({"current_kid": kid, "keys": {kid: TEST_PRIVATE_KEY_PEM}})


def public_ring_payload(*, kid: str = "kid-1") -> str:
    return json.dumps({"current_kid": kid, "keys": {kid: TEST_PUBLIC_KEY_PEM}})
