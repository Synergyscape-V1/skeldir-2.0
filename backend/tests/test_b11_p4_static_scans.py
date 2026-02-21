from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def test_b11_p4_static_scan_negative_control(tmp_path: Path):
    root = _repo_root()
    violating_py = tmp_path / "violating.py"
    violating_wf = tmp_path / "violating.yml"
    violating_py.write_text(
        "import os\nfrom app.core.config import settings\nx=settings.DATABASE_URL\ny=os.getenv('LLM_PROVIDER_API_KEY')\n",
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
