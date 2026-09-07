# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Scope tests for the ACP client's ``fs/read_text_file`` / ``fs/write_text_file``.

NBI advertises the ``fs`` client capability to the ACP agent, so the agent may
send those requests directly -- they are client methods and never pass through
``request_permission``. The handlers used to hand ``path`` straight to
``open()``, so an agent-supplied absolute path or ``..`` traversal read or
overwrote any file the Jupyter user owns. These tests pin the
``safe_jupyter_path`` gate that now confines both to the workspace root.
"""

import asyncio
from types import SimpleNamespace

import acp
import pytest

from notebook_intelligence.acp_agent import _NbiAcpClient
from notebook_intelligence.util import set_jupyter_root_dir


@pytest.fixture
def jupyter_root(tmp_path):
    # A real subdir for the workspace so the parent tmp_path stays available
    # as an "outside the workspace" target.
    root = tmp_path / "workspace"
    root.mkdir()
    set_jupyter_root_dir(str(root))
    return root


@pytest.fixture
def client():
    owner = SimpleNamespace(
        current_response=None,
        agent_spec=SimpleNamespace(label="Codex"),
    )
    return _NbiAcpClient(owner)


class TestReadTextFileContainment:
    def test_reads_workspace_file(self, client, jupyter_root):
        (jupyter_root / "notes.md").write_text("inside", encoding="utf-8")
        result = asyncio.run(client.read_text_file("notes.md", "sess-1"))
        assert result.content == "inside"

    def test_rejects_absolute_path_outside_root(self, client, jupyter_root):
        outside = jupyter_root.parent / "secret.txt"
        outside.write_text("token", encoding="utf-8")
        with pytest.raises(acp.RequestError):
            asyncio.run(client.read_text_file(str(outside), "sess-1"))

    def test_rejects_parent_traversal(self, client, jupyter_root):
        (jupyter_root.parent / "secret.txt").write_text("token", encoding="utf-8")
        with pytest.raises(acp.RequestError):
            asyncio.run(client.read_text_file("../secret.txt", "sess-1"))

    def test_rejects_symlink_escaping_root(self, client, jupyter_root):
        outside = jupyter_root.parent / "secret.txt"
        outside.write_text("token", encoding="utf-8")
        (jupyter_root / "link.txt").symlink_to(outside)
        with pytest.raises(acp.RequestError):
            asyncio.run(client.read_text_file("link.txt", "sess-1"))


class TestWriteTextFileContainment:
    def test_writes_workspace_file(self, client, jupyter_root):
        asyncio.run(client.write_text_file("hello", "sub/out.txt", "sess-1"))
        assert (jupyter_root / "sub" / "out.txt").read_text(encoding="utf-8") == "hello"

    def test_rejects_absolute_path_outside_root(self, client, jupyter_root):
        outside = jupyter_root.parent / "pwned.txt"
        with pytest.raises(acp.RequestError):
            asyncio.run(client.write_text_file("x", str(outside), "sess-1"))
        assert not outside.exists()

    def test_rejects_parent_traversal(self, client, jupyter_root):
        with pytest.raises(acp.RequestError):
            asyncio.run(client.write_text_file("x", "../pwned.txt", "sess-1"))
        assert not (jupyter_root.parent / "pwned.txt").exists()

    def test_traversal_does_not_create_parent_directories(self, client, jupyter_root):
        # The rejection happens before ``makedirs``, so a blocked write leaves
        # no directory tree behind outside the workspace.
        with pytest.raises(acp.RequestError):
            asyncio.run(
                client.write_text_file("x", "../escaped/nested/out.txt", "sess-1")
            )
        assert not (jupyter_root.parent / "escaped").exists()
