from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_provider_boundary_domain_sql_guard_negative_control(tmp_path: Path) -> None:
    root = _repo_root()
    fixture = root / "backend/tests/fixtures/forbidden_provider_boundary_domain_sql_fixture.txt"
    violating = tmp_path / "violating_provider_boundary.py"
    violating.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    res = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/enforce_b16_p1_provider_boundary_domain_sql.py"),
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
    assert "violations:" in combined


def test_provider_boundary_domain_sql_guard_passes_repo_state() -> None:
    root = _repo_root()
    res = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/enforce_b16_p1_provider_boundary_domain_sql.py"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert res.returncode == 0, res.stdout + "\n" + res.stderr
