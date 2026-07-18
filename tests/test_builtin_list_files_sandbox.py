"""Sandbox tests for the built-in list_files tool.

``list_files`` must confine its glob enumeration to ``jupyter_root_dir``
exactly like ``search_files``: a ``..``-bearing or absolute pattern is
refused before ``glob()`` runs, and every match is funnelled through the
``safe_jupyter_path`` gate so an outbound workspace symlink cannot leak
host file names or paths.
"""

import asyncio
import os
import tempfile

import pytest

import notebook_intelligence.built_in_toolsets as toolsets
from notebook_intelligence.util import get_jupyter_root_dir, set_jupyter_root_dir


def _symlinks_supported() -> bool:
    """Whether this platform/process can create symlinks."""
    with tempfile.TemporaryDirectory() as td:
        target = os.path.join(td, "target")
        link = os.path.join(td, "link")
        open(target, "w").close()
        try:
            os.symlink(target, link)
            return True
        except (OSError, NotImplementedError):
            return False


requires_symlinks = pytest.mark.skipif(
    not _symlinks_supported(),
    reason="symlink creation is not supported on this platform",
)


@pytest.fixture
def jupyter_root(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(toolsets, "get_jupyter_root_dir", lambda: str(root))
    previous_root = get_jupyter_root_dir()
    set_jupyter_root_dir(str(root))
    try:
        yield root
    finally:
        set_jupyter_root_dir(previous_root)


def _list_files(pattern: str, **kwargs) -> str:
    tool = toolsets.list_files._tool_function
    return asyncio.run(tool(pattern=pattern, **kwargs))


class TestListFilesSandbox:
    def test_lists_legitimate_workspace_file(self, jupyter_root):
        (jupyter_root / "notes.txt").write_text("hello\n", encoding="utf-8")

        result = _list_files(pattern="*.txt", directory=".")

        assert "notes.txt" in result

    def test_supports_recursive_glob(self, jupyter_root):
        sub = jupyter_root / "sub"
        sub.mkdir()
        (sub / "mod.py").write_text("x\n", encoding="utf-8")

        result = _list_files(pattern="**/*.py", directory=".")

        assert "mod.py" in result

    def test_rejects_parent_traversal_pattern(self, jupyter_root, tmp_path):
        # An outbound ".." pattern must be refused before glob() runs, so
        # the tool never stats or enumerates outside the workspace.
        outside = tmp_path / "secret.txt"
        outside.write_text("data\n", encoding="utf-8")

        result = _list_files(pattern="../secret.txt", directory=".")

        assert "secret.txt" not in result.replace("../secret.txt", "")
        assert "not allowed" in result

    def test_rejects_absolute_pattern(self, jupyter_root):
        result = _list_files(pattern="/etc/*", directory=".")

        assert "not allowed" in result

    def test_traversal_rejection_does_not_leak_existence(
        self, jupyter_root, tmp_path
    ):
        # The rejection is pattern-based and must be identical whether or
        # not the outside target exists, so it cannot be used as an
        # existence oracle for arbitrary host paths.
        present = tmp_path / "present.txt"
        present.write_text("data\n", encoding="utf-8")

        hit_present = _list_files(pattern="../present.txt", directory=".")
        hit_absent = _list_files(pattern="../nope.txt", directory=".")

        assert "not allowed" in hit_present
        assert hit_present.replace("present", "X") == hit_absent.replace(
            "nope", "X"
        )

    @requires_symlinks
    def test_skips_outbound_symlink_directory(self, jupyter_root, tmp_path):
        # A pattern that descends a symlinked directory (link -> /outside)
        # must not enumerate the outside tree; each match is gated by
        # safe_jupyter_path, which resolves the symlink and refuses the
        # outbound target.
        outside_dir = tmp_path / "outside"
        outside_dir.mkdir()
        (outside_dir / "secret.txt").write_text("data\n", encoding="utf-8")
        (jupyter_root / "link").symlink_to(outside_dir, target_is_directory=True)
        (jupyter_root / "real.txt").write_text("in workspace\n", encoding="utf-8")

        via_link = _list_files(pattern="link/*", directory=".")
        assert "secret.txt" not in via_link

        # A legitimate recursive listing still returns in-workspace files and
        # never the symlinked-directory target.
        recursive = _list_files(pattern="**/*.txt", directory=".")
        assert "real.txt" in recursive
        assert "secret.txt" not in recursive
