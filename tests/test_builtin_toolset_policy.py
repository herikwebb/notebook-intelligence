# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Tests for built-in toolset admin denylist helpers."""

from notebook_intelligence.util import (
    filter_enabled_builtin_toolsets,
    is_builtin_toolset_enabled,
)


class TestBuiltinToolsetPolicy:
    def test_enabled_when_denylist_empty(self):
        assert is_builtin_toolset_enabled("nbi-command-execute", None, False)

    def test_disabled_when_on_denylist(self):
        assert not is_builtin_toolset_enabled(
            "nbi-command-execute", ["nbi-command-execute"], False
        )

    def test_env_reenable_when_allowed(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_BUILTIN_TOOLS", "nbi-command-execute")
        assert is_builtin_toolset_enabled(
            "nbi-command-execute", ["nbi-command-execute"], True
        )

    def test_filter_drops_disabled_ids(self):
        result = filter_enabled_builtin_toolsets(
            ["nbi-notebook-edit", "nbi-command-execute"],
            ["nbi-command-execute"],
            False,
        )
        assert result == ["nbi-notebook-edit"]

    def test_filter_preserves_order(self):
        result = filter_enabled_builtin_toolsets(
            ["nbi-file-read", "nbi-notebook-edit"],
            [],
            False,
        )
        assert result == ["nbi-file-read", "nbi-notebook-edit"]
