# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Labels of the built-in providers' model settings, in the user's language.

The OpenAI- and LiteLLM-compatible models describe their settings (API key,
model, base URL, context window) in English; the capabilities response
translates them for the settings panel by model and property id, so a change
of English wording cannot turn the translation off. Models an extension adds
are sent as they describe themselves.
"""

from __future__ import annotations

from typing import Optional

from notebook_intelligence.i18n import TranslationBundle

# Built-in (provider, model) ids, and whether the model must stream (the
# chat models). The provider is part of the key: an extension's provider can
# reuse a built-in model id with its own labels.
_BUILT_IN_MODELS = {
    ("openai-compatible", "openai-compatible-chat-model"): True,
    ("openai-compatible", "openai-compatible-inline-completion-model"): False,
    ("litellm-compatible", "litellm-compatible-chat-model"): True,
    ("litellm-compatible", "litellm-compatible-inline-completion-model"): False,
}


def _labels(
    trans: TranslationBundle, property_id: str, streaming: bool
) -> Optional[dict]:
    if property_id == "api_key":
        return {"name": trans.__("API key"), "description": trans.__("API key")}
    if property_id == "model_id":
        return {
            "name": trans.__("Model"),
            "description": trans.__("Model (must support streaming)")
            if streaming
            else trans.__("Model"),
        }
    if property_id == "base_url":
        return {"name": trans.__("Base URL"), "description": trans.__("Base URL")}
    if property_id == "context_window":
        return {
            "name": trans.__("Context window"),
            "description": trans.__("Context window length"),
        }
    return None


def translate_model_properties(
    trans: TranslationBundle, models: list[dict]
) -> list[dict]:
    """The capabilities model list with the built-in models' setting labels
    translated; everything else, values included, unchanged."""
    translated = []
    for model in models:
        streaming = _BUILT_IN_MODELS.get((model.get("provider"), model.get("id")))
        if streaming is None:
            translated.append(model)
            continue
        properties = []
        for prop in model.get("properties", []):
            labels = _labels(trans, prop.get("id"), streaming)
            properties.append({**prop, **labels} if labels else prop)
        translated.append({**model, "properties": properties})
    return translated
