# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Websocket boundary must enforce the admin disabled_tools denylist."""

import json
from unittest.mock import Mock, patch

from tornado.httputil import HTTPServerRequest
from tornado.web import Application

from notebook_intelligence.extension import WebsocketCopilotHandler
from notebook_intelligence.context_factory import RuleContextFactory
from notebook_intelligence.ruleset import RuleContext


def _create_mock_application():
    app = Mock(spec=Application)
    app.settings = {"jinja2_env": None, "headers": {}}
    app.ui_methods = {}
    app.ui_modules = {}
    app.transforms = []
    return app


def _create_mock_request():
    request = Mock(spec=HTTPServerRequest)
    request.connection = Mock()
    return request


class TestDisabledToolsWebsocketGate:
    @patch("notebook_intelligence.extension.threading.Thread")
    @patch("notebook_intelligence.extension.NotebookIntelligence")
    @patch("notebook_intelligence.extension.ai_service_manager")
    def test_on_message_strips_disabled_builtin_toolsets(
        self, mock_ai_manager, mock_nb_intel, mock_thread
    ):
        mock_nb_intel.root_dir = "/workspace"
        mock_ai_manager.handle_chat_request = Mock()
        mock_ai_manager.is_claude_code_mode = False
        mock_ai_manager.chat_model = Mock()
        mock_ai_manager.chat_model.context_window = 4096

        mock_factory = Mock(spec=RuleContextFactory)
        mock_factory.create.return_value = Mock(spec=RuleContext)

        with patch("notebook_intelligence.extension.ThreadSafeWebSocketConnector"):
            handler = WebsocketCopilotHandler(
                _create_mock_application(),
                _create_mock_request(),
                context_factory=mock_factory,
            )

        handler.disabled_tools = ["nbi-command-execute"]
        handler.allow_enabling_tools_with_env = False

        message = {
            "id": "test-message-id",
            "type": "chat-request",
            "data": {
                "chatId": "test-chat-id",
                "prompt": "run a command",
                "language": "python",
                "filename": "notebook.ipynb",
                "chatMode": "agent",
                "toolSelections": {
                    "builtinToolsets": [
                        "nbi-notebook-edit",
                        "nbi-command-execute",
                    ],
                    "mcpServers": {},
                    "extensions": {},
                },
                "additionalContext": [],
            },
        }

        handler.on_message(json.dumps(message))

        mock_ai_manager.handle_chat_request.assert_called_once()
        chat_request = mock_ai_manager.handle_chat_request.call_args[0][0]
        assert chat_request.tool_selection.built_in_toolsets == [
            "nbi-notebook-edit"
        ]
