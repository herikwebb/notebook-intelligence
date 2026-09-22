# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""``mcp-config-file`` must not hand MCP credentials to the file editor.

The Settings panel's Add / Edit flow copies the GET response into
``<jupyter root>/nbi.mcp.temp.json`` (umask permissions, agent working
directory, best-effort cleanup), so ``headers`` and ``env`` credentials
have to leave the server masked and be restored from the stored config
when the edit is posted back. These tests pin both halves and the handler
wiring between them.
"""

import json
from unittest.mock import MagicMock, patch

import pytest
from tornado.testing import AsyncHTTPTestCase

from notebook_intelligence.mcp_config_secrets import (
    REDACTED_VALUE,
    MCPConfigSecretError,
    is_secret_mcp_value,
    redact_mcp_secrets,
    restore_mcp_secrets,
)

STORED = {
    "mcpServers": {
        "remote": {
            "url": "https://mcp.example.com/mcp",
            "headers": {
                "Authorization": "Bearer mysecrettoken",
                "X-API-Key": "abc123",
                "Accept": "application/json",
            },
        },
        "local": {
            "command": "uvx",
            "args": ["some-server"],
            "env": {
                "BRAVE_API_KEY": "brave-key",
                "GITHUB_PERSONAL_ACCESS_TOKEN": "ghp_xxx",
                "DATABASE_URL": "postgres://user:pass@db.internal/app",
                "NODE_ENV": "production",
                "EMPTY_TOKEN": "",
            },
        },
        "plain": {"command": "npx", "args": ["-y", "server"]},
    }
}


class TestIsSecretMcpValue:
    @pytest.mark.parametrize(
        "key",
        [
            "Authorization",
            "Proxy-Authorization",
            "X-API-Key",
            "x-auth-token",
            "Cookie",
            "OPENAI_API_KEY",
            "SLACK_BOT_TOKEN",
            "DB_PASSWORD",
            "AWS_SECRET_ACCESS_KEY",
        ],
    )
    def test_credential_names_are_secret(self, key):
        assert is_secret_mcp_value(key, "value-of-any-length")

    @pytest.mark.parametrize("key", ["Accept", "User-Agent", "NODE_ENV", "HOME", "PORT"])
    def test_plain_names_are_not_secret(self, key):
        assert not is_secret_mcp_value(key, "value")

    def test_url_userinfo_is_secret_whatever_the_key(self):
        assert is_secret_mcp_value("DATABASE_URL", "postgres://user:pass@db/app")
        assert is_secret_mcp_value("UPSTREAM", "https://token@host/path")
        assert not is_secret_mcp_value("UPSTREAM", "https://host/path?x=1")

    def test_empty_or_non_string_values_pass_through(self):
        assert not is_secret_mcp_value("API_KEY", "")
        assert not is_secret_mcp_value("API_KEY", None)
        assert not is_secret_mcp_value("API_KEY", 42)


class TestRedactMcpSecrets:
    def test_masks_header_and_env_credentials_only(self):
        redacted = redact_mcp_secrets(STORED)
        remote = redacted["mcpServers"]["remote"]
        local = redacted["mcpServers"]["local"]
        assert remote["headers"] == {
            "Authorization": REDACTED_VALUE,
            "X-API-Key": REDACTED_VALUE,
            "Accept": "application/json",
        }
        assert local["env"] == {
            "BRAVE_API_KEY": REDACTED_VALUE,
            "GITHUB_PERSONAL_ACCESS_TOKEN": REDACTED_VALUE,
            "DATABASE_URL": REDACTED_VALUE,
            "NODE_ENV": "production",
            "EMPTY_TOKEN": "",
        }
        # Nothing outside env/headers is touched.
        assert remote["url"] == STORED["mcpServers"]["remote"]["url"]
        assert local["command"] == "uvx" and local["args"] == ["some-server"]
        assert redacted["mcpServers"]["plain"] == STORED["mcpServers"]["plain"]

    def test_no_secret_literal_survives_serialization(self):
        body = json.dumps(redact_mcp_secrets(STORED))
        for literal in ("mysecrettoken", "abc123", "brave-key", "ghp_xxx", "user:pass"):
            assert literal not in body

    def test_does_not_mutate_the_input(self):
        snapshot = json.dumps(STORED, sort_keys=True)
        redact_mcp_secrets(STORED)
        assert json.dumps(STORED, sort_keys=True) == snapshot

    @pytest.mark.parametrize(
        "config",
        [
            {},
            {"mcpServers": {}},
            {"mcpServers": None},
            {"mcpServers": {"x": None, "y": "nope", "z": {"env": "bad", "headers": []}}},
            None,
        ],
    )
    def test_odd_shapes_pass_through_unchanged(self, config):
        assert redact_mcp_secrets(config) == config


class TestRestoreMcpSecrets:
    def test_placeholders_are_replaced_from_the_stored_config(self):
        posted = redact_mcp_secrets(STORED)
        restored = restore_mcp_secrets(posted, STORED)
        assert restored == STORED
        # The posted document is not modified in place.
        assert posted["mcpServers"]["remote"]["headers"]["Authorization"] == REDACTED_VALUE

    def test_new_values_and_untouched_entries_are_kept(self):
        posted = redact_mcp_secrets(STORED)
        posted["mcpServers"]["remote"]["headers"]["Authorization"] = "Bearer rotated"
        posted["mcpServers"]["local"]["env"]["NODE_ENV"] = "development"
        posted["mcpServers"]["local"]["env"]["NEW_TOKEN"] = "fresh"
        restored = restore_mcp_secrets(posted, STORED)
        assert restored["mcpServers"]["remote"]["headers"]["Authorization"] == "Bearer rotated"
        assert restored["mcpServers"]["remote"]["headers"]["X-API-Key"] == "abc123"
        assert restored["mcpServers"]["local"]["env"]["NODE_ENV"] == "development"
        assert restored["mcpServers"]["local"]["env"]["NEW_TOKEN"] == "fresh"
        assert restored["mcpServers"]["local"]["env"]["BRAVE_API_KEY"] == "brave-key"

    def test_without_placeholders_the_posted_object_is_returned_as_is(self):
        posted = {"mcpServers": {"voice": {"command": "uvx"}}}
        # ``stored`` is never consulted, so even an unusable value is fine.
        assert restore_mcp_secrets(posted, MagicMock()) is posted

    @pytest.mark.parametrize(
        "server, section, key",
        [
            ("renamed", "headers", "Authorization"),  # server name changed
            ("remote", "headers", "X-Other-Token"),  # key the store never had
            ("local", "env", "EMPTY_TOKEN"),  # stored value was empty, not masked
            ("local", "env", "NODE_ENV"),  # served in the clear, so never a placeholder
            ("plain", "env", "API_KEY"),  # section the store never had
        ],
    )
    def test_placeholder_with_nothing_stored_is_rejected(self, server, section, key):
        posted = {"mcpServers": {server: {section: {key: REDACTED_VALUE}}}}
        with pytest.raises(MCPConfigSecretError) as excinfo:
            restore_mcp_secrets(posted, STORED)
        assert f"mcpServers.{server}.{section}.{key}" in str(excinfo.value)
        assert isinstance(excinfo.value, ValueError)


class MCPConfigFileRoundTrip(AsyncHTTPTestCase):
    """Drive the real handler for both verbs.

    ``test_get_never_serves_credentials`` fails on the unpatched tree: the
    response body carried every stored header / env value verbatim.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        from jupyter_server.base.handlers import APIHandler

        async def _noop(_self):
            return None

        cls._api_handler_patcher = patch.object(APIHandler, "prepare", _noop)
        cls._api_handler_patcher.start()
        cls._current_user_patcher = patch.object(
            APIHandler,
            "current_user",
            property(lambda _self: {"name": "test-user"}),
        )
        cls._current_user_patcher.start()

    @classmethod
    def tearDownClass(cls):
        cls._current_user_patcher.stop()
        cls._api_handler_patcher.stop()
        super().tearDownClass()

    def get_app(self):
        from tornado.web import Application

        from notebook_intelligence.extension import MCPConfigFileHandler

        return Application([(r"/mcp-config-file", MCPConfigFileHandler)])

    def _mock_manager(self):
        mock_asm = MagicMock()
        mock_asm.nbi_config.mcp = json.loads(json.dumps(STORED))
        mock_asm.get_mcp_stdio_command_allowlist.return_value = []
        return mock_asm

    def test_get_never_serves_credentials(self):
        from notebook_intelligence import extension as ext_module

        with patch.object(ext_module, "ai_service_manager", self._mock_manager()):
            resp = self.fetch("/mcp-config-file", method="GET", raise_error=False)
        assert resp.code == 200
        body = resp.body.decode("utf-8")
        for literal in ("mysecrettoken", "abc123", "brave-key", "ghp_xxx", "user:pass"):
            assert literal not in body
        served = json.loads(body)
        assert served["mcpServers"]["remote"]["headers"]["Authorization"] == REDACTED_VALUE
        assert served["mcpServers"]["local"]["env"]["NODE_ENV"] == "production"
        assert served["mcpServers"]["plain"] == STORED["mcpServers"]["plain"]

    def test_post_restores_placeholders_before_persisting(self):
        from notebook_intelligence import extension as ext_module

        posted = redact_mcp_secrets(STORED)
        posted["mcpServers"]["remote"]["headers"]["Authorization"] = "Bearer rotated"
        mock_asm = self._mock_manager()
        with patch.object(ext_module, "ai_service_manager", mock_asm):
            resp = self.fetch(
                "/mcp-config-file",
                method="POST",
                body=json.dumps(posted),
                headers={"Content-Type": "application/json"},
                raise_error=False,
            )
        assert resp.code == 200, resp.body
        persisted = mock_asm.nbi_config.user_mcp
        assert persisted["mcpServers"]["remote"]["headers"]["Authorization"] == "Bearer rotated"
        assert persisted["mcpServers"]["remote"]["headers"]["X-API-Key"] == "abc123"
        assert persisted["mcpServers"]["local"]["env"]["BRAVE_API_KEY"] == "brave-key"
        assert persisted["mcpServers"]["local"]["env"]["DATABASE_URL"] == (
            "postgres://user:pass@db.internal/app"
        )
        assert REDACTED_VALUE not in json.dumps(persisted)
        assert mock_asm.nbi_config.save.called
        assert mock_asm.update_mcp_servers.called

    def test_post_with_unrestorable_placeholder_is_a_400_and_persists_nothing(self):
        from notebook_intelligence import extension as ext_module

        posted = {
            "mcpServers": {
                "renamed": {
                    "url": "https://mcp.example.com/mcp",
                    "headers": {"Authorization": REDACTED_VALUE},
                }
            }
        }
        mock_asm = self._mock_manager()
        with patch.object(ext_module, "ai_service_manager", mock_asm):
            resp = self.fetch(
                "/mcp-config-file",
                method="POST",
                body=json.dumps(posted),
                headers={"Content-Type": "application/json"},
                raise_error=False,
            )
        assert resp.code == 400
        assert b"mcpServers.renamed.headers.Authorization" in resp.body
        assert not mock_asm.nbi_config.save.called
        assert not mock_asm.update_mcp_servers.called
