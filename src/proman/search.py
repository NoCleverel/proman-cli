from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

SCRIPT_NAME = "run.pm.sh"

LANG_MARKERS = {
    "python": ["requirements.txt", "pyproject.toml", "setup.py",
               "Pipfile", "__pycache__"],
    "node": ["package.json", "node_modules", "yarn.lock"],
    "rust": ["Cargo.toml", "Cargo.lock"],
    "go": ["go.mod", "go.sum"],
    "java": ["pom.xml", "build.gradle"],
}
EXT_MARKERS = {
    "python": {".py"},
    "node": {".js", ".ts", ".jsx", ".tsx"},
    "rust": {".rs"},
    "go": {".go"},
    "java": {".java"},
}

IGNORE_DIRS = {".git", "node_modules", "venv", ".venv", "__pycache__",
               "target", "dist", "build", ".idea", ".vscode", ".pytest_cache"}
IGNORE_FILES = {"__init__.py", "setup.py", "requirements.txt", "conftest.py"}


@dataclass
class Hit:
    path: Path
    score: int
    recent_files: list[str]
    last_modified: float


def _iter_dirs(root: Path):
    for dirpath, dirnames, _ in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in IGNORE_DIRS]
        yield Path(dirpath)


def _recent_user_files(project: Path, lang: str, limit: int = 3) -> list[str]:
    exts = EXT_MARKERS.get(lang, set())
    files: list[tuple[float, str]] = []
    try:
        for p in project.rglob("*"):
            if not p.is_file():
                continue
            if any(part in IGNORE_DIRS for part in p.parts):
                continue
            if p.name in IGNORE_FILES:
                continue
            if exts and p.suffix not in exts:
                continue
            try:
                files.append((p.stat().st_mtime, str(p.relative_to(project))))
            except OSError:
                pass
    except OSError:
        return []
    files.sort(reverse=True)
    return [name for _, name in files[:limit]]


def _last_modified(project: Path) -> float:
    latest = 0.0
    try:
        for p in project.rglob("*"):
            if any(part in IGNORE_DIRS for part in p.parts):
                continue
            try:
                latest = max(latest, p.stat().st_mtime)
            except OSError:
                pass
    except OSError:
        pass
    return latest


def find_by_name(root: Path, name: str) -> Path | None:
    for d in _iter_dirs(root):
        if d.name == name:
            return d
    return None


def find_by_lang(root: Path, lang: str) -> list[Hit]:
    markers = LANG_MARKERS.get(lang, [])
    hits: list[Hit] = []
    for d in _iter_dirs(root):
        score = sum(1 for m in markers if (d / m).exists())
        if score == 0:
            continue
        recent = _recent_user_files(d, lang)
        if not recent:
            continue
        hits.append(Hit(d, score, recent, _last_modified(d)))
    hits.sort(key=lambda h: (-h.score, -h.last_modified))
    return hits[:20]


def fmt_time(ts: float) -> str:
    if ts <= 0:
        return "unknown"
    return datetime.fromtimestamp(ts).strftime("%d-%m-%Y, %H:%M %p")
