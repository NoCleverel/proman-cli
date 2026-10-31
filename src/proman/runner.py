from __future__ import annotations

import subprocess
from pathlib import Path

SCRIPT_NAME = "run.pm.sh"
SCRIPT_BODY = """#!/usr/bin/env bash
# run.pm.sh — managed by proman.
set -e

echo "My Program is running!"
# TODO: python main.py / npm start / cargo run / ...
"""


def script_path(project: Path) -> Path:
    return project / SCRIPT_NAME


def has_script(project: Path) -> bool:
    return script_path(project).is_file()


def ensure_script(project: Path) -> Path:
    sp = script_path(project)
    if not sp.exists():
        sp.write_text(SCRIPT_BODY, encoding="utf-8")
        sp.chmod(0o755)
    return sp


def run(project: Path) -> int:
    sp = script_path(project)
    if not sp.is_file():
        return 127
    print(f"$ bash {sp}")
    return subprocess.call(["bash", str(sp)], cwd=str(project))
