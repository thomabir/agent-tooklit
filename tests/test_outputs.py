import pytest

from hwkit.outputs import OutputGuard


def test_guard_stops_on_changed_file(tmp_path):
    writers = {"a.txt": lambda p: p.write_text("generated")}
    OutputGuard(tmp_path).write_all(writers)
    (tmp_path / "a.txt").write_text("saved by user")
    with pytest.raises(RuntimeError, match="changed"):
        OutputGuard(tmp_path).write_all(writers)
    assert (tmp_path / "a.txt").read_text() == "saved by user"


def test_guard_rewrites_unchanged_file(tmp_path):
    OutputGuard(tmp_path).write_all({"a.txt": lambda p: p.write_text("1")})
    OutputGuard(tmp_path).write_all({"a.txt": lambda p: p.write_text("2")})
    assert (tmp_path / "a.txt").read_text() == "2"
