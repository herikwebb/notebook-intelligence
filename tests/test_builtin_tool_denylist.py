# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""The ``disabled_tools`` traitlet must be enforced where a chat request's
``toolSelections.builtinToolsets`` is consumed, not only in the capabilities
response that decides which toggles the sidebar renders.
"""

import json
from unittest.mock import Mock, patch

import pytest
from tornado.httputil import HTTPServerRequest
from tornado.web import Application

import notebook_intelligence.util as util
from notebook_intelligence.context_factory import RuleContextFactory
from notebook_intelligence.extension import WebsocketCopilotHandler
from notebook_intelligence.ruleset import RuleContext
from notebook_intelligence.util import (
    filter_builtin_toolset_selection,
    is_builtin_tool_allowed,
)


@pytest.fixture(autouse=True)
def _reset_env_cache(monkeypatch):
    # get_enabled_builtin_tools_in_env memoizes the parsed env var in a
    # module global; reset it so each test sees its own monkeypatched env.
    monkeypatch.setattr(util, "_enabled_tools", None)
    monkeypatch.delenv("NBI_ENABLED_BUILTIN_TOOLS", raising=False)
    yield
    monkeypatch.setattr(util, "_enabled_tools", None)


class TestIsBuiltinToolAllowed:
    def test_empty_denylist_allows_everything(self):
        assert is_builtin_tool_allowed("nbi-command-execute", [], False)
        assert is_builtin_tool_allowed("nbi-command-execute", None, False)

    def test_denylisted_tool_is_refused(self):
        assert not is_builtin_tool_allowed(
            "nbi-command-execute", ["nbi-command-execute"], False
        )

    def test_env_reenable_requires_opt_in_flag(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_BUILTIN_TOOLS", "nbi-command-execute")
        assert not is_builtin_tool_allowed(
            "nbi-command-execute", ["nbi-command-execute"], False
        )
        assert is_builtin_tool_allowed(
            "nbi-command-execute", ["nbi-command-execute"], True
        )


class TestFilterBuiltinToolsetSelection:
    def test_drops_only_denylisted_ids(self):
        requested = ["nbi-notebook-edit", "nbi-command-execute", "nbi-file-edit"]
        assert filter_builtin_toolset_selection(
            requested, ["nbi-command-execute", "nbi-file-edit"], False
        ) == ["nbi-notebook-edit"]

    def test_non_list_and_non_string_entries_are_dropped(self):
        assert filter_builtin_toolset_selection("nbi-command-execute", [], False) == []
        assert filter_builtin_toolset_selection(None, [], False) == []
        assert filter_builtin_toolset_selection(
            [None, 1, "nbi-notebook-edit"], [], False
        ) == ["nbi-notebook-edit"]


class TestWebsocketChatRequestClamp:
    def _application(self):
        app = Mock(spec=Application)
        app.settings = {"jinja2_env": None, "headers": {}}
        app.ui_methods = {}
        app.ui_modules = {}
        app.transforms = []
        return app

    def _request(self):
        request = Mock(spec=HTTPServerRequest)
        request.connection = Mock()
        return request

    def _send_agent_request(self, monkeypatch, builtin_toolsets):
        mock_factory = Mock(spec=RuleContextFactory)
        mock_factory.create.return_value = Mock(spec=RuleContext)
        with patch("notebook_intelligence.extension.ai_service_manager") as mock_ai_manager, \
                patch("notebook_intelligence.extension.NotebookIntelligence") as mock_nb_intel, \
                patch("notebook_intelligence.extension.threading.Thread"), \
                patch("notebook_intelligence.extension.ThreadSafeWebSocketConnector"):
            mock_nb_intel.root_dir = "/workspace"
            mock_ai_manager.handle_chat_request = Mock()
            mock_ai_manager.is_claude_code_mode = False
            mock_ai_manager.is_acp_mode = False
            mock_ai_manager.chat_model = Mock()
            mock_ai_manager.chat_model.context_window = 4096
            handler = WebsocketCopilotHandler(
                self._application(), self._request(), context_factory=mock_factory
            )
            handler.on_message(json.dumps({
                "id": "test-message-id",
                "type": "chat-request",
                "data": {
                    "chatId": "test-chat-id",
                    "prompt": "run something",
                    "language": "python",
                    "filename": "notebook.ipynb",
                    "chatMode": "agent",
                    "toolSelections": {
                        "builtinToolsets": builtin_toolsets,
                        "mcpServers": {},
                        "extensions": {},
                    },
                    "additionalContext": [],
                },
            }))
            mock_ai_manager.handle_chat_request.assert_called_once()
            return mock_ai_manager.handle_chat_request.call_args[0][0]

    def test_denylisted_toolset_is_stripped_from_request(self, monkeypatch):
        monkeypatch.setattr(
            WebsocketCopilotHandler, "disabled_tools", ["nbi-command-execute"]
        )
        monkeypatch.setattr(
            WebsocketCopilotHandler, "allow_enabling_tools_with_env", False
        )
        chat_request = self._send_agent_request(
            monkeypatch, ["nbi-notebook-edit", "nbi-command-execute"]
        )
        assert chat_request.tool_selection.built_in_toolsets == ["nbi-notebook-edit"]

    def test_no_denylist_passes_selection_through(self, monkeypatch):
        monkeypatch.setattr(WebsocketCopilotHandler, "disabled_tools", [])
        chat_request = self._send_agent_request(
            monkeypatch, ["nbi-notebook-edit", "nbi-command-execute"]
        )
        assert chat_request.tool_selection.built_in_toolsets == [
            "nbi-notebook-edit",
            "nbi-command-execute",
        ]

    def test_env_reenable_honoured_only_with_opt_in(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_BUILTIN_TOOLS", "nbi-command-execute")
        monkeypatch.setattr(
            WebsocketCopilotHandler, "disabled_tools", ["nbi-command-execute"]
        )
        monkeypatch.setattr(
            WebsocketCopilotHandler, "allow_enabling_tools_with_env", True
        )
        chat_request = self._send_agent_request(monkeypatch, ["nbi-command-execute"])
        assert chat_request.tool_selection.built_in_toolsets == ["nbi-command-execute"]
