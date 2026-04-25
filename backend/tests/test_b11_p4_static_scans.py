from __future__ import annotations

import importlib.util
import subprocess
import sys
from pathlib import Path


def _repo_root() -> Path:
    return Path(__file__).resolve().parents[2]


def _load_static_scan_module():
    root = _repo_root()
    script_path = root / "scripts" / "security" / "b11_p4_generate_static_scans.py"
    spec = importlib.util.spec_from_file_location("b11_p4_static_scan_module", script_path)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_b11_p4_static_scan_allowlisted_governed_neon_source(tmp_path: Path) -> None:
    module = _load_static_scan_module()
    repo_root = tmp_path / "repo"
    workflow_path = repo_root / ".github" / "workflows" / "schema-deploy-production.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        "env:\n  GH_NEON_API_KEY: ${{ secrets.NEON_API_KEY }} # b23_p0_governed_secret_source\n",
        encoding="utf-8",
    )

    module.REPO_ROOT = repo_root
    violations = module._scan_workflows([workflow_path])
    assert not violations


def test_b11_p4_static_scan_rejects_neon_secret_without_marker_even_on_governed_path(
    tmp_path: Path,
) -> None:
    module = _load_static_scan_module()
    repo_root = tmp_path / "repo"
    workflow_path = repo_root / ".github" / "workflows" / "schema-deploy-production.yml"
    workflow_path.parent.mkdir(parents=True, exist_ok=True)
    workflow_path.write_text(
        "env:\n  GH_NEON_API_KEY: ${{ secrets.NEON_API_KEY }}\n",
        encoding="utf-8",
    )

    module.REPO_ROOT = repo_root
    violations = module._scan_workflows([workflow_path])
    assert any("prohibited GitHub secret source for high-risk credential" in item for item in violations)


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
