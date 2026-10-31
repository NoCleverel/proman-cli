from __future__ import annotations

import shutil
from pathlib import Path

from . import runner
from .config import load_config


def create(name: str, template: str | None, dest: Path | None) -> Path:
    cfg = load_config()
    base = dest or Path(cfg["projects_dir"]).expanduser()
    target = base / name
    if target.exists():
        raise FileExistsError(f"'{target}' already exists")
    target.mkdir(parents=True)

    if template:
        tpl = Path(cfg["templates_dir"]).expanduser() / template
        if not tpl.is_dir():
            shutil.rmtree(target, ignore_errors=True)
            raise FileNotFoundError(f"Template '{template}' not found at {tpl}")
        for item in tpl.iterdir():
            dst = target / item.name
            if item.is_dir():
                shutil.copytree(item, dst)
            else:
                shutil.copy2(item, dst)

    if not (target / ".gitignore").exists():
        (target / ".gitignore").write_text(
            "__pycache__/\n.venv/\nbuild/\ndist/\n", encoding="utf-8"
        )

    runner.ensure_script(target)
    return target
