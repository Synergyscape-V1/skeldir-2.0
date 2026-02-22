from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_b11_p4_static_scan_negative_control(tmp_path: Path):
    root = _repo_root()
    scripts_dir = tmp_path / "scripts"
    scripts_dir.mkdir(parents=True, exist_ok=True)
    violating_py = scripts_dir / "violating.py"
    violating_wf = tmp_path / "violating.yml"
    violating_py.write_text(
        "import os\nx=os.getenv('DATABASE_URL')\n",
        encoding="utf-8",
    )
    violating_wf.write_text(
        "name: bad\njobs:\n  x:\n    steps:\n      - run: echo ${{ secrets.NEON_API_KEY }}\n",
        encoding="utf-8",
    )

    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p4_generate_static_scans.py"),
            "--out-dir",
            str(tmp_path / "out"),
            "--python-paths",
            str(violating_py),
            "--workflow-paths",
            str(violating_wf),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode != 0


def test_b11_p4_static_scan_passes_repo_state():
    root = _repo_root()
    result = subprocess.run(
        [
            sys.executable,
            str(root / "scripts/security/b11_p4_generate_static_scans.py"),
            "--out-dir",
            str(root / "docs/forensics/evidence/b11_p4"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=root,
    )
    assert result.returncode == 0, result.stdout + "\n" + result.stderr
