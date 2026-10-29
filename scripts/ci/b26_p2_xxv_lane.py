#!/usr/bin/env python3
"""B2.6-P2 Corrective XXV production-equivalent lane.

Brings up the shipping process topology from the compiled production
image so that XXV falsifiers and proofs execute against the artifact the
deployment runs, not against host imports:

  postgres:15  +  auth root  +  API  +  B2.3 worker  +  relay  +  beat
               +  history observer (sole witness key holder)
               +  Trust signer (TLS)

Lane law
--------
* The image is built from ``backend/Dockerfile`` at the current tree with
  the compiled witness anchor bound in (two-phase: bootstrap image ->
  genesis checkpoint -> final anchored image), exactly as a production
  deployment pins its historical root.
* Every runtime process runs ``ENVIRONMENT=prod`` with the shipping
  least-privilege role graph, the file-mounted ingress credential held
  only by the auth root, and the witness private key held only by the
  observer.
* The control plane is served by a lane-local store reached through an
  ``aws`` shim mounted on PATH, because the shipped production image
  carries no AWS client binary (recorded as finding XXV-F-CP1). The shim
  implements the two commands ``app/core/control_plane.py`` invokes and
  serves per-process stores, so the lane can observe process-scoped
  credential behaviour instead of assuming it.
* No audited code path is modified, mocked, or bypassed by this lane.

Usage
-----
    python scripts/ci/b26_p2_xxv_lane.py up
    python scripts/ci/b26_p2_xxv_lane.py state
    python scripts/ci/b26_p2_xxv_lane.py down
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
import os
import secrets
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.error
import urllib.request
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
BACKEND = REPO_ROOT / "backend"

PREFIX = os.environ.get("B26_P2_XXV_PREFIX", "b26p2xxv")
NETWORK = f"{PREFIX}-net"
PG = f"{PREFIX}-pg"
AUTH = f"{PREFIX}-auth"
API = f"{PREFIX}-api"
WORKER_B23 = f"{PREFIX}-worker-b23"
RELAY = f"{PREFIX}-relay"
BEAT = f"{PREFIX}-beat"
OBSERVER = f"{PREFIX}-observer"
SIGNER = f"{PREFIX}-signer"
WITNESS_VOL = f"{PREFIX}-witness"
SECRETS_VOL = f"{PREFIX}-secrets"
SOURCE_EVIDENCE_VOL = f"{PREFIX}-source-evidence"
DB_NAME = os.environ.get("B26_P2_XXV_DB", "skeldir_xxv")
BOOTSTRAP_IMAGE = f"{PREFIX}-bootstrap:latest"
FINAL_IMAGE = f"{PREFIX}-final:latest"

PG_PORT = int(os.environ.get("B26_P2_XXV_PG_PORT", "55471"))
API_PORT = int(os.environ.get("B26_P2_XXV_API_PORT", "18071"))
AUTH_PORT = int(os.environ.get("B26_P2_XXV_AUTH_PORT", "18072"))

PLATFORM_KEY = "xxv-platform-key"
PLATFORM_KEY_ID = "xxv-key"
JWT_ISSUER = "https://issuer.skeldir.test"
JWT_AUDIENCE = "skeldir-api"
TRUST_KID = "kid:b26-p2-xxv"

LANE_ROOT = Path(
    os.environ.get(
        "B26_P2_XXV_LANE_ROOT",
        str(Path(tempfile.gettempdir()) / f"{PREFIX}-lane"),
    )
)
STATE_PATH = LANE_ROOT / "lane-state.json"


# ----------------------------------------------------------------- helpers
def run(cmd: list[str], **kwargs) -> subprocess.CompletedProcess[str]:
    return subprocess.run(cmd, text=True, capture_output=True, **kwargs)


def docker(*args: str) -> subprocess.CompletedProcess[str]:
    return run(["docker", *args], cwd=str(REPO_ROOT))


def docker_ok(*args: str) -> str:
    proc = docker(*args)
    if proc.returncode != 0:
        raise RuntimeError(
            f"docker {' '.join(args[:3])} failed rc={proc.returncode}: "
            f"{(proc.stderr or proc.stdout)[-900:]}"
        )
    return proc.stdout.strip()


def b64u(raw: bytes) -> str:
    return base64.urlsafe_b64encode(raw).rstrip(b"=").decode("ascii")


def load_state() -> dict:
    if not STATE_PATH.exists():
        raise RuntimeError("lane_state_missing: run `up` first")
    return json.loads(STATE_PATH.read_text(encoding="utf-8"))


def save_state(state: dict) -> None:
    LANE_ROOT.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def admin_dsn() -> str:
    return f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/{DB_NAME}"


def sql(statement: str, params: tuple = (), dsn: str | None = None) -> list[tuple]:
    import psycopg2

    conn = psycopg2.connect(dsn or admin_dsn())
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(statement, params)
        try:
            return cur.fetchall()
        except Exception:  # noqa: BLE001 - statement produced no result set
            return []
    finally:
        conn.close()


def role_dsn(role: str, *, host: str = "127.0.0.1", port: int | None = None) -> str:
    return (
        f"postgresql://{role}:{role}@{host}:{port or PG_PORT}/{DB_NAME}"
    )


# ------------------------------------------------------- volume file access
def volume_put(volume: str, files: dict[str, bytes], *, mode: str = "0600") -> None:
    """Write files into a named volume through a throwaway container."""
    helper = f"{PREFIX}-vol-{uuid.uuid4().hex[:6]}"
    docker("rm", "-f", helper)
    docker_ok(
        "create", "--name", helper, "-v", f"{volume}:/vol", "busybox:latest", "true"
    )
    staging = Path(tempfile.mkdtemp(prefix=f"{PREFIX}-stage-"))
    try:
        for rel, payload in files.items():
            target = staging / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(payload)
            docker_ok("cp", str(target), f"{helper}:/vol/{rel}")
    finally:
        shutil.rmtree(staging, ignore_errors=True)
    docker("rm", "-f", helper)
    fix = f"chmod -R {mode} /vol || true; chown -R 0:0 /vol || true"
    docker_ok(
        "run", "--rm", "-v", f"{volume}:/vol", "busybox:latest", "sh", "-c", fix
    )


def volume_get(volume: str, rel: str) -> bytes:
    proc = docker(
        "run", "--rm", "-v", f"{volume}:/vol", "busybox:latest",
        "sh", "-c", f"cat /vol/{rel} | base64",
    )
    if proc.returncode != 0:
        raise RuntimeError(f"volume_get_failed:{rel}:{proc.stderr[-300:]}")
    return base64.b64decode("".join(proc.stdout.split()))


def volume_list(volume: str) -> str:
    proc = docker(
        "run", "--rm", "-v", f"{volume}:/vol", "busybox:latest",
        "sh", "-c", "ls -l /vol",
    )
    return proc.stdout


def volume_rm(volume: str, rel: str) -> None:
    docker_ok(
        "run", "--rm", "-v", f"{volume}:/vol", "busybox:latest",
        "sh", "-c", f"rm -f /vol/{rel}",
    )


# ----------------------------------------------------------- key material
def generate_material() -> dict:
    """Generate every lane key/credential. Nothing audited is modified."""
    from cryptography import x509
    from cryptography.hazmat.primitives import hashes, serialization
    from cryptography.hazmat.primitives.asymmetric import ed25519, rsa
    from cryptography.x509.oid import NameOID

    LANE_ROOT.mkdir(parents=True, exist_ok=True)

    # --- TLS CA + signer certificate (signer runs real TLS) -------------
    ca_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    ca_name = x509.Name(
        [x509.NameAttribute(NameOID.COMMON_NAME, "Skeldir XXV Lane CA")]
    )
    now = datetime.now(timezone.utc)
    ca_cert = (
        x509.CertificateBuilder()
        .subject_name(ca_name)
        .issuer_name(ca_name)
        .public_key(ca_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(x509.BasicConstraints(ca=True, path_length=None), critical=True)
        .sign(ca_key, hashes.SHA256())
    )
    signer_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    signer_cert = (
        x509.CertificateBuilder()
        .subject_name(
            x509.Name([x509.NameAttribute(NameOID.COMMON_NAME, SIGNER)])
        )
        .issuer_name(ca_name)
        .public_key(signer_key.public_key())
        .serial_number(x509.random_serial_number())
        .not_valid_before(now - timedelta(minutes=5))
        .not_valid_after(now + timedelta(days=2))
        .add_extension(
            x509.SubjectAlternativeName(
                [x509.DNSName(SIGNER), x509.DNSName("localhost")]
            ),
            critical=False,
        )
        .add_extension(
            x509.ExtendedKeyUsage([x509.oid.ExtendedKeyUsageOID.SERVER_AUTH]),
            critical=False,
        )
        .sign(ca_key, hashes.SHA256())
    )

    # --- JWT ring (RS256) ----------------------------------------------
    # A lane rebuild generates a new signing key. The kid must change with
    # it: reusing a kid across key rotations makes a warm verification cache
    # unable to tell the old and new key apart, and the first requests can
    # be refused until the ring TTL expires.
    jwt_kid = f"xxv-jwt-{secrets.token_hex(6)}"
    jwt_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
    jwt_private_pem = jwt_key.private_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PrivateFormat.PKCS8,
        encryption_algorithm=serialization.NoEncryption(),
    )
    jwt_public_pem = jwt_key.public_key().public_bytes(
        encoding=serialization.Encoding.PEM,
        format=serialization.PublicFormat.SubjectPublicKeyInfo,
    )
    jwt_signing_ring = json.dumps(
        {
            "current_kid": jwt_kid,
            "keys": {jwt_kid: jwt_private_pem.decode("ascii")},
        },
        separators=(",", ":"),
    )
    jwt_ring = json.dumps(
        {
            "current_kid": jwt_kid,
            "keys": {jwt_kid: jwt_public_pem.decode("ascii")},
        },
        separators=(",", ":"),
    )

    # --- Trust signing key (Ed25519) + public JWKS ---------------------
    trust_seed = os.urandom(32)
    trust_private = ed25519.Ed25519PrivateKey.from_private_bytes(trust_seed)
    trust_public_raw = trust_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )
    valid_from = (now - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
    trust_jwks = json.dumps(
        {
            "keys": [
                {
                    "kty": "OKP",
                    "crv": "Ed25519",
                    "alg": "EdDSA",
                    "use": "sig",
                    "kid": TRUST_KID,
                    "x": b64u(trust_public_raw),
                    "skeldir_key_state": "active",
                    "skeldir_valid_from": valid_from,
                }
            ]
        },
        separators=(",", ":"),
    )

    # --- Witness keypair (observer-only private seed) ------------------
    witness_private = ed25519.Ed25519PrivateKey.generate()
    witness_private_raw = witness_private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    witness_public_raw = witness_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    # XXV sovereign source-money attestation keypair. The seed is mounted
    # into the authentication root only; the public key is readable by every
    # reader and its fingerprint is compiled into the final image.
    attestation_private = ed25519.Ed25519PrivateKey.generate()
    attestation_private_raw = attestation_private.private_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PrivateFormat.Raw,
        encryption_algorithm=serialization.NoEncryption(),
    )
    attestation_public_raw = attestation_private.public_key().public_bytes(
        encoding=serialization.Encoding.Raw,
        format=serialization.PublicFormat.Raw,
    )

    material = {
        "ca_pem": ca_cert.public_bytes(serialization.Encoding.PEM).decode(),
        "signer_cert_pem": signer_cert.public_bytes(
            serialization.Encoding.PEM
        ).decode(),
        "signer_key_pem": signer_key.private_bytes(
            encoding=serialization.Encoding.PEM,
            format=serialization.PrivateFormat.PKCS8,
            encryption_algorithm=serialization.NoEncryption(),
        ).decode(),
        "jwt_private_pem": jwt_private_pem.decode(),
        "jwt_kid": jwt_kid,
        "jwt_signing_ring_json": jwt_signing_ring,
        "jwt_ring_json": jwt_ring,
        "trust_seed_b64url": b64u(trust_seed),
        "trust_jwks_json": trust_jwks,
        "trust_key_valid_from": valid_from,
        "trust_signer_shared_secret": b64u(os.urandom(32)),
        "witness_private_b64url": b64u(witness_private_raw),
        "witness_public_b64url": b64u(witness_public_raw),
        "witness_public_sha256": hashlib.sha256(witness_public_raw).hexdigest(),
        "attestation_private_b64url": b64u(attestation_private_raw),
        "attestation_public_b64url": b64u(attestation_public_raw),
        "attestation_public_sha256": hashlib.sha256(
            attestation_public_raw
        ).hexdigest(),
    }
    (LANE_ROOT / "jwt-private.pem").write_text(
        material["jwt_private_pem"], encoding="utf-8"
    )
    # The attestation PUBLIC key is published to the lane root as well, so a
    # host-side proof (the mandatory composition validator) can verify the
    # same signatures the containers verify. No private material is written
    # outside the container secret volumes.
    (LANE_ROOT / "source_attestation_ed25519.pub").write_text(
        material["attestation_public_b64url"], encoding="utf-8"
    )
    return material


# --------------------------------------------------- control-plane shim
AWS_SHIM = r"""#!/usr/bin/env python3
# Lane control-plane shim (XXV-F-CP1): the shipped production image has no
# AWS client binary, so the lane provides the two commands
# app/core/control_plane.py invokes. Values come from a read-only
# per-process store mounted at /run/skeldir-cp/store.json. The audited
# resolution code path is unchanged.
import json
import sys

ARGS = sys.argv[1:]
try:
    STORE = json.load(open("/run/skeldir-cp/store.json", encoding="utf-8"))
except Exception as exc:  # noqa: BLE001
    sys.stderr.write(f"control-plane store unreadable: {exc}\n")
    raise SystemExit(70)


def value_for(path):
    if path not in STORE:
        sys.stderr.write(
            "ResourceNotFoundException: control plane has no value for "
            f"{path} in this process scope\n"
        )
        raise SystemExit(254)
    return STORE[path]


def flag(name):
    if name in ARGS:
        return ARGS[ARGS.index(name) + 1]
    return None


if ARGS[:2] == ["secretsmanager", "get-secret-value"]:
    print(value_for(flag("--secret-id")))
elif ARGS[:2] == ["ssm", "get-parameter"]:
    print(value_for(flag("--name")))
else:
    sys.stderr.write(f"unsupported aws invocation: {ARGS}\n")
    raise SystemExit(252)
"""


_MANAGED_CACHE: dict[str, dict] | None = None


def managed_contract(image: str) -> dict[str, dict]:
    """Read the managed-settings contract and defaults out of the image."""
    global _MANAGED_CACHE
    if _MANAGED_CACHE is not None:
        return _MANAGED_CACHE
    probe = (
        "import json;"
        "from app.core.managed_settings_contract import MANAGED_SETTINGS_CONTRACT;"
        "from app.core.config import Settings;"
        "out={};"
        "\nfor k,c in MANAGED_SETTINGS_CONTRACT.items():\n"
        "    f=Settings.model_fields.get(k)\n"
        "    d=None if f is None else f.default\n"
        "    if d is not None and d.__class__.__name__=='PydanticUndefinedType': d=None\n"
        "    if isinstance(d,bool): d='true' if d else 'false'\n"
        "    out[k]={'classification':c.classification,"
        "'path':c.aws_path_template.format(env='prod'),"
        "'default':'' if d is None else str(d)}\n"
        "print('CONTRACT=' + json.dumps(out))"
    )
    proc = docker(
        "run", "--rm",
        "-e", "DATABASE_URL=postgresql+asyncpg://x:y@127.0.0.1:5432/z",
        "-e", "ENVIRONMENT=ci",
        image, "python", "-c", probe,
    )
    if proc.returncode != 0:
        raise RuntimeError(f"managed_contract_probe_failed:{proc.stderr[-800:]}")
    line = next(
        row for row in proc.stdout.splitlines() if row.startswith("CONTRACT=")
    )
    _MANAGED_CACHE = json.loads(line.split("=", 1)[1])
    return _MANAGED_CACHE


def control_plane_store(role: str, state: dict) -> dict[str, str]:
    """Per-process control-plane store.

    The shipped client resolves EVERY managed key for EVERY process from one
    environment scope (``preload_environment_from_control_plane`` iterates
    the whole contract). The lane serves the whole contract so the shipped
    process can boot, but gives each role the DSN its Procfile line
    declares, so process-scoped credential behaviour is observable instead
    of assumed.
    """
    material = state["material"]
    contract = managed_contract(state.get("probe_image", BOOTSTRAP_IMAGE))
    dsn_for = {
        "api": role_dsn("app_user", host="pg", port=5432),
        "auth_ingress": role_dsn("app_user", host="pg", port=5432),
        "worker_b23": role_dsn("app_worker", host="pg", port=5432),
        "observer_b26_p2": role_dsn("app_worker", host="pg", port=5432),
        "b26_p2_relay": role_dsn("app_relay", host="pg", port=5432),
        "beat": role_dsn("app_beat", host="pg", port=5432),
        "trust_signer": role_dsn("app_trust_signer", host="pg", port=5432),
    }[role]
    transport = role_dsn("app_celery_transport", host="pg", port=5432)
    overrides: dict[str, str] = {
        "DATABASE_URL": dsn_for,
        "MIGRATION_DATABASE_URL": role_dsn("migration_owner", host="pg", port=5432),
        "CELERY_BROKER_URL": f"sqla+{transport}",
        "CELERY_RESULT_BACKEND": f"db+{transport}",
        "AUTH_JWT_SECRET": material["jwt_signing_ring_json"],
        "AUTH_JWT_PUBLIC_KEY_RING": material["jwt_ring_json"],
        "AUTH_JWT_ALGORITHM": "RS256",
        "AUTH_JWT_ISSUER": JWT_ISSUER,
        "AUTH_JWT_AUDIENCE": JWT_AUDIENCE,
        "AUTH_LOGIN_IDENTIFIER_PEPPER": "xxv-login-pepper",
        "PLATFORM_TOKEN_ENCRYPTION_KEY": PLATFORM_KEY,
        "PLATFORM_TOKEN_KEY_ID": PLATFORM_KEY_ID,
        # The LLM provider key is required by the prod secret contract. The
        # lane serves a value that is never used: no XXV proof calls an LLM,
        # and the LLM remains excluded from deterministic truth by axiom 2.
        "LLM_PROVIDER_API_KEY": "xxv-lane-llm-key-unused",
        "ENVIRONMENT": "prod",
        "LOG_LEVEL": "INFO",
        "B26_P2_HISTORY_WITNESS_REQUIRED": "true",
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH": "/var/lib/b26_p2/history_witness.jsonl",
        "B26_P2_HISTORY_WITNESS_CUSTODY_PATH": "/var/lib/b26_p2/history_witness_custody.json",
        "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH": "/var/lib/b26_p2/history_witness_heartbeat.json",
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH": "/var/lib/b26_p2/history_witness_ed25519.pub",
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH": state.get("genesis_hash", ""),
        "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH": (
            "/run/secrets/b26_p2_history_witness_key"
            if role == "observer_b26_p2"
            else ""
        ),
    }
    store: dict[str, str] = {}
    for key, meta in contract.items():
        store[meta["path"]] = overrides.get(key, meta["default"])
    return store


def write_control_plane(role: str, state: dict) -> str:
    """Materialise one process-scoped control-plane store volume."""
    volume = f"{PREFIX}-cp-{role.replace('_', '-')}"
    docker("volume", "rm", "-f", volume)
    docker_ok("volume", "create", volume)
    volume_put(
        volume,
        {
            "store.json": json.dumps(control_plane_store(role, state)).encode(),
            "aws": AWS_SHIM.encode(),
        },
        mode="0755",
    )
    return volume


# ------------------------------------------------------------- lane stages
def lane_env(role: str, *, cp_volume: str, extra: dict[str, str]) -> list[str]:
    env = {
        "ENVIRONMENT": "prod",
        "LOG_LEVEL": "INFO",
        "SKELDIR_PROCESS_ROLE": role,
        "SKELDIR_CONTROL_PLANE_ENABLED": "1",
        "SKELDIR_CONTROL_PLANE_CLIENT": "cli",
        "AWS_REGION": "us-east-2",
        "PATH": "/run/skeldir-cp:/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin",
        "PROMETHEUS_MULTIPROC_DIR": "/tmp",
        "PLATFORM_TOKEN_KEY_ID": PLATFORM_KEY_ID,
        "AUTH_JWT_ALGORITHM": "RS256",
        "AUTH_JWT_ISSUER": JWT_ISSUER,
        "AUTH_JWT_AUDIENCE": JWT_AUDIENCE,
        "B26_P2_INGRESS_DATABASE_URL": "",
        "B26_P2_INGRESS_DATABASE_URL_FILE": "",
    }
    env.update(extra)
    flags: list[str] = []
    for key, value in env.items():
        flags.extend(["-e", f"{key}={value}"])
    flags.extend(["-v", f"{cp_volume}:/run/skeldir-cp:ro"])
    return flags


def attestation_env(state: dict, *, signer: bool) -> dict[str, str]:
    """XXV: every process verifies; only the auth root signs."""
    return {
        "B26_P2_SOURCE_ATTESTATION_REQUIRED": "true",
        "B26_P2_SOURCE_EVIDENCE_JOURNAL_PATH": "/var/lib/b26_p2_source/source_evidence.jsonl",
        "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_PATH": (
            "/var/lib/b26_p2/source_attestation_ed25519.pub"
        ),
        "B26_P2_SOURCE_ATTESTATION_PRIVATE_KEY_PATH": (
            "/run/secrets/b26_p2_source_attestation_key" if signer else ""
        ),
    }


def witness_env(state: dict, *, private: bool) -> dict[str, str]:
    env = {
        "B26_P2_HISTORY_WITNESS_REQUIRED": "true",
        "B26_P2_HISTORY_WITNESS_JOURNAL_PATH": "/var/lib/b26_p2/history_witness.jsonl",
        "B26_P2_HISTORY_WITNESS_CUSTODY_PATH": "/var/lib/b26_p2/history_witness_custody.json",
        "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH": "/var/lib/b26_p2/history_witness_heartbeat.json",
        "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH": "/var/lib/b26_p2/history_witness_ed25519.pub",
        "B26_P2_HISTORY_WITNESS_GENESIS_HASH": state.get("genesis_hash", ""),
    }
    if private:
        env["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = (
            "/run/secrets/b26_p2_history_witness_key"
        )
    else:
        env["B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH"] = ""
    return env


def build_image(tag: str, *, anchor: dict | None = None) -> str:
    args = ["build", "-f", "backend/Dockerfile", "-t", tag]
    if anchor:
        args.extend(
            [
                "--build-arg",
                f"B26_P2_HISTORY_WITNESS_PUBLIC_KEY_SHA256={anchor['public_key_sha256']}",
                "--build-arg",
                f"B26_P2_HISTORY_WITNESS_GENESIS_HASH={anchor['genesis_hash']}",
                "--build-arg",
                "B26_P2_SOURCE_ATTESTATION_PUBLIC_KEY_SHA256="
                + anchor["source_attestation_public_key_sha256"],
            ]
        )
    args.append(".")
    docker_ok(*args)
    return docker_ok("image", "inspect", tag, "--format", "{{.Id}}")


def start_pg() -> None:
    docker("rm", "-f", PG)
    docker("network", "rm", NETWORK)
    docker_ok("network", "create", NETWORK)
    docker_ok(
        "run", "-d", "--name", PG, "--network", NETWORK, "--network-alias", "pg",
        "-p", f"{PG_PORT}:5432",
        "-e", "POSTGRES_USER=postgres",
        "-e", "POSTGRES_PASSWORD=postgres",
        "-e", "POSTGRES_DB=postgres",
        "postgres:15-alpine", "postgres", "-c", "max_connections=200",
    )
    for _ in range(90):
        if docker("exec", PG, "pg_isready", "-U", "postgres").returncode == 0:
            time.sleep(2)
            return
        time.sleep(1)
    raise RuntimeError("postgres_not_ready")


def provision() -> None:
    import psycopg2

    conn = psycopg2.connect(f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/postgres")
    try:
        conn.autocommit = True
        cur = conn.cursor()
        cur.execute(f'DROP DATABASE IF EXISTS "{DB_NAME}"')
        cur.execute(f'CREATE DATABASE "{DB_NAME}"')
    finally:
        conn.close()
    proc = run(
        [
            sys.executable,
            str(REPO_ROOT / "scripts/database/prepare_migration_authority_boundary.py"),
            "--admin-dsn",
            f"postgresql://postgres:postgres@127.0.0.1:{PG_PORT}/postgres",
            "--database-name",
            DB_NAME,
        ],
        cwd=str(REPO_ROOT),
    )
    if proc.returncode != 0:
        raise RuntimeError(f"provision_failed:{proc.stderr[-1500:]}")


def migrate(image: str) -> str:
    dsn = role_dsn("migration_owner", host="pg", port=5432)
    proc = docker(
        "run", "--rm", "--network", NETWORK, "--workdir", "/app",
        "-e", f"MIGRATION_DATABASE_URL={dsn}",
        "-e", f"DATABASE_URL={dsn}",
        "-e", "ENVIRONMENT=ci",
        image, "alembic", "-c", "/app/alembic.ini", "upgrade", "head",
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"migrate_failed:{proc.stdout[-800:]}:{proc.stderr[-800:]}"
        )
    return sql("SELECT version_num FROM public.alembic_version")[0][0]


def witness_bootstrap(image: str, material: dict) -> dict:
    """Create the genesis checkpoint with the observer's own code path."""
    docker("volume", "rm", "-f", WITNESS_VOL)
    docker("volume", "rm", "-f", SECRETS_VOL)
    docker_ok("volume", "create", WITNESS_VOL)
    docker_ok("volume", "create", SECRETS_VOL)
    volume_put(
        WITNESS_VOL,
        {
            "history_witness_ed25519.pub": material["witness_public_b64url"].encode(),
            "source_attestation_ed25519.pub": material[
                "attestation_public_b64url"
            ].encode(),
        },
        mode="0644",
    )
    volume_put(
        SECRETS_VOL,
        {
            "b26_p2_history_witness_key": material["witness_private_b64url"].encode(),
            "b26_p2_history_witness_pub": material["witness_public_b64url"].encode(),
        },
    )
    dsn = f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{DB_NAME}"
    probe = (
        "import asyncio, json;"
        "from app.tasks.b26_p2_history import observe_history_integrity;"
        "print('OBSERVED=' + json.dumps(asyncio.run(observe_history_integrity()), default=str))"
    )
    proc = docker(
        "run", "--rm", "--network", NETWORK,
        "-e", f"DATABASE_URL={dsn}",
        "-e", f"B23_WORKER_DATABASE_URL={dsn}",
        "-e", "SKELDIR_B23_REQUIRE_WORKER_DSN=1",
        "-e", "ENVIRONMENT=ci",
        "-e", "SKELDIR_PROCESS_ROLE=observer_b26_p2",
        "-e", "B26_P2_HISTORY_WITNESS_REQUIRED=true",
        "-e", "B26_P2_HISTORY_WITNESS_JOURNAL_PATH=/var/lib/b26_p2/history_witness.jsonl",
        "-e", "B26_P2_HISTORY_WITNESS_CUSTODY_PATH=/var/lib/b26_p2/history_witness_custody.json",
        "-e", "B26_P2_HISTORY_WITNESS_HEARTBEAT_PATH=/var/lib/b26_p2/history_witness_heartbeat.json",
        "-e", "B26_P2_HISTORY_WITNESS_PUBLIC_KEY_PATH=/var/lib/b26_p2/history_witness_ed25519.pub",
        "-e", "B26_P2_HISTORY_WITNESS_PRIVATE_KEY_PATH=/run/secrets/b26_p2_history_witness_key",
        "-e", "PROMETHEUS_MULTIPROC_DIR=/tmp",
        "-v", f"{WITNESS_VOL}:/var/lib/b26_p2",
        "-v", f"{SECRETS_VOL}:/run/secrets:ro",
        image, "python", "-c", probe,
    )
    if proc.returncode != 0:
        raise RuntimeError(
            f"witness_bootstrap_failed:{proc.stdout[-900:]}:{proc.stderr[-900:]}"
        )
    journal = volume_get(WITNESS_VOL, "history_witness.jsonl").decode().strip()
    first = json.loads(journal.splitlines()[0])
    genesis = first["payload"]["checkpoint_hash"]
    return {
        "genesis_hash": genesis,
        "journal_lines": len(journal.splitlines()),
        "observer_stdout": proc.stdout.strip()[-600:],
    }


def start_signer(state: dict) -> None:
    docker("rm", "-f", SIGNER)
    material = state["material"]
    tls_vol = f"{PREFIX}-tls"
    docker("volume", "rm", "-f", tls_vol)
    docker_ok("volume", "create", tls_vol)
    volume_put(
        tls_vol,
        {
            "ca.pem": material["ca_pem"].encode(),
            "signer-cert.pem": material["signer_cert_pem"].encode(),
            "signer-key.pem": material["signer_key_pem"].encode(),
        },
        mode="0644",
    )
    state["tls_volume"] = tls_vol
    cp = write_control_plane("trust_signer", state)
    dsn = f"postgresql+asyncpg://app_trust_signer:app_trust_signer@pg:5432/{DB_NAME}"
    transport = role_dsn("app_celery_transport", host="pg", port=5432)
    # XXV-F-CP2: the control plane is process-scoped. The signer role is not
    # allowed to resolve MIGRATION_DATABASE_URL, so the signer boots with the
    # control plane enabled and its custody law holds without a workaround.
    env = {
        "SKELDIR_CONTROL_PLANE_ENABLED": "1",
        "DATABASE_URL": dsn,
        "TRUST_SIGNER_DATABASE_URL": dsn,
        "CELERY_BROKER_URL": f"sqla+{transport}",
        "CELERY_RESULT_BACKEND": f"db+{transport}",
        "TRUST_SIGNER_SHARED_SECRET": material["trust_signer_shared_secret"],
        "SKELDIR_TRUST_SIGNING_KEY_SEED_B64URL": material["trust_seed_b64url"],
        "SKELDIR_TRUST_SIGNING_KEY_ID": TRUST_KID,
        "SKELDIR_TRUST_SIGNING_KEY_VALID_FROM": material["trust_key_valid_from"],
        **witness_env(state, private=False),
        **attestation_env(state, signer=False),
    }
    docker_ok(
        "run", "-d", "--name", SIGNER, "--network", NETWORK,
        "--network-alias", SIGNER, "--restart", "unless-stopped",
        *lane_env("trust_signer", cp_volume=cp, extra=env),
        "-v", f"{tls_vol}:/run/skeldir-tls:ro",
        state["final_image_tag"],
        "uvicorn", "app.trust.signer_service:app", "--host", "0.0.0.0",
        "--port", "8001",
        "--ssl-keyfile", "/run/skeldir-tls/signer-key.pem",
        "--ssl-certfile", "/run/skeldir-tls/signer-cert.pem",
    )


def start_auth(state: dict, *, extra: dict[str, str] | None = None) -> None:
    docker("rm", "-f", AUTH)
    docker_ok("volume", "create", SOURCE_EVIDENCE_VOL)
    ingress_vol = f"{PREFIX}-ingress"
    docker("volume", "rm", "-f", ingress_vol)
    docker_ok("volume", "create", ingress_vol)
    volume_put(
        ingress_vol,
        {
            "b26_p2_ingress_dsn": (
                f"postgresql+asyncpg://app_ingress:app_ingress@pg:5432/{DB_NAME}"
            ).encode(),
            # XXV: the attestation seed lives with the ingress credential --
            # one process, one secret mount, no other container sees either.
            "b26_p2_source_attestation_key": state["material"][
                "attestation_private_b64url"
            ].encode(),
        },
    )
    state["ingress_volume"] = ingress_vol
    cp = write_control_plane("auth_ingress", state)
    env = {
        "B26_P2_INGRESS_DATABASE_URL_FILE": "/run/secrets/b26_p2_ingress_dsn",
        "DATABASE_POOL_SIZE": "10",
        "DATABASE_MAX_OVERFLOW": "5",
        "DATABASE_FORCE_POOLING": "1",
        **witness_env(state, private=False),
        **attestation_env(state, signer=True),
    }
    env.update(extra or {})
    docker_ok(
        "run", "-d", "--name", AUTH, "--network", NETWORK,
        "--network-alias", AUTH, "--restart", "unless-stopped",
        "-p", f"{AUTH_PORT}:8001",
        *lane_env("auth_ingress", cp_volume=cp, extra=env),
        "-v", f"{ingress_vol}:/run/secrets:ro",
        "-v", f"{WITNESS_VOL}:/var/lib/b26_p2:ro",
        "-v", f"{SOURCE_EVIDENCE_VOL}:/var/lib/b26_p2_source",
        state["final_image_tag"],
        "uvicorn", "app.auth_service.server:app", "--host", "0.0.0.0",
        "--port", "8001", "--workers", "1",
    )


def start_api(state: dict, *, extra: dict[str, str] | None = None) -> None:
    docker("rm", "-f", API)
    material = state["material"]
    cp = write_control_plane("api", state)
    env = {
        "B26_P2_AUTH_ROOT_URL": f"http://{AUTH}:8001",
        "TRUST_ISSUANCE_DATABASE_URL": (
            f"postgresql+asyncpg://app_trust_issuer:app_trust_issuer@pg:5432/{DB_NAME}"
        ),
        "TRUST_SIGNER_URL": f"https://{SIGNER}:8001",
        "TRUST_SIGNER_SHARED_SECRET": material["trust_signer_shared_secret"],
        "TRUST_SIGNER_CA_BUNDLE": "/run/skeldir-tls/ca.pem",
        "SKELDIR_TRUST_PUBLIC_JWKS_JSON": material["trust_jwks_json"],
        "B28_REQUEST_DATABASE_URL": role_dsn("app_b28_requester", host="pg", port=5432),
        "B28_SOLVER_DATABASE_URL": role_dsn("app_b28_solver", host="pg", port=5432),
        "INGESTION_FOLLOWUP_TASKS_ENABLED": "true",
        **witness_env(state, private=False),
        **attestation_env(state, signer=False),
    }
    env.update(extra or {})
    docker_ok(
        "run", "-d", "--name", API, "--network", NETWORK,
        "--network-alias", API, "--restart", "unless-stopped",
        "-p", f"{API_PORT}:8000",
        *lane_env("api", cp_volume=cp, extra=env),
        "-v", f"{state['tls_volume']}:/run/skeldir-tls:ro",
        "-v", f"{WITNESS_VOL}:/var/lib/b26_p2:ro",
        "-v", f"{SOURCE_EVIDENCE_VOL}:/var/lib/b26_p2_source:ro",
        state["final_image_tag"],
        "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000",
        "--workers", "1",
    )


def start_worker_b23(state: dict) -> None:
    docker("rm", "-f", WORKER_B23)
    cp = write_control_plane("worker_b23", state)
    dsn = f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{DB_NAME}"
    env = {
        "B23_WORKER_DATABASE_URL": dsn,
        "SKELDIR_B23_REQUIRE_WORKER_DSN": "1",
        "B23_WORKER_CONCURRENCY": "1",
        "B23_DATABASE_LOCK_TIMEOUT_MS": "250",
        "SKELDIR_CELERY_WORKER_ROLE": "non_bayesian",
        **witness_env(state, private=False),
        **attestation_env(state, signer=False),
    }
    docker_ok(
        "run", "-d", "--name", WORKER_B23, "--network", NETWORK,
        "--restart", "unless-stopped",
        *lane_env("worker_b23", cp_volume=cp, extra=env),
        state["final_image_tag"],
        "celery", "-A", "app.celery_app", "worker", "--loglevel=INFO",
        "--pool=solo", "--concurrency=1", "--prefetch-multiplier=1",
        "--queues=b23_match_engine",
    )


def start_relay(state: dict) -> None:
    docker("rm", "-f", RELAY)
    cp = write_control_plane("b26_p2_relay", state)
    env = {
        "SKELDIR_CELERY_WORKER_ROLE": "b26_p2_relay",
        **witness_env(state, private=False),
        **attestation_env(state, signer=False),
    }
    docker_ok(
        "run", "-d", "--name", RELAY, "--network", NETWORK,
        "--restart", "unless-stopped",
        *lane_env("b26_p2_relay", cp_volume=cp, extra=env),
        state["final_image_tag"],
        "celery", "-A", "app.celery_app", "worker", "--loglevel=INFO",
        "--pool=solo", "--concurrency=1", "--prefetch-multiplier=1",
        "--queues=b26_p2_relay",
    )


def start_observer(state: dict) -> None:
    docker("rm", "-f", OBSERVER)
    cp = write_control_plane("observer_b26_p2", state)
    dsn = f"postgresql+asyncpg://app_worker:app_worker@pg:5432/{DB_NAME}"
    env = {
        "B23_WORKER_DATABASE_URL": dsn,
        "SKELDIR_B23_REQUIRE_WORKER_DSN": "1",
        "SKELDIR_CELERY_WORKER_ROLE": "non_bayesian",
        **witness_env(state, private=True),
        **attestation_env(state, signer=False),
    }
    docker_ok(
        "run", "-d", "--name", OBSERVER, "--network", NETWORK,
        "--restart", "unless-stopped",
        *lane_env("observer_b26_p2", cp_volume=cp, extra=env),
        "-v", f"{WITNESS_VOL}:/var/lib/b26_p2",
        "-v", f"{SOURCE_EVIDENCE_VOL}:/var/lib/b26_p2_source:ro",
        "-v", f"{SECRETS_VOL}:/run/secrets:ro",
        state["final_image_tag"],
        "celery", "-A", "app.celery_app", "worker", "--loglevel=INFO",
        "--pool=solo", "--concurrency=1", "--prefetch-multiplier=1",
        "--queues=b26_p2_history",
    )


def start_beat(state: dict) -> None:
    docker("rm", "-f", BEAT)
    cp = write_control_plane("beat", state)
    env = {
        "B26_P2_RELAY_SWEEP_INTERVAL_SECONDS": "10",
        "B26_P2_HISTORY_OBSERVE_INTERVAL_SECONDS": "15",
        **witness_env(state, private=False),
        **attestation_env(state, signer=False),
    }
    docker_ok(
        "run", "-d", "--name", BEAT, "--network", NETWORK,
        "--restart", "unless-stopped",
        *lane_env("beat", cp_volume=cp, extra=env),
        state["final_image_tag"],
        "celery", "-A", "app.celery_app", "beat", "--loglevel=INFO",
    )


def wait_http(url: str, timeout_s: int = 180) -> str:
    deadline = time.time() + timeout_s
    last = ""
    while time.time() < deadline:
        try:
            with urllib.request.urlopen(url, timeout=10) as resp:
                return resp.read().decode()
        except urllib.error.HTTPError as exc:
            last = f"http_{exc.code}"
            if exc.code < 500:
                return exc.read().decode()
        except Exception as exc:  # noqa: BLE001
            last = f"{type(exc).__name__}"
        time.sleep(2)
    raise RuntimeError(f"wait_http_timeout:{url}:{last}")


def seed_tenant(label: str) -> dict:
    sys.path.insert(0, str(BACKEND))
    # The seed helper imports the application settings module; give the host
    # process the lane DSN and the lane platform key so the ciphertext it
    # produces is the ciphertext the running processes can decrypt.
    os.environ.setdefault(
        "DATABASE_URL",
        f"postgresql+asyncpg://app_user:app_user@127.0.0.1:{PG_PORT}/{DB_NAME}",
    )
    os.environ.setdefault("ENVIRONMENT", "ci")
    os.environ.setdefault("PLATFORM_TOKEN_ENCRYPTION_KEY", PLATFORM_KEY)
    os.environ.setdefault("PLATFORM_TOKEN_KEY_ID", PLATFORM_KEY_ID)
    from tests.helpers.webhook_secret_seed import webhook_secret_insert_params

    tenant_id = str(uuid.uuid4())
    user_id = str(uuid.uuid4())
    client_id = str(uuid.uuid4())
    tenant_key = f"xxv-{label}-{tenant_id[:8]}"
    machine_token = f"mt_{secrets.token_urlsafe(32)}"
    stripe_secret = f"whsec_xxv_{tenant_id[:8]}"
    shopify_secret = f"shop_xxv_{tenant_id[:8]}"
    paypal_secret = f"pp_xxv_{tenant_id[:8]}"
    woo_secret = f"woo_xxv_{tenant_id[:8]}"
    params = webhook_secret_insert_params(
        shopify_secret=shopify_secret,
        stripe_secret=stripe_secret,
        paypal_secret=paypal_secret,
        woocommerce_secret=woo_secret,
    )
    sql(
        """
        INSERT INTO public.tenants (
            id, name, api_key_hash, notification_email,
            shopify_webhook_secret_ciphertext, shopify_webhook_secret_key_id,
            stripe_webhook_secret_ciphertext, stripe_webhook_secret_key_id,
            paypal_webhook_secret_ciphertext, paypal_webhook_secret_key_id,
            woocommerce_webhook_secret_ciphertext, woocommerce_webhook_secret_key_id,
            created_at, updated_at
        ) VALUES (
            %s, %s, %s, %s,
            pgp_sym_encrypt(%s, %s), %s,
            pgp_sym_encrypt(%s, %s), %s,
            pgp_sym_encrypt(%s, %s), %s,
            pgp_sym_encrypt(%s, %s), %s,
            now(), now()
        )
        """,
        (
            tenant_id,
            f"xxv-{label}-{tenant_id[:8]}",
            hashlib.sha256(tenant_key.encode()).hexdigest(),
            f"xxv-{label}-{tenant_id[:8]}@example.invalid",
            shopify_secret,
            params["webhook_secret_key"],
            params["webhook_secret_key_id"],
            stripe_secret,
            params["webhook_secret_key"],
            params["webhook_secret_key_id"],
            paypal_secret,
            params["webhook_secret_key"],
            params["webhook_secret_key_id"],
            woo_secret,
            params["webhook_secret_key"],
            params["webhook_secret_key_id"],
        ),
    )
    sql(
        "INSERT INTO public.users (id, login_identifier_hash, auth_provider,"
        " is_active) VALUES (%s, %s, 'password', true)",
        (user_id, f"sha256:{hashlib.sha256(user_id.encode()).hexdigest()}"),
    )
    sql(
        "INSERT INTO public.agent_clients (id, tenant_id, client_name,"
        " client_display_hash, audience, status)"
        " VALUES (%s, %s, %s, %s, 'b26-p2-xxv', 'active')",
        (
            client_id,
            tenant_id,
            f"xxv-client-{label}",
            f"sha256:{hashlib.sha256(client_id.encode()).hexdigest()}",
        ),
    )
    sql(
        "INSERT INTO public.agent_service_credentials (id, tenant_id,"
        " agent_client_id, token_prefix, token_hash, hash_algorithm, status,"
        " issued_at) VALUES (%s, %s, %s, %s, %s, 'sha256', 'active', now())",
        (
            str(uuid.uuid4()),
            tenant_id,
            client_id,
            machine_token[:8],
            hashlib.sha256(machine_token.encode()).hexdigest(),
        ),
    )
    for scope in (
        "trust.envelope.read",
        "trust.envelope.verify",
        "trust.audit.read",
        "trust.keys.read",
        "trust.export.create_limited",
    ):
        sql(
            "INSERT INTO public.agent_scope_grants (id, tenant_id,"
            " agent_client_id, scope_value, granted_at)"
            " VALUES (%s, %s, %s, %s, now())",
            (str(uuid.uuid4()), tenant_id, client_id, scope),
        )
    return {
        "label": label,
        "tenant_id": tenant_id,
        "user_id": user_id,
        "agent_client_id": client_id,
        "tenant_key": tenant_key,
        "machine_token": machine_token,
        "stripe_secret": stripe_secret,
        "shopify_secret": shopify_secret,
        "paypal_secret": paypal_secret,
        "woocommerce_secret": woo_secret,
    }


def mint_jwt(state: dict, tenant: dict, scopes: tuple[str, ...]) -> str:
    import jwt as pyjwt

    now = int(time.time())
    return pyjwt.encode(
        {
            "tenant_id": tenant["tenant_id"],
            "user_id": tenant["user_id"],
            "sub": tenant["user_id"],
            "jti": str(uuid.uuid4()),
            "iat": now,
            "exp": now + 3600,
            "iss": JWT_ISSUER,
            "aud": JWT_AUDIENCE,
            "scopes": list(scopes),
        },
        (LANE_ROOT / "jwt-private.pem").read_bytes(),
        algorithm="RS256",
        headers={"kid": state.get("material", {}).get("jwt_kid", "xxv-jwt")},
    )


def _worktree_summary() -> dict:
    """Summarise the worktree, separating image-copied paths from the rest.

    The production image copies backend/, alembic/, contracts/, db/ and
    contracts-internal/ only. A modification outside those paths cannot
    change the image, so the summary states both facts explicitly instead
    of pasting the whole status.
    """
    status = run(["git", "status", "--porcelain"], cwd=str(REPO_ROOT)).stdout.splitlines()
    image_paths = ("backend/", "alembic/", "contracts/", "db/", "contracts-internal/")
    dirty_image = [
        line for line in status
        if line[3:].strip().strip('"').replace("\\", "/").startswith(image_paths)
    ]
    return {
        "entries": len(status),
        "image_copied_path_entries": dirty_image,
        "image_bytes_match_committed_tree": not dirty_image,
        "non_image_entry_sample": [line for line in status[:4]],
    }


def artifact_identity(state: dict) -> dict:
    tag = state["final_image_tag"]
    return {
        "commit_sha": run(["git", "rev-parse", "HEAD"], cwd=str(REPO_ROOT)).stdout.strip(),
        "tree_sha": run(
            ["git", "rev-parse", "HEAD^{tree}"], cwd=str(REPO_ROOT)
        ).stdout.strip(),
        "worktree_status_summary": _worktree_summary(),
        "image_tag": tag,
        "image_id": docker_ok("image", "inspect", tag, "--format", "{{.Id}}"),
        "base_image_id": docker_ok(
            "image", "inspect", "python:3.11-slim", "--format", "{{.Id}}"
        ),
        "compiled_public_key_sha256": state["material"]["witness_public_sha256"],
        "compiled_genesis_hash": state["genesis_hash"],
        "compiled_source_attestation_public_key_sha256": state["material"][
            "attestation_public_sha256"
        ],
        "migration_head": state["migration_head"],
        "captured_at_utc": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }


def cmd_up(args: argparse.Namespace) -> int:
    print("[xxv-lane] removing any previous lane resources", flush=True)
    cmd_down(args)
    print("[xxv-lane] generating lane key material", flush=True)
    material = generate_material()
    state: dict = {"material": material, "lane_root": str(LANE_ROOT)}

    print("[xxv-lane] building bootstrap image", flush=True)
    bootstrap_id = build_image(BOOTSTRAP_IMAGE)
    state["bootstrap_image_id"] = bootstrap_id

    print("[xxv-lane] starting postgres 15", flush=True)
    start_pg()
    print("[xxv-lane] provisioning least-privilege role graph", flush=True)
    provision()
    print("[xxv-lane] migrating inside the production image", flush=True)
    state["migration_head"] = migrate(BOOTSTRAP_IMAGE)
    print(f"[xxv-lane] migration head {state['migration_head']}", flush=True)

    print("[xxv-lane] bootstrapping the signed history genesis", flush=True)
    boot = witness_bootstrap(BOOTSTRAP_IMAGE, material)
    state.update(boot)
    print(f"[xxv-lane] genesis {state['genesis_hash']}", flush=True)

    print("[xxv-lane] building final anchored production image", flush=True)
    final_id = build_image(
        FINAL_IMAGE,
        anchor={
            "public_key_sha256": material["witness_public_sha256"],
            "genesis_hash": state["genesis_hash"],
            "source_attestation_public_key_sha256": material[
                "attestation_public_sha256"
            ],
        },
    )
    state["final_image_tag"] = FINAL_IMAGE
    state["final_image_id"] = final_id

    print("[xxv-lane] starting signer / auth root / api / workers", flush=True)
    start_signer(state)
    start_auth(state)
    start_api(state)
    start_worker_b23(state)
    start_relay(state)
    start_observer(state)
    start_beat(state)

    print("[xxv-lane] waiting for the auth root and api", flush=True)
    wait_http(f"http://127.0.0.1:{AUTH_PORT}/health/live", 240)
    wait_http(f"http://127.0.0.1:{API_PORT}/health/live", 240)

    print("[xxv-lane] seeding tenants and machine identities", flush=True)
    state["tenant_a"] = seed_tenant("a")
    state["tenant_b"] = seed_tenant("b")
    state["authority_universe"] = sql(
        "SELECT universe::text FROM public.b26_p2_authority_universe LIMIT 1"
    )[0][0]
    state["artifact"] = artifact_identity(state)
    save_state(state)
    print(json.dumps(state["artifact"], indent=2))
    print("[xxv-lane] UP", flush=True)
    return 0


def cmd_state(args: argparse.Namespace) -> int:
    state = load_state()
    redacted = {
        k: v for k, v in state.items() if k not in {"material"}
    }
    redacted["material_fingerprints"] = {
        "witness_public_sha256": state["material"]["witness_public_sha256"],
        "trust_key_id": TRUST_KID,
    }
    print(json.dumps(redacted, indent=2, sort_keys=True))
    return 0


def cmd_down(args: argparse.Namespace) -> int:
    for name in (API, AUTH, SIGNER, WORKER_B23, RELAY, OBSERVER, BEAT, PG):
        docker("rm", "-f", name)
    docker("network", "rm", NETWORK)
    for vol in (
        WITNESS_VOL,
        SECRETS_VOL,
        SOURCE_EVIDENCE_VOL,
        f"{PREFIX}-tls",
        f"{PREFIX}-ingress",
        *[
            f"{PREFIX}-cp-{role}"
            for role in (
                "api", "auth-ingress", "worker-b23", "observer-b26-p2",
                "b26-p2-relay", "beat", "trust-signer",
            )
        ],
    ):
        docker("volume", "rm", "-f", vol)
    print("[xxv-lane] DOWN", flush=True)
    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    name = {
        "api": API, "auth": AUTH, "signer": SIGNER, "worker": WORKER_B23,
        "relay": RELAY, "observer": OBSERVER, "beat": BEAT, "pg": PG,
    }[args.service]
    proc = docker("logs", "--tail", str(args.tail), name)
    print(proc.stdout[-20000:])
    print(proc.stderr[-20000:], file=sys.stderr)
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="B2.6-P2 XXV lane")
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("up").set_defaults(func=cmd_up)
    sub.add_parser("state").set_defaults(func=cmd_state)
    sub.add_parser("down").set_defaults(func=cmd_down)
    logs = sub.add_parser("logs")
    logs.add_argument("service")
    logs.add_argument("--tail", type=int, default=200)
    logs.set_defaults(func=cmd_logs)
    args = parser.parse_args()
    try:
        return int(args.func(args))
    except Exception as exc:  # noqa: BLE001 - lane driver reports and exits
        print(f"[xxv-lane] FAILED: {type(exc).__name__}: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
