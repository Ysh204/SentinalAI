"""Local Git helpers for disposable workspaces. No remotes, commits, or pushes."""

from __future__ import annotations

from pathlib import Path

from git import Repo


def init_local_baseline(workspace: Path) -> None:
    """Initialize a local git repo so later PR work can attach here.

    This MVP never commits incident patches, never pushes, and never deploys.
    """
    if (workspace / ".git").exists():
        return
    repo = Repo.init(workspace)
    repo.index.add(["."])
    repo.index.commit("sentinelai-workspace-baseline")
