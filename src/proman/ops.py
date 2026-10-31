from __future__ import annotations

import json
import shutil
import tarfile
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from . import git_ops, runner, search
from .config import load_config


@dataclass
class Health:
    name: str
    path: Path
    exists: bool
    is_git: bool
    has_script: bool
    branch: str
    dirty: bool
    ahead: int
    behind: int
    last_commit: float

    @property
    def problems(self) -> list[str]:
        p: list[str] = []
        if not self.exists:
            p.append("path missing")
        if self.exists and not self.is_git:
            p.append("not a git repo")
        if self.exists and not self.has_script:
            p.append("run.pm.sh missing")
        if self.exists and self.is_git and self.dirty:
            p.append("uncommitted changes")
        if self.exists and self.is_git and self.ahead:
            p.append(f"{self.ahead} commit(s) not pushed")
        if self.exists and self.is_git and self.behind:
            p.append(f"{self.behind} commit(s) behind remote")
        return p

    @property
    def ok(self) -> bool:
        return not self.problems


def check_project(name: str, path: Path) -> Health:
    cfg = load_config()
    exists = path.is_dir()
    is_git = exists and git_ops.is_repo(path)
    has_script = exists and runner.has_script(path)
    branch = git_ops.current_branch(path) if is_git else ""
    dirty = git_ops.has_uncommitted(path) if is_git else False
    ahead = behind = 0
    last = 0.0
    if is_git and branch:
        ahead, behind = git_ops.ahead_behind(path, cfg["remote_name"], branch)
        last = git_ops.last_commit_ts(path)
    return Health(name, path, exists, is_git, has_script, branch,
                  dirty, ahead, behind, last)


def doctor_all(registry_data: dict[str, dict]) -> list[Health]:
    return [check_project(n, Path(e["path"]))
            for n, e in registry_data.items() if "path" in e]


def backup_all(registry_data: dict[str, dict]) -> list[Path]:
    cfg = load_config()
    out_dir = Path(cfg["backup_dir"]).expanduser()
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    results: list[Path] = []
    for name, entry in registry_data.items():
        src = Path(entry["path"]) if "path" in entry else None
        if not src or not src.is_dir():
            continue
        archive = out_dir / f"{name}-{stamp}.tar.gz"
        with tarfile.open(archive, "w:gz") as tar:
            tar.add(src, arcname=name)
        results.append(archive)
    return results


def export_registry(registry_data: dict[str, dict], dest: Path) -> None:
    dest.write_text(
        json.dumps(registry_data, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


def import_registry(src: Path) -> dict[str, dict]:
    return json.loads(src.read_text(encoding="utf-8"))


def move_project(name: str, new_path: Path) -> Path:
    from . import registry
    entry = registry.get_entry(name)
    if entry is None:
        raise FileNotFoundError(f"'{name}' not registered")
    old = Path(entry["path"])
    if not old.is_dir():
        raise FileNotFoundError(f"Source '{old}' missing")
    new_path = new_path.expanduser().resolve()
    if new_path.exists():
        raise FileExistsError(f"'{new_path}' already exists")
    new_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(old), str(new_path))
    registry.add(name, new_path,
                 **{k: v for k, v in entry.items() if k != "path"})
    return new_path


def tree_stat(path: Path) -> tuple[int, int]:
    files = total = 0
    try:
        for p in path.rglob("*"):
            if any(part in search.IGNORE_DIRS for part in p.parts):
                continue
            if p.is_file():
                files += 1
                try:
                    total += p.stat().st_size
                except OSError:
                    pass
    except OSError:
        pass
    return files, total


def human_size(n: int) -> str:
    for unit in ("B", "KB", "MB", "GB", "TB"):
        if n < 1024:
            return f"{n:.1f} {unit}"
        n /= 1024
    return f"{n:.1f} PB"
