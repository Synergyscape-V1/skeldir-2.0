"""B2.6-P2 Corrective XVI authority-governance gates.

H-XVI-R10 (capability custody): only the sovereign authentication-root
service may acquire the ingress credential under supported runtime
configuration. Any manifest change that mounts the credential (or the
auth role) into an ordinary service REDs.

H-XVI-R11 (call-path dominance): exactly the two production call sites
may reach b26_p2_authenticate_ingress_atomic, and both are dominated by
verification -> derivation -> binding. A new direct caller REDs.

H-XVI-R5 (lineage consumer census): webhook_ingress_identities.event_id
is lookup-hint/adoption-binding only. Any new production reader outside
the allowlist REDs (tripwire; the load-bearing proof is the behavioral
rebind experiment in the physics validator).

H-XVI-R15 (operational wiring): every required internal async edge is
registered, routed, and scheduled. Removing a queue route, task
registration, or Beat entry REDs.
"""

import re
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[3]
APP_ROOT = REPO_ROOT / "backend" / "app"

_INGRESS_FILE_TOKEN = "B26_P2_INGRESS_DATABASE_URL_FILE"
_INGRESS_SECRET_PATH = "/run/secrets/b26_p2_ingress_dsn"


def test_xvi_procfile_custody() -> None:
    """Only the auth_ingress Procfile process may hold the credential."""
    lines = (REPO_ROOT / "Procfile").read_text(encoding="utf-8").splitlines()
    holders = []
    for line in lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#") or ":" not in stripped:
            continue
        name, _, command = stripped.partition(":")
        name = name.strip()
        if _INGRESS_FILE_TOKEN not in command:
            continue
        assignments = re.findall(
            rf"{_INGRESS_FILE_TOKEN}=([^\s]*)", command
        )
        if any(v.strip() for v in assignments):
            holders.append(name)
    assert holders == ["auth_ingress"], holders


def test_xvi_procfile_auth_role_unique() -> None:
    """SKELDIR_PROCESS_ROLE=auth_ingress appears on one process only."""
    lines = (REPO_ROOT / "Procfile").read_text(encoding="utf-8").splitlines()
    holders = [
        line.split(":")[0].strip()
        for line in lines
        if "SKELDIR_PROCESS_ROLE=auth_ingress" in line
        and not line.strip().startswith("#")
    ]
    assert holders == ["auth_ingress"], holders


def test_xvi_compose_custody() -> None:
    """Compose services other than auth must blank the credential file."""
    offenders = []
    for compose in sorted(REPO_ROOT.glob("docker-compose*.yml")):
        text = compose.read_text(encoding="utf-8")
        # Split loosely on service blocks; flag non-empty FILE assignments
        # outside an auth service block (comments excluded).
        current_service = None
        for raw_line in text.splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            svc = re.match(r"^  ([A-Za-z0-9_.-]+):\s*$", raw_line)
            if svc:
                current_service = svc.group(1)
            if _INGRESS_FILE_TOKEN in line and current_service:
                value = line.split(":", 1)[-1].strip().strip("\"'")
                if value and value not in ("", '""', "''"):
                    if "auth" not in current_service:
                        offenders.append(
                            f"{compose.name}:{current_service}:{line.strip()}"
                        )
    assert offenders == [], offenders


def _production_atomic_callers() -> dict[str, str]:
    """Non-test production files invoking the atomic transition."""
    callers = {}
    for path in sorted((APP_ROOT).rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        if "b26_p2_authenticate_ingress_atomic(" in text:
            callers[path.relative_to(REPO_ROOT).as_posix()] = text
    return callers


def test_xvi_atomic_callers_closed() -> None:
    """Exactly the two dominated production call sites may reach atomic."""
    callers = _production_atomic_callers()
    assert sorted(callers) == [
        "backend/app/auth_service/server.py",
        "backend/app/ingestion/event_service.py",
    ], sorted(callers)


def test_xvi_atomic_callers_dominated() -> None:
    """Every production caller proves verification->derivation->binding."""
    callers = _production_atomic_callers()
    # The root verifies signatures, derives, and compares binding.
    server = callers["backend/app/auth_service/server.py"]
    for token in (
        "verifier(",
        "derive_commerce(",
        "binding_mismatches(",
        "b26_p2_handoff_binding_refused",
        "_require_auth_role()",
    ):
        assert token in server, token
    # The finalizer admits only HMAC-established arrivals and enforces
    # the shared sovereign binding law on both its paths.
    finalizer = callers["backend/app/ingestion/event_service.py"]
    for token in (
        "_assert_sovereign_finalization_binding",
        'context="relay"',
        'context="direct"',
        "finalization_no_auth_consequence",
        "b26_p2_atomic_sovereign_duplicate_refused",
    ):
        assert token in finalizer, token


def test_xvi_event_id_consumers_allowlisted() -> None:
    """New production readers of ingress.event_id must be reviewed."""
    allowed_files = {
        "backend/app/api/webhooks.py",  # dispatch + re-drive lookup hints
        "backend/app/ingestion/event_service.py",  # adoption linkage writes
        "backend/app/auth_service/server.py",  # routing identity intake
    }
    offenders = []
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = str(path.relative_to(REPO_ROOT))
        if rel not in allowed_files:
            continue
        text = path.read_text(encoding="utf-8")
        if rel == "backend/app/api/webhooks.py":
            # Only the two lookup-hint predicates may filter on it.
            uses = [
                m.start()
                for m in re.finditer(r"i\.event_id\s*=\s*:event_id", text)
            ]
            assert len(uses) == 2, f"dispatch lookup-hint count changed: {uses}"
        if rel == "backend/app/ingestion/event_service.py":
            # Writes only via the documented adoption bindings.
            assert "existing.event_id = event_id" in text
    # No other production module may reference the ingress linkage.
    for path in sorted(APP_ROOT.rglob("*.py")):
        rel = path.relative_to(REPO_ROOT).as_posix()
        if rel in allowed_files:
            continue
        text = path.read_text(encoding="utf-8")
        if "webhook_ingress_identities" in text and ".event_id" in text:
            offenders.append(rel)
    assert offenders == [], offenders


def test_xvi_operational_wiring_registered() -> None:
    """Required async edges exist: task, route, queue, Beat entry."""
    celery_app = (APP_ROOT / "celery_app.py").read_text(encoding="utf-8")
    queues = (APP_ROOT / "core" / "queues.py").read_text(encoding="utf-8")
    assert 'QUEUE_B23_MATCH_ENGINE = "b23_match_engine"' in queues
    assert 'QUEUE_B26_P2_RELAY = "b26_p2_relay"' in queues
    assert "QUEUE_B23_MATCH_ENGINE" in celery_app
    assert "QUEUE_B26_P2_RELAY" in celery_app
    assert "app.tasks.revenue_verification.*" in celery_app
    assert "app.tasks.b26_p2_relay.*" in celery_app
    beat = (APP_ROOT / "tasks" / "beat_schedule.py").read_text(encoding="utf-8")
    assert "b26-p2-relay-sweep" in beat
    assert "app.tasks.b26_p2_relay.relay_b26_p2_pending_dispatches" in beat
    relay = (APP_ROOT / "tasks" / "b26_p2_relay.py").read_text(encoding="utf-8")
    assert "def relay_b26_p2_pending_dispatches" in relay or (
        "relay_b26_p2_pending_dispatches" in relay
    )
    worker = (APP_ROOT / "tasks" / "revenue_verification.py").read_text(
        encoding="utf-8"
    )
    assert "execute_b23_batch_match_engine" in worker


def test_xvi_api_isolation_refuses_smuggled_credential(monkeypatch) -> None:
    """A mis-mounted API process refuses to serve (fail closed)."""
    from app.db.session import assert_api_ingress_isolation  # noqa: PLC0415

    monkeypatch.setenv("SKELDIR_PROCESS_ROLE", "api")
    monkeypatch.setenv(
        "B26_P2_INGRESS_DATABASE_URL_FILE", "/run/secrets/b26_p2_ingress_dsn"
    )
    try:
        with __import__("pytest").raises(RuntimeError):
            assert_api_ingress_isolation()
    finally:
        monkeypatch.undo()


def test_xvi_scope_classification_consumes_no_linkage() -> None:
    """Scope truth cannot depend on the mutable event linkage (R5).

    Structural complement to the behavioral rebind proof in the physics
    validator: the canonical classifier's parameter list must not admit
    the ingress event linkage at all, so no future change can smuggle
    it into scope truth without REDing this gate.
    """
    import inspect  # noqa: PLC0415

    from app.finance_reconciliation.scope_authority import (  # noqa: PLC0415
        classify_candidate,
    )

    params = set(inspect.signature(classify_candidate).parameters)
    assert "event_id" not in params
    assert "idempotency_key" not in params
    assert "linkage" not in params


def test_xvi_no_caller_guc_privilege() -> None:
    """No new caller-controlled context may carry P2 privilege (R22)."""
    forbidden = ["current_setting('app.", 'current_setting("app.']
    offenders = []
    for path in sorted((APP_ROOT / "webhooks").rglob("*.py")):
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")
    for path in [
        APP_ROOT / "auth_service" / "server.py",
        APP_ROOT / "ingestion" / "event_service.py",
    ]:
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            if token in text:
                offenders.append(f"{path.name}:{token}")
    assert offenders == [], offenders
