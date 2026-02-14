from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_provider_dependency_scanner_has_negative_control(tmp_path: Path):
    root = _repo_root()
    fixture = root / "backend/tests/fixtures/forbidden_provider_import_fixture.txt"
    content = fixture.read_text(encoding="utf-8")
    violating = tmp_path / "violating_module.py"
    violating.write_text(content + "\n", encoding="utf-8")

    res = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/enforce_llm_provider_boundary.py"),
            "--paths",
            str(violating),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert res.returncode != 0
    combined = (res.stdout + "\n" + res.stderr).lower()
    assert "provider dependency references" in combined


def test_provider_dependency_scanner_rejects_direct_call_pattern(tmp_path: Path):
    root = _repo_root()
    fixture = root / "backend/tests/fixtures/forbidden_direct_provider_call_fixture.txt"
    violating = tmp_path / "violating_direct_call.py"
    violating.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    res = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/enforce_llm_provider_boundary.py"),
            "--paths",
            str(violating),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert res.returncode != 0
    combined = (res.stdout + "\n" + res.stderr).lower()
    assert "provider dependency references" in combined


def test_provider_dependency_scanner_passes_repo_state():
    root = _repo_root()
    res = subprocess.run(
        [sys.executable, str(root / "scripts/ci/enforce_llm_provider_boundary.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
