"""Regression tests: the file tools must not follow a symlink that replaces
the target between the containment check and the open."""

import asyncio
import os

import pytest

import notebook_intelligence.built_in_toolsets as toolsets
from notebook_intelligence import util as util_mod


@pytest.fixture
def jupyter_root(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(util_mod, "_jupyter_root_dir", str(root))
    return root


@pytest.fixture
def outside_file(tmp_path):
    victim = tmp_path / "victim.txt"
    victim.write_text("secret\n", encoding="utf-8")
    return victim


def _swap_after_check(monkeypatch, target, link_to):
    """Make safe_jupyter_path succeed on the real file and then replace that
    file with a symlink before the tool opens it, which is what a racing
    local writer does between the two path resolutions."""
    real = toolsets.safe_jupyter_path

    def swapped(path):
        resolved = real(path)
        target.unlink()
        target.symlink_to(link_to)
        return resolved

    monkeypatch.setattr(toolsets, "_get_safe_path", swapped)


def _run(tool, **kwargs):
    return asyncio.run(tool._tool_function(**kwargs))


class TestWriteToFile:
    def test_swapped_symlink_is_not_followed(self, jupyter_root, outside_file, monkeypatch):
        target = jupyter_root / "notes.txt"
        target.write_text("original\n", encoding="utf-8")
        _swap_after_check(monkeypatch, target, outside_file)

        result = _run(toolsets.write_to_file, file_path="notes.txt", content="payload\n")

        assert result.startswith("Error writing to file:")
        assert outside_file.read_text(encoding="utf-8") == "secret\n"

    def test_swapped_parent_directory_is_not_followed(
        self, jupyter_root, tmp_path, outside_file, monkeypatch
    ):
        # A directory component, not the file itself, is what gets replaced;
        # O_NOFOLLOW alone would not catch this, the opened-path check must.
        probe = os.open(str(tmp_path), os.O_RDONLY)
        try:
            if util_mod._opened_fd_path(probe) is None:
                pytest.skip("platform does not expose the path behind an open fd")
        finally:
            os.close(probe)
        sub = jupyter_root / "sub"
        sub.mkdir()
        (sub / "notes.txt").write_text("original\n", encoding="utf-8")
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "notes.txt").write_text("secret\n", encoding="utf-8")
        real = toolsets.safe_jupyter_path

        def swapped(path):
            resolved = real(path)
            (sub / "notes.txt").unlink()
            sub.rmdir()
            sub.symlink_to(outside_dir, target_is_directory=True)
            return resolved

        monkeypatch.setattr(toolsets, "_get_safe_path", swapped)

        result = _run(toolsets.write_to_file, file_path="sub/notes.txt", content="payload\n")

        assert result.startswith("Error writing to file:")
        assert (outside_dir / "notes.txt").read_text(encoding="utf-8") == "secret\n"

    def test_regular_file_still_written(self, jupyter_root):
        result = _run(toolsets.write_to_file, file_path="new/notes.txt", content="hello\n")

        assert result == "Wrote content to 'new/notes.txt'"
        assert (jupyter_root / "new" / "notes.txt").read_text(encoding="utf-8") == "hello\n"

    def test_overwrite_truncates_regular_file(self, jupyter_root):
        target = jupyter_root / "notes.txt"
        target.write_text("a much longer original body\n", encoding="utf-8")

        _run(toolsets.write_to_file, file_path="notes.txt", content="short\n")

        assert target.read_text(encoding="utf-8") == "short\n"


class TestInsertContent:
    def test_swapped_symlink_is_not_followed(self, jupyter_root, outside_file, monkeypatch):
        target = jupyter_root / "notes.txt"
        target.write_text("line1\nline2\n", encoding="utf-8")
        _swap_after_check(monkeypatch, target, outside_file)

        result = _run(
            toolsets.insert_content, file_path="notes.txt", line_number=1, content="payload"
        )

        assert result.startswith("Error inserting content:")
        assert outside_file.read_text(encoding="utf-8") == "secret\n"

    def test_regular_file_still_edited(self, jupyter_root):
        target = jupyter_root / "notes.txt"
        target.write_text("line1\nline2\n", encoding="utf-8")

        result = _run(
            toolsets.insert_content, file_path="notes.txt", line_number=2, content="inserted"
        )

        assert result == "Inserted content at line 2 in 'notes.txt'"
        assert target.read_text(encoding="utf-8") == "line1\ninserted\nline2\n"


class TestReadFile:
    def test_swapped_symlink_is_not_followed(self, jupyter_root, outside_file, monkeypatch):
        target = jupyter_root / "notes.txt"
        target.write_text("line1\n", encoding="utf-8")
        _swap_after_check(monkeypatch, target, outside_file)

        result = _run(toolsets.read_file, file_path="notes.txt")

        assert result.startswith("Error reading file:")
        assert "secret" not in result


class TestOpenConfined:
    def test_refuses_symlink_final_component(self, tmp_path, outside_file):
        link = tmp_path / "link.txt"
        link.symlink_to(outside_file)

        with pytest.raises(ValueError):
            util_mod.open_confined(link.resolve().parent / "link.txt", write=True)
        assert outside_file.read_text(encoding="utf-8") == "secret\n"

    def test_refuses_directory(self, tmp_path):
        with pytest.raises(ValueError):
            util_mod.open_confined(tmp_path.resolve())

    def test_write_creates_regular_file(self, tmp_path):
        target = (tmp_path / "fresh.txt").resolve()

        with util_mod.open_confined(target, write=True) as f:
            f.write("ok\n")

        assert target.read_text(encoding="utf-8") == "ok\n"
