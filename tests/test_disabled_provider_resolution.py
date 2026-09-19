# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""`disabled_providers` has to hold at model resolution, not only in the
capabilities picker.

The denylist used to live solely in `GetCapabilitiesHandler.get`, which
shaped the provider and model lists the settings panel renders. The chat
and inline models themselves are resolved by
`AIServiceManager.update_models_from_config` from `config.json`, and that
path never consulted the denylist: a hand-rolled config POST or a hand edit
naming a disabled provider was served on the next turn. `readiness.py`
already tells the user a provider that fails to resolve "may be disabled by
an administrator (see disabled_providers)", so resolution is where the gate
belongs. `AIServiceManager.is_provider_enabled` is now the single predicate
and `get_llm_provider` applies it.
"""

from unittest.mock import Mock

import pytest

from notebook_intelligence.ai_service_manager import AIServiceManager
from notebook_intelligence.llm_providers.ollama_llm_provider import OllamaLLMProvider
from notebook_intelligence.llm_providers.openai_compatible_llm_provider import (
    OpenAICompatibleLLMProvider,
)


OPENAI_COMPAT_CHAT = "openai-compatible-chat-model"
OPENAI_COMPAT_INLINE = "openai-compatible-inline-completion-model"


def _make_manager(options=None, chat_model=None, inline_completion_model=None):
    """A manager with the two providers registered and no Host bootstrap.

    Mirrors `_make_manager` in test_ai_service_manager_dispatch.py; the
    `__init__` path would connect MCP servers and start file watchers.
    """
    manager = AIServiceManager.__new__(AIServiceManager)
    manager._options = dict(options or {})
    manager.llm_providers = {}
    manager.chat_participants = {}
    manager._acp_chat_participant = None
    manager._chatbook_acp_client = None
    manager._websocket_connector = None
    claude_participant = Mock()
    claude_participant.id = "claude-code"
    manager._claude_code_chat_participant = claude_participant

    config = Mock()
    config.using_github_copilot_service = False
    config.store_github_access_token = False
    config.claude_settings = {"enabled": False}
    config.acp_settings = {"enabled": False}
    config.chat_model = chat_model or {"provider": "none", "model": "none"}
    config.inline_completion_model = inline_completion_model or {
        "provider": "none",
        "model": "none",
    }
    manager._nbi_config = config

    manager.register_llm_provider(OpenAICompatibleLLMProvider())
    manager.register_llm_provider(OllamaLLMProvider())
    return manager


def _openai_compat_config():
    # What a hand-rolled POST /notebook-intelligence/config, or a hand edit of
    # ~/.jupyter/nbi/config.json, persists when the picker no longer offers
    # the provider.
    return (
        {
            "provider": "openai-compatible",
            "model": OPENAI_COMPAT_CHAT,
            "properties": [{"id": "base_url", "value": "https://example.invalid/v1"}],
        },
        {"provider": "openai-compatible", "model": OPENAI_COMPAT_INLINE, "properties": []},
    )


class TestIsProviderEnabled:
    def test_no_denylist_enables_everything(self):
        manager = _make_manager({"disabled_providers": None})
        assert manager.is_provider_enabled("openai-compatible")
        assert manager.is_provider_enabled("anything")

    def test_empty_denylist_enables_everything(self):
        manager = _make_manager({"disabled_providers": []})
        assert manager.is_provider_enabled("ollama")

    def test_denylisted_provider_is_disabled(self):
        manager = _make_manager({"disabled_providers": ["ollama"]})
        assert not manager.is_provider_enabled("ollama")
        assert manager.is_provider_enabled("openai-compatible")

    def test_env_re_enable_requires_the_opt_in_flag(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_PROVIDERS", "ollama")
        locked = _make_manager({"disabled_providers": ["ollama"]})
        assert not locked.is_provider_enabled("ollama")

        opted_in = _make_manager(
            {"disabled_providers": ["ollama"], "allow_enabling_providers_with_env": True}
        )
        assert opted_in.is_provider_enabled("ollama")

    def test_env_re_enable_only_covers_the_named_provider(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_PROVIDERS", "ollama")
        manager = _make_manager(
            {
                "disabled_providers": ["ollama", "openai-compatible"],
                "allow_enabling_providers_with_env": True,
            }
        )
        assert manager.is_provider_enabled("ollama")
        assert not manager.is_provider_enabled("openai-compatible")


class TestGetLLMProvider:
    def test_returns_registered_provider_when_enabled(self):
        manager = _make_manager({"disabled_providers": ["ollama"]})
        provider = manager.get_llm_provider("openai-compatible")
        assert provider is not None and provider.id == "openai-compatible"

    def test_returns_none_for_a_disabled_provider(self):
        manager = _make_manager({"disabled_providers": ["openai-compatible"]})
        assert manager.get_llm_provider("openai-compatible") is None
        # The registration itself is untouched: the capabilities response
        # still walks llm_providers through the same predicate.
        assert "openai-compatible" in manager.llm_providers

    def test_model_ref_lookup_honors_the_denylist(self):
        manager = _make_manager({"disabled_providers": ["openai-compatible"]})
        assert manager.get_llm_provider_for_model_ref("openai-compatible::x") is None
        assert manager.get_chat_model(f"openai-compatible::{OPENAI_COMPAT_CHAT}") is None


class TestUpdateModelsFromConfig:
    def test_disabled_provider_does_not_resolve_from_config(self):
        chat_cfg, inline_cfg = _openai_compat_config()
        manager = _make_manager(
            {"disabled_providers": ["openai-compatible", "litellm-compatible"]},
            chat_model=chat_cfg,
            inline_completion_model=inline_cfg,
        )

        manager.update_models_from_config()

        assert manager.chat_model is None
        assert manager.inline_completion_model is None

    def test_enabled_provider_still_resolves_from_config(self):
        chat_cfg, inline_cfg = _openai_compat_config()
        manager = _make_manager(
            {"disabled_providers": ["ollama"]},
            chat_model=chat_cfg,
            inline_completion_model=inline_cfg,
        )

        manager.update_models_from_config()

        assert manager.chat_model is not None
        assert manager.chat_model.provider.id == "openai-compatible"
        assert manager.inline_completion_model is not None
        assert manager.inline_completion_model.provider.id == "openai-compatible"

    def test_env_re_enabled_provider_resolves_from_config(self, monkeypatch):
        monkeypatch.setenv("NBI_ENABLED_PROVIDERS", "openai-compatible")
        chat_cfg, inline_cfg = _openai_compat_config()
        manager = _make_manager(
            {
                "disabled_providers": ["openai-compatible"],
                "allow_enabling_providers_with_env": True,
            },
            chat_model=chat_cfg,
            inline_completion_model=inline_cfg,
        )

        manager.update_models_from_config()

        assert manager.chat_model is not None
        assert manager.inline_completion_model is not None

    @pytest.mark.parametrize("field", ["chat_model", "inline_completion_model"])
    def test_disabled_copilot_provider_skips_the_copilot_login(self, monkeypatch, field):
        import notebook_intelligence.ai_service_manager as asm

        login = Mock()
        monkeypatch.setattr(asm.github_copilot, "login_with_existing_credentials", login)
        monkeypatch.setattr(
            asm.github_copilot, "enable_github_login_status_change_updater", Mock()
        )
        manager = _make_manager({"disabled_providers": ["github-copilot"]})
        manager._nbi_config.using_github_copilot_service = True
        setattr(
            manager._nbi_config, field, {"provider": "github-copilot", "model": "gpt-4.1"}
        )

        manager.update_models_from_config()

        login.assert_not_called()
        assert manager.chat_model is None
        assert manager.inline_completion_model is None
