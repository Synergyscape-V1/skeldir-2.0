from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_secret_chokepoint_scanner_has_negative_control(tmp_path: Path):
    root = _repo_root()
    fixture = root / "backend/tests/fixtures/forbidden_secret_access_fixture.txt"
    violating = tmp_path / "violating_secret_read.py"
    violating.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p2_secret_chokepoint_guard.py"),
            "--paths",
            str(violating),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode != 0
    combined = f"{result.stdout}\n{result.stderr}".lower()
    assert "forbidden settings secret access" in combined


def test_secret_chokepoint_scanner_passes_repo_state():
    root = _repo_root()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p2_secret_chokepoint_guard.py"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
