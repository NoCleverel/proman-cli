from proman import runner


def test_ensure_script_creates_file(tmp_path):
    sp = runner.ensure_script(tmp_path)
    assert sp.is_file()
    assert runner.has_script(tmp_path)
