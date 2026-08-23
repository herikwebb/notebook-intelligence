# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from typing import Any

import tiktoken


CHAT_INPUT_BUDGET_RATIO = 0.8
MESSAGE_OVERHEAD_TOKENS = 4
IMAGE_TOKEN_ESTIMATE = 1024
CONTEXT_OMISSION_NOTICE = (
    "\n\n[Context note: Some earlier conversation or attached context was "
    "omitted or truncated to fit the model context window.]"
)
TRUNCATION_MARKER = "\n...[truncated to fit model context]"

_encoding = tiktoken.encoding_for_model("gpt-4o")


def text_token_count(text: str) -> int:
    return len(_encoding.encode(text))


def truncate_text(
    text: str,
    token_budget: int,
    marker: str = "\n...[truncated]",
) -> str:
    if token_budget <= 0 or text == "":
        return ""

    encoded = _encoding.encode(text)
    if len(encoded) <= token_budget:
        return text

    marker_tokens = text_token_count(marker)
    prefix_size = token_budget - marker_tokens
    while prefix_size > 0:
        prefix = _encoding.decode(encoded[:prefix_size]).rstrip()
        candidate = prefix + marker
        if text_token_count(candidate) <= token_budget:
            return candidate
        prefix_size -= 1
    return ""


def _content_token_count(content: Any) -> int:
    if content is None:
        return 0
    if isinstance(content, str):
        return text_token_count(content)
    if isinstance(content, list):
        return sum(_content_token_count(item) for item in content)
    if isinstance(content, dict):
        content_type = content.get("type")
        if content_type in {"image", "image_url"} or "image_url" in content:
            return IMAGE_TOKEN_ESTIMATE
        if content_type == "text" and isinstance(content.get("text"), str):
            return text_token_count(content["text"])
        return sum(
            _content_token_count(value)
            for key, value in content.items()
            if key != "type"
        )
    return text_token_count(str(content))


def estimate_message_tokens(message: dict) -> int:
    """Estimate a chat message's input cost without serializing image data."""
    tokens = MESSAGE_OVERHEAD_TOKENS + _content_token_count(
        message.get("content")
    )
    for key in ("name", "tool_call_id", "tool_calls"):
        if key in message:
            tokens += _content_token_count(message[key])
    return tokens


def _truncate_text_message(message: dict, token_budget: int) -> dict | None:
    content = message.get("content")
    if not isinstance(content, str):
        return None

    content_budget = token_budget - MESSAGE_OVERHEAD_TOKENS
    truncated_content = truncate_text(
        content,
        content_budget,
        TRUNCATION_MARKER,
    )
    if truncated_content == "":
        return None

    truncated = message.copy()
    truncated["content"] = truncated_content
    return truncated


def _complete_turns(messages: list[dict]) -> list[list[dict]]:
    """Return complete user-to-assistant turns, dropping orphaned messages."""
    turns = []
    current_turn = []
    for message in messages:
        role = message.get("role")
        if not current_turn:
            if role != "user":
                continue
            current_turn = [message]
        else:
            current_turn.append(message)

        if role == "assistant":
            turns.append(current_turn)
            current_turn = []
    return turns


def _with_omission_notice(system_messages: list[dict]) -> list[dict]:
    updated = [message.copy() for message in system_messages]
    if updated and isinstance(updated[-1].get("content"), str):
        updated[-1]["content"] += CONTEXT_OMISSION_NOTICE
    else:
        updated.append({"role": "system", "content": CONTEXT_OMISSION_NOTICE.strip()})
    return updated


def budget_chat_messages(
    messages: list[dict],
    context_window: int,
) -> list[dict]:
    """Fit ask-mode messages to a model window without splitting old turns.

    The system prompt and newest user message are mandatory. Current-turn
    context is next in priority and may be truncated when it is plain text.
    Complete prior turns then fill the remaining budget from newest to oldest.
    """
    if not isinstance(context_window, int) or context_window <= 0:
        return list(messages)

    input_budget = max(1, int(context_window * CHAT_INPUT_BUDGET_RATIO))
    system_end = 0
    while (
        system_end < len(messages)
        and messages[system_end].get("role") == "system"
    ):
        system_end += 1
    system_messages = messages[:system_end]
    conversation = messages[system_end:]

    latest_user_index = next(
        (
            index
            for index in range(len(conversation) - 1, -1, -1)
            if conversation[index].get("role") == "user"
        ),
        None,
    )
    if latest_user_index is None:
        return list(messages)

    latest_user = conversation[latest_user_index]
    trailing_messages = conversation[latest_user_index + 1:]
    preceding_messages = conversation[:latest_user_index]
    last_assistant_index = next(
        (
            index
            for index in range(len(preceding_messages) - 1, -1, -1)
            if preceding_messages[index].get("role") == "assistant"
        ),
        -1,
    )
    past_messages = preceding_messages[:last_assistant_index + 1]
    current_context = preceding_messages[last_assistant_index + 1:]
    complete_turns = _complete_turns(past_messages)
    normalized_past_messages = [
        message for turn in complete_turns for message in turn
    ]
    needs_pruning = (
        sum(estimate_message_tokens(message) for message in messages)
        > input_budget
        or normalized_past_messages != past_messages
    )
    if not needs_pruning:
        return list(messages)

    system_messages = _with_omission_notice(system_messages)

    mandatory_messages = [*system_messages, latest_user, *trailing_messages]
    remaining_budget = max(
        0,
        input_budget
        - sum(
            estimate_message_tokens(message)
            for message in mandatory_messages
        ),
    )

    selected_context = []
    for message in current_context:
        message_tokens = estimate_message_tokens(message)
        if message_tokens <= remaining_budget:
            selected_context.append(message)
            remaining_budget -= message_tokens
            continue

        truncated = _truncate_text_message(message, remaining_budget)
        if truncated is not None:
            selected_context.append(truncated)
            remaining_budget -= estimate_message_tokens(truncated)
        break

    selected_turns = []
    for turn in reversed(complete_turns):
        turn_tokens = sum(estimate_message_tokens(message) for message in turn)
        if turn_tokens > remaining_budget:
            break
        selected_turns.append(turn)
        remaining_budget -= turn_tokens
    selected_turns.reverse()

    return [
        *system_messages,
        *(message for turn in selected_turns for message in turn),
        *selected_context,
        latest_user,
        *trailing_messages,
    ]
