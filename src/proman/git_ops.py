from __future__ import annotations

import subprocess
from pathlib import Path


def _run(cmd: list[str], cwd: Path | None = None) -> int:
    print(f"$ {' '.join(cmd)}")
    return subprocess.call(cmd, cwd=str(cwd) if cwd else None)


def clone(url: str, dest: Path) -> int:
    dest.parent.mkdir(parents=True, exist_ok=True)
    return _run(["git", "clone", url, str(dest)])


def is_repo(path: Path) -> bool:
    return (path / ".git").is_dir()


def checkout_branch(repo: Path, branch: str) -> int:
    local = subprocess.run(
        ["git", "rev-parse", "--verify", "--quiet", branch],
        cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    if local:
        return _run(["git", "checkout", branch], cwd=repo)
    remote = subprocess.run(
        ["git", "ls-remote", "--exit-code", "--heads", "origin", branch],
        cwd=repo, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    ).returncode == 0
    if remote:
        return _run(["git", "checkout", "-b", branch, f"origin/{branch}"], cwd=repo)
    return _run(["git", "checkout", "-b", branch], cwd=repo)


def current_branch(repo: Path) -> str:
    try:
        out = subprocess.check_output(
            ["git", "rev-parse", "--abbrev-ref", "HEAD"],
            cwd=repo, text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return ""
    return out.strip()


def has_uncommitted(repo: Path) -> bool:
    try:
        out = subprocess.check_output(
            ["git", "status", "--porcelain"],
            cwd=repo, text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return False
    return bool(out.strip())


def ahead_behind(repo: Path, remote: str, branch: str) -> tuple[int, int]:
    try:
        out = subprocess.check_output(
            ["git", "rev-list", "--left-right", "--count",
             f"{remote}/{branch}...HEAD"],
            cwd=repo, text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return (0, 0)
    parts = out.split()
    if len(parts) != 2:
        return (0, 0)
    behind, ahead = parts
    return int(behind), int(ahead)


def last_commit_ts(repo: Path) -> float:
    try:
        out = subprocess.check_output(
            ["git", "log", "-1", "--format=%ct"],
            cwd=repo, text=True, stderr=subprocess.DEVNULL,
        )
    except subprocess.CalledProcessError:
        return 0.0
    return float(out.strip() or 0)


def save(repo: Path, message: str, remote: str, branch: str,
         auto_push: bool) -> int:
    rc = _run(["git", "add", "-A"], cwd=repo)
    if rc != 0:
        return rc
    rc = _run(["git", "commit", "-m", message], cwd=repo)
    if rc != 0:
        return rc
    if auto_push:
        return _run(["git", "push", remote, branch], cwd=repo)
    return 0


def sync(repo: Path, remote: str, branch: str) -> int:
    rc = _run(["git", "pull", "--rebase", remote, branch], cwd=repo)
    if rc != 0:
        return rc
    return _run(["git", "push", remote, branch], cwd=repo)
