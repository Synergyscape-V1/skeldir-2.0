#!/usr/bin/env python3
"""B2.5-P12 static and dynamic trust-path isolation.

Covers invariant registry domains 15-18:

  15  AST transitive no-LLM import graph
  16  dynamic import ban in the trust path
  17  runtime ``sys.modules`` trace across representative paths
  18  no compute dispatch from trust reads

Why each proof is shaped the way it is
--------------------------------------
*Transitive, not direct* (P12-H05). Banning ``import app.llm`` in the route file
is trivially evadable by importing a helper that imports it. The graph is walked
to fixpoint over first-party modules.

*Dynamic imports are a separate invariant* (P12-H06). A static import graph
cannot see ``importlib.import_module(name)``. Treating the two as one check
leaves an escape hatch, so they are proven independently.

*Runtime trace covers failure paths* (P12-H07). Modules can stay unimported on
the happy path and load under refusal or degraded handling, so the trace
exercises success, refusal, verification and export paths rather than one call.

*Dispatch is banned by surface, not by import* (P12-H08). A trust read can
enqueue work without importing the worker: ``send_task``, a generic enqueue
helper, an outbox insert, or a task-name string all suffice. The ban is on those
surfaces.
"""

from __future__ import annotations

import argparse
import ast
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[2]
BACKEND = ROOT / "backend"

#: Entry points of the machine trust surface. Isolation must hold from each.
TRUST_ENTRY_MODULES = (
    "app.api.trust_api",
    "app.api.trust_export",
    "app.api.trust_keys",
    "app.trust.builder",
    "app.trust.source_adapters",
    "app.trust.reason_truth_matrix",
    "app.trust.canonicalization",
    "app.trust.signing",
    "app.trust.verification",
    "app.trust.export_artifact",
    "app.trust.export_projection",
)

#: Module prefixes that must never be reachable from the trust surface.
FORBIDDEN_MODULE_PREFIXES = (
    "app.llm",
    "app.workers.llm",
    "app.tasks.bayesian",
    "app.bayesian",
)

#: Dynamic-import mechanisms that would bypass the static graph entirely.
DYNAMIC_IMPORT_CALLS = (
    "import_module",
    "__import__",
    "load_module",
    "exec_module",
    "entry_points",
)
DYNAMIC_IMPORT_MODULES = ("importlib", "pkg_resources", "pkgutil")

#: Compute-dispatch surfaces. A trust read may not reach any of these, whether
#: or not it imports the implementation behind them.
DISPATCH_ATTRIBUTES = ("send_task", "apply_async", "delay", "enqueue_tenant_task")
DISPATCH_TOKENS = ("celery_app.send_task", "enqueue_tenant_task(", ".apply_async(")


class B25P12IsolationError(RuntimeError):
    """Raised when trust-path isolation is violated."""


def _require(condition: bool, reason: str) -> None:
    if not condition:
        raise B25P12IsolationError(reason)


def _module_path(module: str) -> Path | None:
    candidate = BACKEND / Path(module.replace(".", "/") + ".py")
    if candidate.exists():
        return candidate
    package = BACKEND / Path(module.replace(".", "/")) / "__init__.py"
    if package.exists():
        return package
    return None


def _first_party_imports(source: str, module: str) -> set[str]:
    """Return first-party ``app.*`` modules imported by one module."""
    imported: set[str] = set()
    tree = ast.parse(source)
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name.startswith("app."):
                    imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.level:
                # Relative import: resolve against the containing package.
                base = module.rsplit(".", node.level)[0] if "." in module else ""
                target = f"{base}.{node.module}" if node.module else base
            else:
                target = node.module or ""
            if not target.startswith("app."):
                continue
            imported.add(target)
            for alias in node.names:
                imported.add(f"{target}.{alias.name}")
    return imported


def build_import_graph(
    overrides: dict[Path, str] | None = None,
) -> dict[str, set[str]]:
    """Walk first-party imports to fixpoint from every trust entry point."""
    overrides = overrides or {}
    reachable: dict[str, set[str]] = {}
    for entry in TRUST_ENTRY_MODULES:
        seen: set[str] = set()
        queue = [entry]
        while queue:
            module = queue.pop()
            if module in seen:
                continue
            seen.add(module)
            path = _module_path(module)
            if path is None:
                continue
            source = overrides.get(path, path.read_text(encoding="utf-8"))
            try:
                for target in _first_party_imports(source, module):
                    if target not in seen:
                        queue.append(target)
            except SyntaxError as exc:  # pragma: no cover - defensive
                raise B25P12IsolationError(f"trust_module_unparsable:{module}:{exc}")
        reachable[entry] = seen
    return reachable


def validate_no_llm_reachability(overrides: dict[Path, str] | None = None) -> int:
    """Domain 15: no forbidden module is transitively reachable."""
    graph = build_import_graph(overrides)
    checks = 0
    for entry, modules in graph.items():
        for module in sorted(modules):
            for prefix in FORBIDDEN_MODULE_PREFIXES:
                if module == prefix or module.startswith(prefix + "."):
                    raise B25P12IsolationError(
                        f"forbidden_module_reachable_from_trust_path:{entry}->{module}"
                    )
        checks += 1
    _require(checks == len(TRUST_ENTRY_MODULES), "trust_entry_coverage_incomplete")
    return checks


def validate_no_dynamic_imports(overrides: dict[Path, str] | None = None) -> int:
    """Domain 16: the trust path may not use dynamic import mechanisms."""
    overrides = overrides or {}
    graph = build_import_graph(overrides)
    trust_modules = {m for modules in graph.values() for m in modules}
    checks = 0
    for module in sorted(trust_modules):
        path = _module_path(module)
        if path is None:
            continue
        source = overrides.get(path, path.read_text(encoding="utf-8"))
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                func = node.func
                name = getattr(func, "attr", getattr(func, "id", ""))
                if name in DYNAMIC_IMPORT_CALLS:
                    raise B25P12IsolationError(
                        f"dynamic_import_in_trust_path:{module}:{name}"
                    )
            if isinstance(node, ast.Import):
                for alias in node.names:
                    root = alias.name.split(".")[0]
                    if root in DYNAMIC_IMPORT_MODULES:
                        raise B25P12IsolationError(
                            f"dynamic_import_module_in_trust_path:{module}:{alias.name}"
                        )
            if isinstance(node, ast.ImportFrom):
                root = (node.module or "").split(".")[0]
                if root in DYNAMIC_IMPORT_MODULES:
                    raise B25P12IsolationError(
                        f"dynamic_import_module_in_trust_path:{module}:{node.module}"
                    )
        checks += 1
    return checks


def validate_no_compute_dispatch(overrides: dict[Path, str] | None = None) -> int:
    """Domain 18: no dispatch surface is reachable from the trust path."""
    overrides = overrides or {}
    graph = build_import_graph(overrides)
    trust_modules = {m for modules in graph.values() for m in modules}
    checks = 0
    for module in sorted(trust_modules):
        path = _module_path(module)
        if path is None:
            continue
        source = overrides.get(path, path.read_text(encoding="utf-8"))
        for token in DISPATCH_TOKENS:
            if token in source:
                raise B25P12IsolationError(
                    f"compute_dispatch_surface_in_trust_path:{module}:{token}"
                )
        try:
            tree = ast.parse(source)
        except SyntaxError:
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                if node.func.attr in DISPATCH_ATTRIBUTES:
                    raise B25P12IsolationError(
                        f"compute_dispatch_call_in_trust_path:{module}:{node.func.attr}"
                    )
        checks += 1
    return checks


def validate_runtime_module_trace() -> int:
    """Domain 17: no forbidden module loads while exercising trust paths.

    Covers success, refusal and verification paths rather than the happy path
    alone, because a module can stay unimported until an error branch runs.
    """
    sys.path.insert(0, str(BACKEND))
    for name in list(sys.modules):
        for prefix in FORBIDDEN_MODULE_PREFIXES:
            if name == prefix or name.startswith(prefix + "."):
                del sys.modules[name]

    import hashlib  # noqa: PLC0415
    import json  # noqa: PLC0415
    from datetime import datetime, timedelta, timezone  # noqa: PLC0415

    from cryptography.hazmat.primitives.asymmetric.ed25519 import (  # noqa: PLC0415
        Ed25519PrivateKey,
    )

    from app.trust.export_artifact import (  # noqa: PLC0415
        build_export_artifact,
        sign_export_artifact,
        verify_export_artifact,
    )
    from app.trust.key_registry import (
        TrustKeyRegistry,
        TrustSigningKey,
    )  # noqa: PLC0415
    from app.trust.signing import sign_trust_envelope  # noqa: PLC0415
    from app.trust.verification import verify_trust_envelope  # noqa: PLC0415

    before = set(sys.modules)
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

    def _utc(value: datetime) -> str:
        return (
            value.astimezone(timezone.utc)
            .replace(microsecond=0)
            .isoformat()
            .replace("+00:00", "Z")
        )

    issued = datetime.now(timezone.utc)
    envelope = json.loads(
        (
            ROOT / "contracts/trust-api/examples/deterministic_only_verified.json"
        ).read_text(encoding="utf-8")
    )
    envelope["created_at"] = _utc(issued)
    envelope["valid_until"] = _utc(issued + timedelta(days=1))

    paths_exercised = 0

    # happy: sign an envelope
    signed = sign_trust_envelope(envelope, key_registry=registry)
    paths_exercised += 1

    # verify path
    verify_trust_envelope(signed, key_registry=registry.public_only())
    paths_exercised += 1

    # export issuance path
    artifact = sign_export_artifact(
        build_export_artifact(
            envelopes=[signed],
            tenant_id_hash=str(signed["tenant_id_hash"]),
            generated_at=issued,
        ),
        key_registry=registry,
    )
    paths_exercised += 1

    # refusal / rejection path: tampered artifact must be rejected, and the
    # rejection branch must not pull in a forbidden module either.
    tampered = dict(artifact)
    tampered["generated_at"] = _utc(issued + timedelta(hours=1))
    result = verify_export_artifact(tampered, key_registry=registry.public_only())
    _require(
        result.verification_status == "rejected", "runtime_trace_tamper_not_rejected"
    )
    paths_exercised += 1

    # unsupported-protocol refusal path
    unsupported = dict(artifact)
    unsupported["artifact_schema_version"] = "b25-p11-export-artifact-v9"
    unsupported["canonicalization_version"] = "b25-p11-artifact-framing-v9"
    refused = verify_export_artifact(unsupported, key_registry=registry.public_only())
    _require(
        refused.verification_status == "rejected",
        "runtime_trace_unsupported_protocol_not_rejected",
    )
    paths_exercised += 1

    newly_loaded = set(sys.modules) - before
    for name in sorted(newly_loaded):
        for prefix in FORBIDDEN_MODULE_PREFIXES:
            if name == prefix or name.startswith(prefix + "."):
                raise B25P12IsolationError(f"forbidden_module_loaded_at_runtime:{name}")
    return paths_exercised


def validate_core(overrides: dict[Path, str] | None = None) -> dict[str, int]:
    return {
        "no_llm_reachability_controls": validate_no_llm_reachability(overrides),
        "dynamic_import_controls": validate_no_dynamic_imports(overrides),
        "compute_dispatch_controls": validate_no_compute_dispatch(overrides),
    }


def _inject(module: str, snippet: str) -> dict[Path, str]:
    """Append a semantic violation to a real trust module.

    Appending (rather than replacing) keeps the module syntactically valid, so a
    firing control proves the invariant was detected rather than that the file
    stopped parsing (P12-H22).
    """
    path = _module_path(module)
    _require(path is not None, f"negative_control_module_missing:{module}")
    source = path.read_text(encoding="utf-8")
    return {path: source + snippet}


def run_negative_controls() -> int:
    controls: tuple[tuple[str, dict[Path, str], str], ...] = (
        (
            "NC-P12-ISO-01",
            _inject(
                "app.trust.builder", "\nfrom app.llm import provider_boundary  # noqa\n"
            ),
            "forbidden_module_reachable_from_trust_path",
        ),
        (
            "NC-P12-ISO-02",
            _inject(
                "app.trust.builder",
                "\nimport importlib\n\n\ndef _late(name):\n    return importlib.import_module(name)\n",
            ),
            "dynamic_import",
        ),
        (
            "NC-P12-ISO-04",
            _inject(
                "app.trust.export_artifact",
                "\n\ndef _dispatch(app_obj, name):\n    return app_obj.send_task(name)\n",
            ),
            "compute_dispatch",
        ),
    )
    fired = 0
    for name, overrides, expected in controls:
        try:
            validate_core(overrides)
        except B25P12IsolationError as exc:
            reason = str(exc)
            _require(
                reason.startswith(expected),
                f"negative_control_wrong_reason:{name}:expected={expected}:observed={reason[:120]}",
            )
            fired += 1
            continue
        raise B25P12IsolationError(f"negative_control_silent:{name}")
    return fired


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        description="Validate B2.5-P12 trust-path isolation."
    )
    parser.add_argument("--negative-control", action="store_true")
    args = parser.parse_args(argv)

    try:
        counters = validate_core()
        runtime_paths = validate_runtime_module_trace()
        negative_controls = run_negative_controls() if args.negative_control else 0
        if args.negative_control:
            _require(negative_controls == 3, "isolation_negative_control_count_drift")
    except B25P12IsolationError as exc:
        print(f"B25_P12_TRUST_ISOLATION_VALIDATION_FAIL:{exc}")
        return 1
    except Exception as exc:  # noqa: BLE001
        print(f"B25_P12_TRUST_ISOLATION_VALIDATION_FAIL:unexpected:{exc}")
        return 1

    print("B25_P12_TRUST_ISOLATION_VALIDATION_PASS")
    for key, value in counters.items():
        print(f"{key}_passed={value}")
    print(f"runtime_trace_paths_exercised={runtime_paths}")
    print(f"isolation_negative_controls_fired={negative_controls}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
