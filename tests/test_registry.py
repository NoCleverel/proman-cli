from pathlib import Path

from proman import registry


def test_add_load_remove(tmp_path, monkeypatch):
    reg = tmp_path / "projects.json"
    monkeypatch.setattr(registry, "REGISTRY_JSON", reg)
    monkeypatch.setattr(registry, "REGISTRY_OLD", tmp_path / "nope.conf")

    registry.add("demo", tmp_path / "demo")
    data = registry.load()
    assert data["demo"]["path"] == str((tmp_path / "demo").resolve())

    registry.remove("demo")
    assert registry.load() == {}
