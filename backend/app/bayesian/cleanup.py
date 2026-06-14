"""Parent-side cleanup orchestration for Bayesian fit attempts."""

from __future__ import annotations

from dataclasses import dataclass

from app.bayesian.compiledir_reaper import (
    CompiledirLease,
    cleanup_compiledir,
    reap_expired_compiledirs,
)
from app.bayesian.temp_workspace import (
    WorkspaceLease,
    cleanup_workspace,
    reap_expired_workspaces,
)


@dataclass(frozen=True)
class CleanupReport:
    """Payload-free cleanup report for a parent-owned fit attempt."""

    workspace_removed: bool
    compiledir_removed: bool


def cleanup_fit_attempt(
    *,
    workspace: WorkspaceLease | None,
    compiledir: CompiledirLease | None,
) -> CleanupReport:
    """Clean parent-owned workspace and compiledir after every terminal path."""

    compiledir_removed = False
    workspace_removed = False
    if compiledir is not None and compiledir.path.exists():
        compiledir_removed = cleanup_compiledir(compiledir)
    if workspace is not None and workspace.path.exists():
        workspace_removed = cleanup_workspace(workspace)
    return CleanupReport(
        workspace_removed=workspace_removed,
        compiledir_removed=compiledir_removed,
    )


def run_preflight_janitor(
    *,
    ttl_seconds: int = 3600,
    max_deletions: int = 25,
    max_scan_entries: int = 200,
) -> dict[str, object]:
    """Run bounded parent-side cleanup before creating new fit-attempt state."""

    return {
        "workspaces": reap_expired_workspaces(
            ttl_seconds=ttl_seconds,
            max_deletions=max_deletions,
            max_scan_entries=max_scan_entries,
        ),
        "compiledirs": reap_expired_compiledirs(
            ttl_seconds=ttl_seconds,
            max_deletions=max_deletions,
            max_scan_entries=max_scan_entries,
        ),
    }
