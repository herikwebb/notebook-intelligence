"""Sandbox tests for the built-in search_files tool.

``read_file`` routes every path through ``safe_jupyter_path`` before
opening; ``search_files`` must apply the same gate to each glob match so
outbound workspace symlinks cannot leak host file contents.
"""

import asyncio

import pytest

import notebook_intelligence.built_in_toolsets as toolsets
from notebook_intelligence.util import set_jupyter_root_dir


@pytest.fixture
def jupyter_root(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(toolsets, "get_jupyter_root_dir", lambda: str(root))
    set_jupyter_root_dir(str(root))
    return root


def _search_files(pattern: str, **kwargs) -> str:
    tool = toolsets.search_files._tool_function
    return asyncio.run(tool(pattern=pattern, **kwargs))


class TestSearchFilesSymlinkSandbox:
    def test_skips_outbound_symlink_when_searching_content(
        self, jupyter_root, tmp_path
    ):
        outside = tmp_path / "secret.txt"
        outside.write_text("TOP_SECRET_DATA\n", encoding="utf-8")
        link = jupyter_root / "leak.txt"
        link.symlink_to(outside)

        result = _search_files(
            pattern="leak.txt",
            directory=".",
            content_pattern="TOP_SECRET",
        )

        assert "TOP_SECRET_DATA" not in result
        assert "No matches found" in result

    def test_reads_legitimate_workspace_file(self, jupyter_root):
        target = jupyter_root / "notes.txt"
        target.write_text("hello workspace\n", encoding="utf-8")

        result = _search_files(
            pattern="notes.txt",
            directory=".",
            content_pattern="workspace",
        )

        assert "hello workspace" in result

    def test_rejects_parent_traversal_pattern(self, jupyter_root, tmp_path):
        # An outbound ".." pattern must be refused before glob() runs, so
        # the tool never stats or reads outside the workspace.
        outside = tmp_path / "secret.txt"
        outside.write_text("TOP_SECRET_DATA\n", encoding="utf-8")

        result = _search_files(
            pattern="../secret.txt",
            directory=".",
            content_pattern="TOP_SECRET",
        )

        assert "TOP_SECRET_DATA" not in result
        assert "not allowed" in result

    def test_traversal_rejection_does_not_leak_existence(
        self, jupyter_root, tmp_path
    ):
        # The rejection is pattern-based and must be identical whether or
        # not the outside target exists, so it cannot be used as an
        # existence oracle for arbitrary host paths.
        present = tmp_path / "present.txt"
        present.write_text("data\n", encoding="utf-8")

        hit_present = _search_files(pattern="../present.txt", directory=".")
        hit_absent = _search_files(pattern="../nope.txt", directory=".")

        assert "not allowed" in hit_present
        assert hit_present.replace("present", "X") == hit_absent.replace(
            "nope", "X"
        )

    def test_outbound_symlink_target_existence_not_revealed(
        self, jupyter_root, tmp_path
    ):
        # is_file() must not be called on a candidate before the sandbox
        # gate resolves it, or an outbound symlink whose target exists
        # would be admitted-then-skipped while a broken one is filtered
        # out earlier, leaking outside-path existence via the reply.
        existing_target = tmp_path / "exists.txt"
        existing_target.write_text("TOP_SECRET_DATA\n", encoding="utf-8")
        (jupyter_root / "link_present").symlink_to(existing_target)
        (jupyter_root / "link_absent").symlink_to(tmp_path / "missing.txt")

        present = _search_files(pattern="link_present", directory=".")
        absent = _search_files(pattern="link_absent", directory=".")

        assert "TOP_SECRET_DATA" not in present
        # Responses differ only by the echoed pattern name, never by
        # whether the outbound target exists.
        assert present.replace("link_present", "L") == absent.replace(
            "link_absent", "L"
        )
