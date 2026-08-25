from __future__ import annotations

import ast
import importlib.util
import json
import os
from pathlib import Path

import pytest

from app.bayesian.sampling_policy import DEFAULT_P6_SAMPLING_POLICY
from app.bayesian.child_environment import build_sampler_child_env
from app.bayesian.compiledir_reaper import (
    create_compiledir_lease,
    reap_expired_compiledirs,
)
from app.bayesian.runtime_policy import (
    apply_native_runtime_environment,
    build_runtime_policy,
    resolved_runtime_authority_from_env,
)
from app.bayesian.sampler_supervisor import (
    build_child_env_for_lease,
    run_supervised_sampler,
    sampler_child_command,
    synthetic_blocking_child_command,
    synthetic_noisy_child_command,
)


ROOT = Path(__file__).resolve().parents[2]
RUNTIME_STATE = ROOT / "backend/app/bayesian/runtime_state.py"
RUNTIME_PROBE = ROOT / "backend/app/bayesian/runtime_probe.py"
FIT_EXECUTION = ROOT / "backend/app/bayesian/fit_execution.py"
SAMPLER_CHILD = ROOT / "backend/app/bayesian/sampler_child.py"


def test_b24_p5_thread_budget_rejects_oversubscription(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("B24_BAYESIAN_WORKER_CONCURRENCY", "4")
    monkeypatch.setenv("B24_PYMC_CORES", "4")
    monkeypatch.setenv("B24_BLAS_TOTAL_THREADS", "4")
    monkeypatch.setenv("B24_BAYESIAN_CPU_BUDGET", "2")
    with pytest.raises(RuntimeError, match="thread budget"):
        build_runtime_policy()


def test_b24_p5_timeout_hierarchy_is_enforced(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("B24_SAMPLER_SUPERVISOR_DEADLINE_S", "300")
    monkeypatch.setenv("BAYESIAN_TASK_SOFT_TIME_LIMIT_S", "270")
    monkeypatch.setenv("BAYESIAN_TASK_TIME_LIMIT_S", "360")
    with pytest.raises(RuntimeError, match="timeout hierarchy"):
        build_runtime_policy()


def test_b24_p5_runtime_sets_thread_caps_and_compiledir(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    monkeypatch.setenv("B24_PYTENSOR_EXECUTION_ID", "unit-test-execution")
    monkeypatch.setenv("B24_BAYESIAN_WORKER_RUNTIME_ID", "unit-worker")
    monkeypatch.setenv("B24_BLAS_TOTAL_THREADS", "1")
    policy = apply_native_runtime_environment()
    assert Path(policy.compiledir).exists()
    assert "unit-worker" in Path(policy.compiledir).parts
    assert f"parent-{os.getpid()}" in Path(policy.compiledir).parts
    assert "unit-test-execution" in Path(policy.compiledir).parts
    assert os.environ["OMP_NUM_THREADS"] == "1"
    assert os.environ["OPENBLAS_NUM_THREADS"] == "1"
    assert "base_compiledir=" in os.environ["PYTENSOR_FLAGS"]


def test_b24_p5_supervisor_kills_blocking_child(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    pythonpath = str(ROOT / "backend")
    monkeypatch.setenv("PYTHONPATH", pythonpath)
    result = run_supervised_sampler(
        synthetic_blocking_child_command(seconds=30), deadline_seconds=0.5
    )
    assert result.status == "timeout"
    assert result.killed_by_supervisor is True
    assert result.orphan_reaped is True


@pytest.mark.parametrize("stream", ["stdout", "stderr"])
def test_b24_p6_supervisor_drains_byte_capped_child_streams(
    monkeypatch: pytest.MonkeyPatch,
    stream: str,
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    result = run_supervised_sampler(
        synthetic_noisy_child_command(stream=stream, byte_count=160 * 1024),
        deadline_seconds=5,
        stream_capture_limit_bytes=4096,
    )
    captured = result.stdout if stream == "stdout" else result.stderr
    other = result.stderr if stream == "stdout" else result.stdout
    assert result.status == "completed"
    assert result.returncode == 0
    assert captured.total_bytes == 160 * 1024
    assert len(captured.retained_bytes) == 4096
    assert captured.truncated is True
    assert other.total_bytes == 0


def test_b24_p6_stage_markers_are_fsynced_before_sigkill(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    marker = tmp_path / "execution" / "stage-markers.jsonl"
    lease = create_compiledir_lease(
        execution_id="stage-marker-kill-unit", worker_id="unit-worker"
    )
    env = build_child_env_for_lease(
        lease,
        source_env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "backend"),
            "B24_STAGE_MARKER_PATH": str(marker),
        },
    )
    result = run_supervised_sampler(
        sampler_child_command(mode="stage-marker-kill", seconds=1),
        deadline_seconds=10,
        env=env,
        compiledir_lease=lease,
    )
    stages = [
        json.loads(line)["stage"]
        for line in marker.read_text(encoding="utf-8").splitlines()
    ]
    assert result.status == "completed"
    assert result.killed_by_supervisor is False
    assert stages == ["input_loaded"]
    assert not lease.path.exists()


def test_b24_p6_has_no_shadow_result_staging() -> None:
    text = FIT_EXECUTION.read_text(encoding="utf-8")
    assert "stage_sampler_result" not in text
    assert "find_latest_staged_sampler_result" not in text
    assert "result_staging" not in text
    assert "execution_storage" not in text
    assert "staged_result_path" not in text
    assert not (ROOT / "backend/app/bayesian/result_staging.py").exists()
    assert not (ROOT / "backend/app/bayesian/execution_storage.py").exists()


def test_b24_p6_real_fit_child_emits_bounded_unvalidated_summary(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    if importlib.util.find_spec("pymc") is None:
        pytest.skip("PyMC is not installed in this test environment")
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    execution_dir = tmp_path / "execution"
    execution_dir.mkdir()
    input_path = execution_dir / "input.json"
    output = execution_dir / "result.json"
    marker = execution_dir / "stage-markers.jsonl"
    input_path.write_text(
        json.dumps(
            {
                "execution_id": "real-fit-unit",
                "fit_id": "0bd2d855-dceb-4039-bd98-5848edb269c7",
                "random_seed": 42,
                "max_samples": DEFAULT_P6_SAMPLING_POLICY.total_chain_iterations,
                "max_cores": 1,
                "observed_signal": [0.0, 0.1, -0.1],
                "worker_runtime_authority": resolved_runtime_authority_from_env(),
            },
            sort_keys=True,
        ),
        encoding="utf-8",
    )
    lease = create_compiledir_lease(
        execution_id="real-fit-unit", worker_id="unit-worker"
    )
    env = build_child_env_for_lease(
        lease,
        source_env={
            **os.environ,
            "PYTHONPATH": str(ROOT / "backend"),
            "B24_STAGE_MARKER_PATH": str(marker),
        },
    )
    result = run_supervised_sampler(
        sampler_child_command(
            mode="real-fit",
            input_path=input_path,
            output=output,
            seconds=1,
        ),
        deadline_seconds=30,
        env=env,
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    stages = [
        json.loads(line)["stage"]
        for line in marker.read_text(encoding="utf-8").splitlines()
    ]
    assert result.status == "completed"
    assert result.returncode == 0
    assert payload["status"] == "sampled_unvalidated"
    # Read from the policy. These were 1 and 64, and the pair was F-11 in two
    # literals: one chain makes R-hat undefined, and 64 draws cannot reach an
    # effective sample size of 400. A proof that pinned them could only ever
    # have stayed green by expecting the sampler to fail its own diagnostics.
    assert payload["n_chains"] == DEFAULT_P6_SAMPLING_POLICY.chains
    assert (
        payload["n_samples_actual"] == DEFAULT_P6_SAMPLING_POLICY.posterior_draws_total
    )
    assert "posterior" not in payload
    assert "trace" not in payload
    assert stages == [
        "input_loaded",
        "model_built",
        "graph_compiling",
        "graph_compiled",
        "sampling_started",
        "sampling_completed",
        "result_written",
    ]


def test_b24_p6_parent_orchestration_keeps_pymc_child_only() -> None:
    tree = ast.parse(FIT_EXECUTION.read_text(encoding="utf-8"))
    imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    from_imports = {
        node.module
        for node in tree.body
        if isinstance(node, ast.ImportFrom) and node.module is not None
    }
    assert "pymc" not in imports
    assert "pymc" not in from_imports
    assert "app.bayesian.sampler_child" not in from_imports


def test_b24_p6_parent_recomputes_after_db_failure_without_staging() -> None:
    text = FIT_EXECUTION.read_text(encoding="utf-8")
    child_pos = text.find("result = run_supervised_sampler")
    persist_tx_pos = text.find("with engine.begin() as conn:", child_pos)
    persist_call_pos = text.find("_persist_result_summary(", persist_tx_pos)
    cleanup_pos = text.rfind(
        "cleanup_fit_attempt(workspace=workspace, compiledir=lease)"
    )
    assert -1 not in {child_pos, persist_tx_pos, persist_call_pos, cleanup_pos}
    assert "cleanup_compiledir_on_exit=False" in text
    assert "except" not in text[persist_tx_pos:persist_call_pos]
    assert child_pos < persist_tx_pos < persist_call_pos < cleanup_pos


def test_b24_p6_child_model_is_trivial_physics_probe() -> None:
    text = SAMPLER_CHILD.read_text(encoding="utf-8")
    tree = ast.parse(text)
    pymc_calls = [
        node.func.attr
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pm"
    ]
    assert pymc_calls.count("Model") == 1
    assert pymc_calls.count("Normal") == 2
    assert "HalfNormal" not in pymc_calls
    assert "campaign" not in text.lower()
    assert "provider" not in text.lower()
    assert "marketing" not in text.lower()


def test_b24_p6_stage_markers_wrap_physical_operations() -> None:
    text = SAMPLER_CHILD.read_text(encoding="utf-8")
    model_pos = text.find("with pm.Model() as model:")
    observed_pos = text.find('pm.Normal("observed_signal"', model_pos)
    model_built_pos = text.find('emit_stage_marker("model_built"', observed_pos)
    graph_compiling_pos = text.find(
        'emit_stage_marker("graph_compiling"', model_built_pos
    )
    compile_pos = text.find("model.compile_logp()", graph_compiling_pos)
    graph_compiled_pos = text.find('emit_stage_marker("graph_compiled"', compile_pos)
    sampling_started_pos = text.find(
        'emit_stage_marker("sampling_started"', graph_compiled_pos
    )
    assert -1 not in {
        model_pos,
        observed_pos,
        model_built_pos,
        graph_compiling_pos,
        compile_pos,
        graph_compiled_pos,
        sampling_started_pos,
    }
    assert (
        model_pos
        < observed_pos
        < model_built_pos
        < graph_compiling_pos
        < compile_pos
        < graph_compiled_pos
        < sampling_started_pos
    )


def test_b24_p5_child_env_is_allowlisted(tmp_path: Path) -> None:
    source_env = {
        "PATH": os.environ.get("PATH", ""),
        "SystemRoot": os.environ.get("SystemRoot", ""),
        "COMSPEC": os.environ.get("COMSPEC", ""),
        "PYTHONPATH": str(ROOT / "backend"),
        "DATABASE_URL": "postgresql://should:not@leak/db",
        "SKELDIR_FAKE_PARENT_SECRET": "nope",
        "AWS_SECRET_ACCESS_KEY": "nope",
        "B24_BLAS_TOTAL_THREADS": "1",
    }
    env = build_sampler_child_env(
        compiledir=tmp_path / "worker" / f"parent-{os.getpid()}" / "fit-123",
        execution_id="fit-123",
        source_env=source_env,
    )
    assert "PATH" in env
    assert "DATABASE_URL" not in env
    assert "SKELDIR_FAKE_PARENT_SECRET" not in env
    assert "AWS_SECRET_ACCESS_KEY" not in env
    assert "B24_PYTENSOR_COMPILEDIR" in env
    assert env["B24_SAMPLER_CHILD_BOOTSTRAP"] == "1"
    assert env["PYTENSORRC"] == os.devnull
    assert env["USER"] == "skeldir_sampler"
    assert env["USERPROFILE"].endswith("_home")
    if os.name == "nt":
        assert env["SystemRoot"] == source_env["SystemRoot"]
        assert env["SYSTEMROOT"] == source_env["SystemRoot"]
        assert env["COMSPEC"] == source_env["COMSPEC"]


def test_b24_p5_child_runtime_blocks_db_imports(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    lease = create_compiledir_lease(
        execution_id="import-airgap-unit", worker_id="unit-worker"
    )
    output = tmp_path / "child-import.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="import-negative", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.status == "completed"
    assert "sqlalchemy" in payload["blocked_imports"]
    assert "app.bayesian.runtime_state" in payload["blocked_imports"]
    assert payload["boot_airgap_active"] is True
    assert payload["multiprocessing_policy"] == "single-process"
    assert payload["preinstall_forbidden_modules"] == []
    assert payload["pre_attempt_forbidden_modules"] == []
    assert payload["post_attempt_forbidden_modules"] == []
    assert not payload["unexpected_imports"]
    assert not lease.path.exists()


def test_b24_p5_child_boot_airgap_reports_preinstall_cache_empty(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    lease = create_compiledir_lease(
        execution_id="boot-airgap-unit", worker_id="unit-worker"
    )
    output = tmp_path / "child-boot.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="boot-report", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.status == "completed"
    assert payload["boot_airgap_active"] is True
    assert payload["preinstall_forbidden_modules"] == []
    assert payload["cached_forbidden_modules"] == []
    assert payload["multiprocessing_guard_active"] is True
    assert payload["multiprocessing_policy"] == "single-process"


def test_b24_p5_child_fork_and_default_multiprocessing_are_blocked(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("PYTHONPATH", str(ROOT / "backend"))
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    lease = create_compiledir_lease(
        execution_id="fork-negative-unit", worker_id="unit-worker"
    )
    output = tmp_path / "child-fork-negative.json"
    result = run_supervised_sampler(
        sampler_child_command(mode="fork-negative", output=output, seconds=1),
        deadline_seconds=10,
        env=build_child_env_for_lease(lease),
        compiledir_lease=lease,
    )
    payload = json.loads(output.read_text(encoding="utf-8"))
    assert result.status == "completed"
    blocked = payload["blocked_controls"]
    assert "multiprocessing.get_context('fork')" in blocked
    assert "multiprocessing.get_context()" in blocked
    assert "multiprocessing.Process" in blocked
    if os.name != "nt":
        assert "os.fork" in blocked


def test_b24_p5_reaper_preserves_foreign_and_deletes_expired_owned(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setenv("B24_PYTENSOR_ROOT", str(tmp_path / "root"))
    lease = create_compiledir_lease(execution_id="expired", worker_id="unit-worker")
    metadata_path = lease.path / "skeldir_compiledir_owner.json"
    metadata = json.loads(metadata_path.read_text(encoding="utf-8"))
    metadata["created_at"] = 1
    metadata["parent_pid"] = 99999999
    metadata_path.write_text(json.dumps(metadata, sort_keys=True), encoding="utf-8")
    foreign = tmp_path / "root" / "foreign" / "parent-99999999" / "dir"
    foreign.mkdir(parents=True)
    (foreign / "skeldir_compiledir_owner.json").write_text(
        json.dumps({"owner": "foreign", "created_at": 1}),
        encoding="utf-8",
    )
    report = reap_expired_compiledirs(ttl_seconds=60, max_deletions=10)
    assert report["deleted"] >= 1
    assert not lease.path.exists()
    assert foreign.exists()


def test_b24_p5_runtime_state_writes_only_bayesian_table() -> None:
    text = RUNTIME_STATE.read_text(encoding="utf-8")
    assert "UPDATE public.bayesian_model_fits" in text
    assert "set_config('app.current_tenant_id'" in text
    assert "WHERE tenant_id = :tenant_id" in text
    forbidden = (
        "UPDATE public.attribution_events",
        "UPDATE public.attribution_allocations",
        "UPDATE public.b23_match_verdicts",
        "UPDATE public.b23_revenue_events",
        "INSERT INTO public.attribution_events",
        "INSERT INTO public.b23_match_verdicts",
    )
    for token in forbidden:
        assert token not in text


def test_b24_p5_probe_does_not_import_pymc_before_env_caps() -> None:
    tree = ast.parse(RUNTIME_PROBE.read_text(encoding="utf-8"))
    top_level_imports = {
        alias.name
        for node in tree.body
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    assert "pymc" not in top_level_imports
    text = RUNTIME_PROBE.read_text(encoding="utf-8")
    assert text.find("apply_native_runtime_environment") < text.find(
        "import pymc as pm"
    )


def test_b24_p5_pymc_sample_uses_central_single_process_policy() -> None:
    tree = ast.parse(RUNTIME_PROBE.read_text(encoding="utf-8"))
    sample_calls = [
        node
        for node in ast.walk(tree)
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Attribute)
        and node.func.attr == "sample"
        and isinstance(node.func.value, ast.Name)
        and node.func.value.id == "pm"
    ]
    assert len(sample_calls) == 1
    assert any(
        keyword.arg is None
        and isinstance(keyword.value, ast.Name)
        and keyword.value.id == "sample_policy"
        for keyword in sample_calls[0].keywords
    )


def test_b24_p5_runtime_probe_module_loads_without_science_stack() -> None:
    module = __import__("app.bayesian.runtime_probe", fromlist=["COMMANDS"])
    assert "tiny-benchmark" in module.COMMANDS
