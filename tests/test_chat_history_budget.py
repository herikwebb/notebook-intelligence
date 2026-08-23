from notebook_intelligence.chat_history_budget import (
    CHAT_INPUT_BUDGET_RATIO,
    CONTEXT_OMISSION_NOTICE,
    TRUNCATION_MARKER,
    budget_chat_messages,
    estimate_message_tokens,
)


def test_messages_under_budget_are_unchanged():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "user", "content": "Question"},
    ]

    assert budget_chat_messages(messages, 4096) == messages


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


def test_pruning_drops_an_orphaned_assistant_message():
    messages = [
        {"role": "system", "content": "Be concise."},
        {"role": "assistant", "content": "orphaned answer"},
        {"role": "user", "content": "current question"},
    ]

    result = budget_chat_messages(messages, 4096)

    assert [message["role"] for message in result] == ["system", "user"]
    assert result[-1]["content"] == "current question"


def test_system_and_latest_user_survive_an_extremely_small_window():
    messages = [
        {"role": "system", "content": "mandatory system instructions"},
        {"role": "user", "content": "mandatory user request"},
    ]

    result = budget_chat_messages(messages, 1)

    assert result[0]["content"].startswith("mandatory system instructions")
    assert result[-1] == messages[-1]


def test_invalid_context_window_leaves_messages_unchanged():
    messages = [{"role": "user", "content": "Question"}]

    assert budget_chat_messages(messages, 0) == messages
    assert budget_chat_messages(messages, "4096") == messages
