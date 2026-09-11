# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""A per-request ("Approve for this request") approval of a file-writing
Claude Code tool must stay confined to the Jupyter root. Before this guard the
approval set was keyed by tool name alone, so one approved in-workspace Write
let every later Write in the same turn land anywhere the user can write with
no further prompt.
"""

import asyncio
from unittest.mock import AsyncMock, MagicMock

import pytest
from claude_agent_sdk import PermissionResultAllow

import notebook_intelligence.claude as claude_module
from notebook_intelligence.claude import _session_approval_covers
from notebook_intelligence.util import set_jupyter_root_dir


@pytest.fixture
def workspace(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    (tmp_path / "outside").mkdir()
    set_jupyter_root_dir(str(root))
    monkeypatch.setattr(claude_module, "_approved_tools_for_response", set())
    monkeypatch.setattr(claude_module, "_approved_tools_response_id", None)
    yield root
    set_jupyter_root_dir(None)


class TestSessionApprovalCovers:
    def test_in_root_targets_are_covered(self, workspace):
        assert _session_approval_covers("Write", {"file_path": str(workspace / "a.py")})
        assert _session_approval_covers("Edit", {"file_path": "sub/b.py"})
        assert _session_approval_covers(
            "NotebookEdit", {"notebook_path": str(workspace / "n.ipynb")}
        )

    def test_out_of_root_targets_are_not_covered(self, workspace, tmp_path):
        outside = tmp_path / "outside" / "authorized_keys"
        assert not _session_approval_covers("Write", {"file_path": str(outside)})
        assert not _session_approval_covers("Edit", {"file_path": "../outside/x"})
        assert not _session_approval_covers(
            "NotebookEdit", {"notebook_path": str(outside)}
        )
        assert not _session_approval_covers("MultiEdit", {"file_path": "~/.bashrc"})

    def test_missing_or_malformed_target_is_not_covered(self, workspace):
        assert not _session_approval_covers("Write", {})
        assert not _session_approval_covers("Write", {"file_path": ""})
        assert not _session_approval_covers("Write", {"file_path": 42})
        assert not _session_approval_covers("Write", None)

    def test_non_file_tools_keep_tool_level_scope(self, workspace):
        assert _session_approval_covers("WebSearch", {"query": "x"})
        assert _session_approval_covers("mcp__nbi__add-code-cell", {"source": "x"})

    def test_unset_root_is_fail_closed(self, workspace):
        set_jupyter_root_dir(None)
        assert not _session_approval_covers("Write", {"file_path": "/tmp/x"})


def _run_handler(monkeypatch, response, tool_name, input_data, answer):
    monkeypatch.setattr(claude_module, "get_current_response", lambda: response)
    monkeypatch.setattr(claude_module, "get_current_permission_mode", lambda: "default")
    monkeypatch.setattr(
        claude_module.ChatResponse,
        "wait_for_chat_user_input",
        AsyncMock(return_value=answer),
    )
    return asyncio.run(
        claude_module._custom_permission_handler(tool_name, input_data, {})
    )


class TestPermissionHandlerScope:
    def test_session_approval_does_not_extend_outside_root(
        self, workspace, tmp_path, monkeypatch
    ):
        response = MagicMock(message_id="response-1")
        response.stream_user_input_request.return_value = object()

        first = _run_handler(
            monkeypatch,
            response,
            "Write",
            {"file_path": str(workspace / "report.md"), "content": "ok"},
            {"confirmed_for_session": True},
        )
        assert isinstance(first, PermissionResultAllow)
        assert response.stream_user_input_request.call_count == 1

        # Same tool, same turn, still inside the workspace: no re-prompt.
        second = _run_handler(
            monkeypatch,
            response,
            "Write",
            {"file_path": str(workspace / "notes.md"), "content": "ok"},
            {"confirmed": False},
        )
        assert isinstance(second, PermissionResultAllow)
        assert response.stream_user_input_request.call_count == 1

        # Same tool, same turn, outside the workspace: prompts again and the
        # user's refusal is honoured.
        third = _run_handler(
            monkeypatch,
            response,
            "Write",
            {
                "file_path": str(tmp_path / "outside" / "authorized_keys"),
                "content": "ssh-ed25519 AAAA...",
            },
            {"confirmed": False},
        )
        assert not isinstance(third, PermissionResultAllow)
        assert response.stream_user_input_request.call_count == 2

    def test_new_turn_clears_session_approvals(self, workspace, monkeypatch):
        response = MagicMock(message_id="response-1")
        response.stream_user_input_request.return_value = object()
        _run_handler(
            monkeypatch,
            response,
            "Write",
            {"file_path": str(workspace / "a.md"), "content": "ok"},
            {"confirmed_for_session": True},
        )
        next_response = MagicMock(message_id="response-2")
        next_response.stream_user_input_request.return_value = object()
        result = _run_handler(
            monkeypatch,
            next_response,
            "Write",
            {"file_path": str(workspace / "a.md"), "content": "ok"},
            {"confirmed": False},
        )
        assert not isinstance(result, PermissionResultAllow)
        assert next_response.stream_user_input_request.call_count == 1
