from __future__ import annotations

import configparser
from pathlib import Path

SYSTEM_CONFIG = Path("/etc/proman/config")
USER_CONFIG = Path.home() / ".config" / "proman" / "config"

DEFAULTS = {
    "default_branch_name": "develop",
    "remote_name": "origin",
    "auto_push": "true",
    "projects_dir": str(Path.home() / "Projects"),
    "templates_dir": str(Path.home() / ".config" / "proman" / "templates"),
    "backup_dir": str(Path.home() / ".local" / "share" / "proman" / "backups"),
}


def _read(path: Path, parser: configparser.ConfigParser) -> None:
    if path.is_file():
        parser.read(path, encoding="utf-8")


def load_config() -> dict[str, str]:
    parser = configparser.ConfigParser()
    parser.read_dict({"proman": DEFAULTS})
    _read(SYSTEM_CONFIG, parser)
    _read(USER_CONFIG, parser)
    _read(Path.cwd() / ".proman", parser)
    if "proman" not in parser:
        parser.add_section("proman")
    return {k: parser["proman"].get(k, DEFAULTS.get(k, ""))
            for k in parser["proman"]}
