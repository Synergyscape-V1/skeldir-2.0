from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import yaml


REPO_ROOT = Path(__file__).resolve().parents[2]
ATTRIBUTION_CONTRACT = REPO_ROOT / "api-contracts" / "openapi" / "v1" / "attribution.yaml"


def _run(command: list[str]) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        command,
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
    )


def _write_yaml(path: Path, payload: dict) -> None:
    path.write_text(yaml.safe_dump(payload, sort_keys=False), encoding="utf-8")


def test_b13_p1_contract_authority_gate_passes_repo_state() -> None:
    result = _run([sys.executable, "scripts/ci/enforce_b13_p1_contract_authority.py"])
    assert result.returncode == 0, result.stdout + "\n" + result.stderr


def test_b13_p1_negative_control_detects_missing_lifecycle_route(tmp_path: Path) -> None:
    attribution_doc = yaml.safe_load(ATTRIBUTION_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(attribution_doc, dict)
    removed = attribution_doc.get("paths", {}).pop("/api/attribution/platform-oauth/{platform}/refresh-state", None)
    assert removed is not None

    patched_contract = tmp_path / "attribution.yaml"
    _write_yaml(patched_contract, attribution_doc)

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p1_contract_authority.py",
            "--attribution-contract",
            str(patched_contract),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "missing lifecycle route" in combined


def test_b13_p1_negative_control_detects_wrong_security_binding(tmp_path: Path) -> None:
    attribution_doc = yaml.safe_load(ATTRIBUTION_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(attribution_doc, dict)
    operation = (
        attribution_doc.get("paths", {})
        .get("/api/attribution/platform-oauth/{platform}/authorize", {})
        .get("post")
    )
    assert isinstance(operation, dict)
    operation["security"] = [{"tenantKeyAuth": []}]

    patched_contract = tmp_path / "attribution.yaml"
    _write_yaml(patched_contract, attribution_doc)

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p1_contract_authority.py",
            "--attribution-contract",
            str(patched_contract),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "accessBearerAuth-only" in combined


def test_b13_p1_negative_control_detects_taxonomy_regression(tmp_path: Path) -> None:
    attribution_doc = yaml.safe_load(ATTRIBUTION_CONTRACT.read_text(encoding="utf-8"))
    assert isinstance(attribution_doc, dict)
    enum_values = (
        attribution_doc.get("components", {})
        .get("schemas", {})
        .get("ProviderLifecycleErrorCode", {})
        .get("enum", [])
    )
    assert isinstance(enum_values, list)
    enum_values.remove("provider_rate_limited")

    patched_contract = tmp_path / "attribution.yaml"
    _write_yaml(patched_contract, attribution_doc)

    result = _run(
        [
            sys.executable,
            "scripts/ci/enforce_b13_p1_contract_authority.py",
            "--attribution-contract",
            str(patched_contract),
        ]
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}"
    assert "ProviderLifecycleErrorCode.enum mismatch" in combined
