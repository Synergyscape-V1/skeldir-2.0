#!/usr/bin/env python3
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import tempfile
import zipfile
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]


def _run(cmd: list[str]) -> tuple[int, str, str]:
    try:
        proc = subprocess.run(cmd, capture_output=True, text=True, check=False)
    except FileNotFoundError as exc:
        return 127, "", f"{exc.__class__.__name__}: {exc}"
    return proc.returncode, (proc.stdout or "").strip(), (proc.stderr or "").strip()


def _aws_bin() -> str:
    explicit = os.getenv("AWS_CLI_BIN")
    if explicit:
        return explicit
    return "aws.cmd" if os.name == "nt" else "aws"


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        while True:
            chunk = fh.read(8192)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def _canonical_json(data: dict) -> str:
    return json.dumps(data, sort_keys=True, separators=(",", ":"), ensure_ascii=True)


def _read_sums(path: Path) -> tuple[str, str]:
    zip_sha = ""
    manifest_digest = ""
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        m = re.match(r"^([0-9a-f]{64})\s+\S+$", line)
        if m:
            zip_sha = m.group(1)
            continue
        if line.startswith("manifest_digest="):
            manifest_digest = line.split("=", 1)[1].strip()
    if not zip_sha or not manifest_digest:
        raise ValueError("sha256SUMS.txt missing zip sha or manifest_digest")
    return zip_sha, manifest_digest


def _download_s3_uri(aws: str, uri: str, out_path: Path) -> None:
    cmd = [aws, "s3", "cp", uri, str(out_path)]
    code, out, err = _run(cmd)
    if code != 0:
        raise RuntimeError(f"failed to download evidence bundle: cmd={' '.join(cmd)} stderr={err} stdout={out}")


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify B11-P6 durable evidence bundle and manifest chain")
    parser.add_argument("--evidence-dir", default="docs/forensics/evidence/b11_p6")
    args = parser.parse_args()

    evidence_dir = (REPO_ROOT / args.evidence_dir).resolve()
    manifest_path = evidence_dir / "MANIFEST.json"
    sums_path = evidence_dir / "sha256SUMS.txt"
    pointer_path = evidence_dir / "evidence_bundle_pointer.txt"

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    expected_zip_sha, expected_manifest_digest = _read_sums(sums_path)

    bundle_uri = ""
    for line in pointer_path.read_text(encoding="utf-8").splitlines():
        if line.startswith("bundle_uri="):
            bundle_uri = line.split("=", 1)[1].strip()
            break
    if not bundle_uri:
        raise ValueError("evidence_bundle_pointer.txt missing bundle_uri")

    aws = _aws_bin()
    with tempfile.TemporaryDirectory(prefix="b11_p6_verify_") as tmp_dir:
        bundle_local = Path(tmp_dir) / "bundle.zip"
        _download_s3_uri(aws=aws, uri=bundle_uri, out_path=bundle_local)
        actual_zip_sha = _sha256(bundle_local)
        if actual_zip_sha != expected_zip_sha:
            raise RuntimeError(
                f"zip sha mismatch expected={expected_zip_sha} actual={actual_zip_sha} uri={bundle_uri}"
            )

        with zipfile.ZipFile(bundle_local, "r") as zf:
            names = set(zf.namelist())
            for filename, expected_hash in manifest.get("artifact_hashes", {}).items():
                if filename not in names:
                    raise RuntimeError(f"bundle missing file listed in manifest: {filename}")
                data = zf.read(filename)
                actual_hash = hashlib.sha256(data).hexdigest()
                if actual_hash != expected_hash:
                    raise RuntimeError(
                        f"artifact hash mismatch for {filename}: expected={expected_hash} actual={actual_hash}"
                    )

    canonical_subset = manifest.get("canonical_subset", {})
    actual_manifest_digest = hashlib.sha256(_canonical_json(canonical_subset).encode("utf-8")).hexdigest()
    if actual_manifest_digest != manifest.get("manifest_digest"):
        raise RuntimeError(
            "manifest digest mismatch between canonical subset and MANIFEST.json field "
            f"expected={manifest.get('manifest_digest')} actual={actual_manifest_digest}"
        )
    if actual_manifest_digest != expected_manifest_digest:
        raise RuntimeError(
            f"manifest digest mismatch with sha256SUMS.txt expected={expected_manifest_digest} actual={actual_manifest_digest}"
        )

    failed_telemetry = [
        name for name, ok in manifest.get("telemetry_validation", {}).items() if not bool(ok)
    ]
    if failed_telemetry:
        raise RuntimeError("telemetry validation failed for: " + ",".join(failed_telemetry))

    print("b11_p6_evidence_verification=PASS")
    print(f"bundle_uri={bundle_uri}")
    print(f"bundle_sha256={expected_zip_sha}")
    print(f"manifest_digest={expected_manifest_digest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
