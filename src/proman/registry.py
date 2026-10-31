from __future__ import annotations

import json
from pathlib import Path

REGISTRY_OLD = Path.home() / ".local" / "share" / "proman" / "proj-path.conf"
REGISTRY_JSON = Path.home() / ".local" / "share" / "proman" / "projects.json"


def _ensure() -> None:
    REGISTRY_JSON.parent.mkdir(parents=True, exist_ok=True)


def _migrate() -> None:
    if REGISTRY_JSON.exists() or not REGISTRY_OLD.exists():
        return
    old: dict[str, dict] = {}
    for line in REGISTRY_OLD.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        name, path = line.split("=", 1)
        old[name.strip()] = {"path": path.strip()}
    REGISTRY_JSON.write_text(
        json.dumps(old, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def load() -> dict[str, dict]:
    _ensure()
    _migrate()
    if not REGISTRY_JSON.exists():
        return {}
    return json.loads(REGISTRY_JSON.read_text(encoding="utf-8"))


def save(data: dict[str, dict]) -> None:
    _ensure()
    REGISTRY_JSON.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
    )


def add(name: str, path: str | Path, **extra) -> None:
    data = load()
    entry = data.get(name, {})
    entry["path"] = str(Path(path).expanduser().resolve())
    entry.update(extra)
    data[name] = entry
    save(data)


def remove(name: str) -> None:
    data = load()
    if name in data:
        del data[name]
        save(data)


def get_path(name: str) -> str | None:
    entry = load().get(name)
    return entry.get("path") if entry else None


def get_entry(name: str) -> dict | None:
    return load().get(name)