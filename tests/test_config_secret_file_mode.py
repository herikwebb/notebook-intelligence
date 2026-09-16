# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Pin the file-mode contract on ``~/.jupyter/nbi/config.json`` and
``~/.jupyter/nbi/mcp.json``.

Both files carry credentials: ``config.json`` persists the Claude, ACP
and OpenAI-compatible provider ``api_key`` values (unless an env
override blanks them) and ``mcp.json`` persists remote-server
``headers`` and stdio ``env`` values verbatim. ``_atomic_write_json``
defaults to preserving whatever mode the target already has, so a
file first written by an older release under a permissive umask
(0o644) stayed group/world-readable on every later save. On shared-home
topologies (NFS, classroom labs, JupyterHub nodes with traversable
homes) that lets other local users read the keys. ``NBIConfig.save()``
must force 0o600 on every write, the same contract ``user-data.json``
already has, regardless of prior state.
"""

import json
import os
import stat

import pytest

from notebook_intelligence.config import NBIConfig


def _mode(path):
    return stat.S_IMODE(os.stat(path).st_mode)


@pytest.fixture
def isolated_config(tmp_path, monkeypatch):
    """Build an NBIConfig whose user files live under tmp_path so the
    test never touches the real ~/.jupyter/nbi/."""
    monkeypatch.setenv("HOME", str(tmp_path))
    config = NBIConfig()
    user_dir = tmp_path / ".jupyter" / "nbi"
    config.nbi_user_dir = str(user_dir)
    config.user_config_file = str(user_dir / "config.json")
    config.user_mcp_file = str(user_dir / "mcp.json")
    return config


class TestConfigSecretFileMode:
    def test_first_save_is_0o600(self, isolated_config):
        config = isolated_config
        assert not os.path.exists(config.user_config_file)
        assert not os.path.exists(config.user_mcp_file)

        config.user_config = {"claude_settings": {"api_key": "sk-ant-test"}}
        config.user_mcp = {"mcpServers": {"r": {"url": "https://x", "headers": {"Authorization": "Bearer t"}}}}
        config.save()

        assert _mode(config.user_config_file) == 0o600
        assert _mode(config.user_mcp_file) == 0o600

    def test_save_tightens_pre_widened_files(self, isolated_config):
        # A config.json / mcp.json first written by a release that used a
        # plain umask-default open() is 0o644. A later save must not keep
        # re-asserting that mode on a file that now holds API keys.
        config = isolated_config
        os.makedirs(config.nbi_user_dir, exist_ok=True)
        for path in (config.user_config_file, config.user_mcp_file):
            with open(path, "w") as fh:
                json.dump({"old": True}, fh)
            os.chmod(path, 0o644)
            assert _mode(path) == 0o644

        config.user_config = {"claude_settings": {"api_key": "sk-ant-test"}}
        config.user_mcp = {"mcpServers": {}}
        config.save()

        assert _mode(config.user_config_file) == 0o600
        assert _mode(config.user_mcp_file) == 0o600
        assert json.load(open(config.user_config_file)) == config.user_config
        assert json.load(open(config.user_mcp_file)) == config.user_mcp

    def test_set_goes_through_the_same_contract(self, isolated_config):
        # ConfigHandler.post persists via NBIConfig.set(); it must not be
        # able to bypass the mode contract by taking a different path.
        config = isolated_config
        os.makedirs(config.nbi_user_dir, exist_ok=True)
        with open(config.user_config_file, "w") as fh:
            json.dump({}, fh)
        os.chmod(config.user_config_file, 0o664)

        config.set("acp_settings", {"api_key": "sk-openai-test"})

        assert _mode(config.user_config_file) == 0o600
        assert json.load(open(config.user_config_file))["acp_settings"]["api_key"] == "sk-openai-test"
