"""Regression tests: the Claude Code built-in tool grant must reach the agent.

``NBI_CLAUDE_CODE_TOOLS_POLICY=force-off`` strips the built-in tool set from
the policy-applied ``claude_settings['tools']`` list. That list shaped only the
capabilities response and the config write filter; the client options handed
to the SDK never consulted it, so the CLI still started with its full built-in
tool set under an admin lock.
"""

import dataclasses
from types import SimpleNamespace

from claude_agent_sdk import ClaudeAgentOptions

import notebook_intelligence.claude as claude_module
from notebook_intelligence import util as util_mod
from notebook_intelligence.api import ClaudeToolType
from notebook_intelligence.claude import (
    ClaudeCodeChatParticipant,
    _built_in_tool_restrictions,
)
from notebook_intelligence.feature_flags import (
    POLICY_FORCE_OFF,
    apply_claude_policies,
)


def _participant_with_settings(claude_settings: dict) -> ClaudeCodeChatParticipant:
    participant = ClaudeCodeChatParticipant.__new__(ClaudeCodeChatParticipant)
    participant._host = SimpleNamespace(
        nbi_config=SimpleNamespace(claude_settings=claude_settings)
    )
    return participant


class TestBuiltInToolRestrictions:
    def test_granted_set_adds_no_restriction(self):
        assert _built_in_tool_restrictions(
            {"tools": [ClaudeToolType.ClaudeCodeTools.value]}
        ) == {}

    def test_stripped_set_disables_built_in_tools(self):
        restrictions = _built_in_tool_restrictions({"tools": []})

        option_fields = {f.name for f in dataclasses.fields(ClaudeAgentOptions)}
        if "tools" in option_fields:
            assert restrictions == {"tools": []}
        else:
            assert "Bash" in restrictions["disallowed_tools"]
            assert "Write" in restrictions["disallowed_tools"]

    def test_force_off_policy_reaches_the_restriction(self):
        settings = apply_claude_policies(
            {"tools": [ClaudeToolType.ClaudeCodeTools.value]},
            {"claude_code_tools": POLICY_FORCE_OFF},
        )

        assert _built_in_tool_restrictions(settings) != {}


class TestCreateClientOptions:
    def test_force_off_policy_restricts_agent_tools(self, tmp_path, monkeypatch):
        monkeypatch.setattr(util_mod, "_jupyter_root_dir", str(tmp_path))
        monkeypatch.setattr(claude_module, "resolve_claude_cli_path", lambda: None)
        settings = apply_claude_policies(
            {"tools": [ClaudeToolType.ClaudeCodeTools.value]},
            {"claude_code_tools": POLICY_FORCE_OFF},
        )

        options = _participant_with_settings(settings)._create_client_options()

        restricted = getattr(options, "tools", None) == [] or (
            "Bash" in (getattr(options, "disallowed_tools", None) or [])
        )
        assert restricted
        assert options.mcp_servers == {}

    def test_granted_set_leaves_agent_tools_unrestricted(self, tmp_path, monkeypatch):
        monkeypatch.setattr(util_mod, "_jupyter_root_dir", str(tmp_path))
        monkeypatch.setattr(claude_module, "resolve_claude_cli_path", lambda: None)
        settings = {"tools": [ClaudeToolType.ClaudeCodeTools.value]}

        options = _participant_with_settings(settings)._create_client_options()

        assert getattr(options, "tools", None) is None
        assert not getattr(options, "disallowed_tools", None)
