import logging
from unittest.mock import Mock

import notebook_intelligence.chat_history_budget as budget_module
from notebook_intelligence.chat_history_budget import (
    CHAT_INPUT_BUDGET_RATIO,
    CONTEXT_OMISSION_NOTICE,
    TRUNCATION_MARKER,
    budget_chat_messages,
    estimate_message_tokens,
    text_token_count,
    warm_tokenizer_encoding,
)


def test_messages_under_budget_are_unchanged():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Question"},
    ]

    assert budget_chat_messages(messages, 4096) == messages


def test_tokenizer_encoding_is_loaded_lazily_and_cached(monkeypatch):
    encoding = Mock()
    encoding.encode.return_value = [1, 2]
    encoding_for_model = Mock(return_value=encoding)
    budget_module._get_encoding.cache_clear()
    monkeypatch.setattr(
        budget_module.tiktoken,
        "encoding_for_model",
        encoding_for_model,
    )

    try:
        assert budget_module._get_encoding.cache_info().currsize == 0
        assert text_token_count("first") == 2
        assert text_token_count("second") == 2
        encoding_for_model.assert_called_once_with("gpt-4o")
    finally:
        budget_module._get_encoding.cache_clear()


def test_tokenizer_load_failure_uses_cached_utf8_fallback(monkeypatch, caplog):
    encoding_for_model = Mock(side_effect=RuntimeError("offline"))
    budget_module._get_encoding.cache_clear()
    monkeypatch.setattr(
        budget_module.tiktoken,
        "encoding_for_model",
        encoding_for_model,
    )

    try:
        with caplog.at_level(logging.WARNING):
            assert text_token_count("abcdefgh") == 3
            assert text_token_count("abcdefgh") == 3
        encoding_for_model.assert_called_once_with("gpt-4o")
        assert "using the UTF-8 size fallback" in caplog.text
    finally:
        budget_module._get_encoding.cache_clear()


def test_tokenizer_warmup_starts_a_daemon_thread(monkeypatch):
    thread = Mock()
    thread_class = Mock(return_value=thread)
    monkeypatch.setattr(budget_module.threading, "Thread", thread_class)

    warm_tokenizer_encoding()

    thread_class.assert_called_once_with(
        target=budget_module._get_encoding,
        name="nbi-tokenizer-warmup",
        daemon=True,
    )
    thread.start.assert_called_once()


def test_unexpected_budgeting_error_fails_open(monkeypatch, caplog):
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Question"},
    ]
    monkeypatch.setattr(
        budget_module,
        "estimate_message_tokens",
        Mock(side_effect=ValueError("malformed message")),
    )

    with caplog.at_level(logging.ERROR):
        result = budget_chat_messages(messages, 128)

    assert result == messages
    assert "sending the original messages" in caplog.text


def test_keeps_newest_complete_turns_and_drops_older_turns():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "old question " * 500},
        {"role": "assistant", "content": "old answer " * 500},
        {"role": "user", "content": "recent question"},
        {"role": "assistant", "content": "recent answer"},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 256)

    contents = [message["content"] for message in result]
    assert "old question " * 500 not in contents
    assert "old answer " * 500 not in contents
    assert "recent question" in contents
    assert "recent answer" in contents
    assert contents[-1] == "current question"
    assert CONTEXT_OMISSION_NOTICE in contents[0]


def test_current_context_is_prioritized_and_truncated():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "attached context " * 500},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 128)

    assert result[-1] == messages[-1]
    assert result[-2]["role"] == "user"
    assert result[-2]["content"].endswith(TRUNCATION_MARKER)
    assert len(result[-2]["content"]) < len(messages[-2]["content"])
    assert sum(estimate_message_tokens(message) for message in result) <= int(
        128 * CHAT_INPUT_BUDGET_RATIO
    )


def test_messages_under_budget_are_not_normalized():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "assistant", "content": "orphaned answer"},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 4096)

    assert result == messages


def test_pruning_drops_an_orphaned_assistant_message():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "assistant", "content": "orphaned answer " * 500},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 128)

    assert [message["role"] for message in result] == ["system", "user"]
    assert result[-1]["content"] == "current question"


def test_tool_call_turn_is_kept_complete_when_history_is_pruned():
    tool_call = {
        "id": "call-1",
        "type": "function",
        "function": {"name": "inspect_data", "arguments": "{}"},
    }
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "old question " * 500},
        {"role": "assistant", "content": "old answer " * 500},
        {"role": "user", "content": "inspect the dataframe"},
        {"role": "assistant", "content": "", "tool_calls": [tool_call]},
        {"role": "tool", "content": "5 rows", "tool_call_id": "call-1"},
        {"role": "assistant", "content": "The dataframe has 5 rows."},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 512)

    assert [message["role"] for message in result[1:]] == [
        "user",
        "assistant",
        "tool",
        "assistant",
        "user",
    ]
    assert result[2]["tool_calls"] == [tool_call]
    assert result[3]["tool_call_id"] == "call-1"


def test_incomplete_tool_call_turn_is_dropped_as_a_unit():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "old question " * 500},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-1", "function": {"name": "inspect"}}],
        },
        {"role": "tool", "content": "partial result", "tool_call_id": "call-1"},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 128)

    assert [message["role"] for message in result] == ["system", "user"]
    assert result[-1]["content"] == "current question"


def test_trailing_tool_message_is_dropped_when_pruning():
    messages = [
        {"role": "system", "content": "Be concise."},
        {
            "role": "assistant",
            "content": "",
            "tool_calls": [{"id": "call-1", "function": {"name": "inspect"}}],
        },
        {"role": "user", "content": "current question " * 500},
        {"role": "tool", "content": "late result", "tool_call_id": "call-1"},
    ]

    result = budget_chat_messages(messages, 128)

    assert [message["role"] for message in result] == ["system", "user"]
    assert result[-1]["content"].endswith(TRUNCATION_MARKER)


def test_multimodal_context_uses_fixed_image_estimate_and_is_omitted():
    image_context = {
        "role": "user",
        "content": [
            {"type": "text", "text": "Attached image"},
            {
                "type": "image_url",
                "image_url": {"url": "data:image/png;base64," + "a" * 10000},
            },
        ],
    }
    messages = [
        {"role": "system", "content": "Be concise."},
        image_context,
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 256)

    assert image_context not in result
    assert result[-1]["content"] == "current question"


def test_system_and_latest_user_survive_an_extremely_small_window(caplog):
    messages = [
        {"role": "system", "content": "mandatory system instructions"},
        {"role": "user", "content": "mandatory user request"},
    ]

    with caplog.at_level(logging.WARNING):
        result = budget_chat_messages(messages, 1)

    assert result[0]["content"].startswith("mandatory system instructions")
    assert result[-1] == messages[-1]
    assert "Mandatory chat context requires" in caplog.text


def test_oversized_latest_user_request_is_truncated_as_last_resort():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "mandatory request " * 500},
    ]

    result = budget_chat_messages(messages, 128)

    assert result[-1]["content"].endswith(TRUNCATION_MARKER)
    assert sum(estimate_message_tokens(message) for message in result) <= int(
        128 * CHAT_INPUT_BUDGET_RATIO
    )


def test_invalid_context_window_leaves_messages_unchanged():
    messages = [{"role": "user", "content": "Question"}]

    assert budget_chat_messages(messages, 0) == messages
    assert budget_chat_messages(messages, "4096") == messages
