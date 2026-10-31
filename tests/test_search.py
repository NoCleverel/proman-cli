from pathlib import Path

from proman import search


def test_find_by_lang_python(tmp_path):
    proj = tmp_path / "projA"
    proj.mkdir()
    (proj / "requirements.txt").write_text("flask\n")
    (proj / "main.py").write_text("print('hi')\n")
    (proj / "__pycache__").mkdir()

    hits = search.find_by_lang(tmp_path, "python")
    assert any(h.path == proj for h in hits)


def test_find_by_name(tmp_path):
    proj = tmp_path / "target"
    proj.mkdir()
    assert search.find_by_name(tmp_path, "target") == proj
