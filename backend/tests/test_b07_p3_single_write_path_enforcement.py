from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_single_write_path_scanner_has_negative_control(tmp_path: Path):
    root = _repo_root()
    fixture = root / "backend/tests/fixtures/forbidden_llm_api_call_write_fixture.txt"
    violating = tmp_path / "violating_llm_write.py"
    violating.write_text(fixture.read_text(encoding="utf-8"), encoding="utf-8")

    res = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/ci/enforce_llm_api_call_single_write_path.py"),
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
    assert "llmapicall constructor" in combined or "insert(llmapicall)" in combined


def test_single_write_path_scanner_passes_repo_state():
    root = _repo_root()
    res = subprocess.run(
        [sys.executable, str(root / "scripts/ci/enforce_llm_api_call_single_write_path.py")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert res.returncode == 0, res.stdout + "\n" + res.stderr

