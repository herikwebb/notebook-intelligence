# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Secret-scrub test for the Jupyter-terminal shell tool's return value.

``execute_command`` and ``run_command_in_embedded_terminal`` both route
their command output through ``redact_env_secrets`` before it reaches
chat. ``run_command_in_jupyter_terminal`` returned the UI command's reply
verbatim, so a model-issued ``env`` in a Jupyter terminal pasted the
user's secret-bearing environment into chat history and on to the model
provider. These tests pin the scrub on that path too.
"""

import asyncio
from unittest.mock import MagicMock

import pytest

import notebook_intelligence.built_in_toolsets as toolsets
from notebook_intelligence.util import set_jupyter_root_dir


_SECRET = "ghp_0123456789abcdefghijklmnopqrstuvwxyz"


@pytest.fixture
def jupyter_root(tmp_path, monkeypatch):
    root = tmp_path / "workspace"
    root.mkdir()
    monkeypatch.setattr(toolsets, "get_jupyter_root_dir", lambda: str(root))
    set_jupyter_root_dir(str(root))
    return root


def _invoke(ui_reply: str) -> str:
    """Drive run_command_in_jupyter_terminal with a stubbed UI bridge that
    replays ``ui_reply`` as the terminal's captured output."""
    tool = toolsets.run_command_in_jupyter_terminal._tool_function
    response = MagicMock()

    async def _run_ui_command(_command, _args):
        return ui_reply

    response.run_ui_command = _run_ui_command
    return asyncio.run(tool(command="env", working_directory=".", response=response))


def test_env_value_of_sensitive_var_is_scrubbed(jupyter_root, monkeypatch):
    monkeypatch.setenv("GITHUB_TOKEN", _SECRET)
    out = _invoke(f"Command executed in Jupyter terminal, output: GITHUB_TOKEN={_SECRET}\n")
    assert _SECRET not in out
    assert "<redacted>" in out


def test_known_prefix_token_is_scrubbed_without_matching_env(jupyter_root, monkeypatch):
    monkeypatch.delenv("GITHUB_TOKEN", raising=False)
    out = _invoke(f"Command executed in Jupyter terminal, output: token={_SECRET}\n")
    assert _SECRET not in out
    assert "<redacted>" in out


def test_benign_output_passes_through(jupyter_root):
    out = _invoke("Command executed in Jupyter terminal, output: hello\n")
    assert "hello" in out


def test_non_string_ui_reply_does_not_raise(jupyter_root):
    """The UI bridge is typed as returning a dict; a non-string reply must
    still survive the scrub rather than blowing up the tool call."""
    out = _invoke(None)
    assert isinstance(out, str)
