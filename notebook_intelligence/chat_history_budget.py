# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from __future__ import annotations

import logging
import threading
import time
from typing import Any

import tiktoken


CHAT_INPUT_BUDGET_RATIO = 0.8
MESSAGE_OVERHEAD_TOKENS = 4
# A deterministic cross-provider baseline. Exact vision token cost varies by
# provider, resolution, and detail mode. The 20% output reserve reduces, but
# cannot eliminate, that variance without provider-specific image inspection.
IMAGE_TOKEN_ESTIMATE = 1024
CONTEXT_OMISSION_NOTICE = (
    "\n\n[Context note: Some earlier conversation or attached context was "
    "omitted or truncated to fit the model context window.]"
)
SHORT_CONTEXT_OMISSION_NOTICE = "\n\n[Context omitted to fit model window.]"
TRUNCATION_MARKER = "\n...[truncated to fit model context]"

log = logging.getLogger(__name__)
_TOKENIZER_MAX_LOAD_ATTEMPTS = 3
_TOKENIZER_LOAD_TIMEOUT_SECONDS = 30
_IMAGE_OMISSION_TEXT = "[Image omitted.]"
_tokenizer_lock = threading.Lock()
_tokenizer_encoding: Any | None = None
_tokenizer_load_attempts = 0
_tokenizer_load_in_progress = False
_tokenizer_load_started_at = 0.0
_tokenizer_load_generation = 0
_tokenizer_fallback_logged = False


def _load_tokenizer_encoding(load_generation: int) -> None:
    global _tokenizer_encoding, _tokenizer_load_in_progress
    global _tokenizer_load_started_at
    encoding = None
    try:
        encoding = tiktoken.encoding_for_model("gpt-4o")
    except Exception as error:
        log.warning(
            "Could not warm the gpt-4o tokenizer; using the UTF-8 size "
            "fallback until a later retry succeeds: %s",
            error,
        )
    finally:
        with _tokenizer_lock:
            if encoding is not None:
                _tokenizer_encoding = encoding
            if (
                encoding is not None
                or load_generation == _tokenizer_load_generation
            ):
                _tokenizer_load_in_progress = False
                _tokenizer_load_started_at = 0.0


def warm_tokenizer_encoding() -> None:
    """Warm tokenizer data asynchronously, retrying transient failures."""
    global _tokenizer_load_attempts, _tokenizer_load_in_progress
    global _tokenizer_load_started_at, _tokenizer_load_generation
    stale_load = False
    with _tokenizer_lock:
        if _tokenizer_encoding is not None:
            return
        now = time.monotonic()
        if _tokenizer_load_in_progress:
            if (
                now - _tokenizer_load_started_at
                < _TOKENIZER_LOAD_TIMEOUT_SECONDS
            ):
                return
            stale_load = True
            _tokenizer_load_in_progress = False
        if _tokenizer_load_attempts >= _TOKENIZER_MAX_LOAD_ATTEMPTS:
            return
        _tokenizer_load_attempts += 1
        _tokenizer_load_in_progress = True
        _tokenizer_load_started_at = now
        _tokenizer_load_generation += 1
        load_generation = _tokenizer_load_generation
    if stale_load:
        log.warning(
            "Tokenizer warm-up exceeded %d seconds; starting a bounded retry",
            _TOKENIZER_LOAD_TIMEOUT_SECONDS,
        )
    thread = threading.Thread(
        target=_load_tokenizer_encoding,
        args=(load_generation,),
        name="nbi-tokenizer-warmup",
        daemon=True,
    )
    try:
        thread.start()
    except Exception as error:
        with _tokenizer_lock:
            if load_generation == _tokenizer_load_generation:
                _tokenizer_load_in_progress = False
                _tokenizer_load_started_at = 0.0
        log.warning(
            "Could not start the tokenizer warm-up thread; using the UTF-8 "
            "size fallback until a later retry succeeds: %s",
            error,
        )


def _get_encoding():
    with _tokenizer_lock:
        encoding = _tokenizer_encoding
    if encoding is None:
        warm_tokenizer_encoding()
        with _tokenizer_lock:
            encoding = _tokenizer_encoding
    return encoding


def _warn_tokenizer_fallback_once() -> None:
    global _tokenizer_fallback_logged
    with _tokenizer_lock:
        if _tokenizer_fallback_logged:
            return
        _tokenizer_fallback_logged = True
    log.warning(
        "Using the UTF-8 size fallback for chat context budgeting while the "
        "gpt-4o tokenizer is unavailable"
    )


def _fallback_text_token_count(text: str) -> int:
    if text == "":
        return 0
    return max(1, (len(text.encode("utf-8")) + 2) // 3)


def text_token_count(text: str) -> int:
    # TODO: select provider-specific tokenizers where a stable local encoder
    # exists. The shared estimate is not exact for every provider; the output
    # reserve reduces, but does not eliminate, that cross-tokenizer risk.
    encoding = _get_encoding()
    if encoding is None:
        _warn_tokenizer_fallback_once()
        return _fallback_text_token_count(text)
    return len(encoding.encode(text))


def truncate_text(
    text: str,
    token_budget: int,
    marker: str = "\n...[truncated]",
) -> str:
    if token_budget <= 0 or text == "":
        return ""

    encoding = _get_encoding()
    if encoding is None:
        _warn_tokenizer_fallback_once()
        if _fallback_text_token_count(text) <= token_budget:
            return text
        marker_bytes = marker.encode("utf-8")
        available_bytes = token_budget * 3 - len(marker_bytes)
        if available_bytes <= 0:
            return ""
        prefix = text.encode("utf-8")[:available_bytes].decode(
            "utf-8", errors="ignore"
        ).rstrip()
        return prefix + marker if prefix else ""

    encoded = encoding.encode(text)
    if len(encoded) <= token_budget:
        return text
    marker_tokens = len(encoding.encode(marker))
    prefix_size = token_budget - marker_tokens
    if prefix_size <= 0:
        return ""

    # BPE merges at the prefix/marker boundary can make the combined candidate
    # a few tokens larger than the sum of its parts. Correct a bounded number
    # of times; if the boundary remains pathological, return the marker alone.
    for _ in range(4):
        prefix = encoding.decode(encoded[:prefix_size]).rstrip()
        candidate = prefix + marker
        candidate_tokens = len(encoding.encode(candidate))
        if candidate_tokens <= token_budget:
            return candidate
        prefix_size -= max(1, candidate_tokens - token_budget)
        if prefix_size <= 0:
            break
    return marker if marker_tokens <= token_budget else ""


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


def _content_token_upper_bound(content: Any) -> int:
    """Return a cheap upper bound without invoking the tokenizer."""
    if content is None:
        return 0
    if isinstance(content, str):
        return len(content.encode("utf-8"))
    if isinstance(content, list):
        return sum(_content_token_upper_bound(item) for item in content)
    if isinstance(content, dict):
        content_type = content.get("type")
        if content_type in {"image", "image_url"} or "image_url" in content:
            return IMAGE_TOKEN_ESTIMATE
        if content_type == "text" and isinstance(content.get("text"), str):
            return len(content["text"].encode("utf-8"))
        return sum(
            _content_token_upper_bound(value)
            for key, value in content.items()
            if key != "type"
        )
    return len(str(content).encode("utf-8"))


def _message_token_upper_bound(message: dict) -> int:
    tokens = MESSAGE_OVERHEAD_TOKENS + _content_token_upper_bound(
        message.get("content")
    )
    for key in ("name", "tool_call_id", "tool_calls"):
        if key in message:
            tokens += _content_token_upper_bound(message[key])
    return tokens


def _truncate_text_message(message: dict, token_budget: int) -> dict | None:
    content = message.get("content")
    if not isinstance(content, str):
        return None

    fixed_fields = message.copy()
    fixed_fields["content"] = ""
    content_budget = token_budget - estimate_message_tokens(fixed_fields)
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


def _truncate_mandatory_message(
    message: dict,
    token_budget: int,
) -> dict | None:
    if isinstance(message.get("content"), str):
        return _truncate_text_message(message, token_budget)

    content = message.get("content")
    if not isinstance(content, list):
        return None
    text_parts = []
    omitted_non_text = False
    for item in content:
        if isinstance(item, str):
            text_parts.append(item)
        elif (
            isinstance(item, dict)
            and item.get("type") == "text"
            and isinstance(item.get("text"), str)
        ):
            text_parts.append(item["text"])
        else:
            omitted_non_text = True
    if omitted_non_text:
        text_parts.insert(0, _IMAGE_OMISSION_TEXT)
    elif not text_parts:
        text_parts.append(_IMAGE_OMISSION_TEXT)

    text_message = message.copy()
    text_message["content"] = "\n".join(text_parts)
    truncated = _truncate_text_message(text_message, token_budget)
    if truncated is None:
        return None
    if omitted_non_text and not truncated["content"].startswith(
        _IMAGE_OMISSION_TEXT
    ):
        return None
    truncated["content"] = [
        {"type": "text", "text": truncated["content"]}
    ]
    return truncated


def _partition_turns(
    messages: list[dict],
) -> tuple[list[list[dict]], list[dict]]:
    """Split complete user turns from the unfinished trailing sequence."""
    turns = []
    current_turn = []
    for message in messages:
        role = message.get("role")
        if role == "user" and any(
            item.get("role") in {"assistant", "tool"}
            for item in current_turn
        ):
            # A new user message cannot continue an unfinished tool-call
            # exchange. Discard that incomplete turn and start a fresh one.
            current_turn = [message]
            continue
        if not current_turn:
            if role != "user":
                continue
            current_turn = [message]
        else:
            current_turn.append(message)

        if role == "assistant" and not message.get("tool_calls"):
            turns.append(current_turn)
            current_turn = []
    return turns, current_turn


def _with_omission_notice(
    system_messages: list[dict],
    notice: str = CONTEXT_OMISSION_NOTICE,
    prepend: bool = False,
) -> list[dict]:
    updated = [message.copy() for message in system_messages]
    if updated and isinstance(updated[-1].get("content"), str):
        if prepend:
            updated[-1]["content"] = (
                notice.strip() + "\n\n" + updated[-1]["content"]
            )
        else:
            updated[-1]["content"] += notice
    else:
        updated.append({"role": "system", "content": notice.strip()})
    return updated


def _truncate_system_messages(
    system_messages: list[dict],
    token_budget: int,
) -> list[dict]:
    if token_budget <= 0:
        return []
    if sum(estimate_message_tokens(message) for message in system_messages) <= token_budget:
        return list(system_messages)

    text_parts = [
        message["content"]
        for message in system_messages
        if isinstance(message.get("content"), str)
    ]
    if not text_parts:
        return []
    combined = {"role": "system", "content": "\n\n".join(text_parts)}
    truncated = _truncate_text_message(combined, token_budget)
    protected_notice = SHORT_CONTEXT_OMISSION_NOTICE.strip()
    if (
        combined["content"].startswith(protected_notice)
        and (
            truncated is None
            or not truncated["content"].startswith(protected_notice)
        )
    ):
        notice_message = {"role": "system", "content": protected_notice}
        if estimate_message_tokens(notice_message) <= token_budget:
            return [notice_message]
    return [truncated] if truncated is not None else []


def _budget_chat_messages(
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
    if sum(_message_token_upper_bound(message) for message in messages) <= input_budget:
        return list(messages)

    token_cache = {}

    def message_tokens(message: dict) -> int:
        cache_key = id(message)
        cached = token_cache.get(cache_key)
        if cached is None or cached[0] is not message:
            cached = (message, estimate_message_tokens(message))
            # Retaining the object alongside its estimate prevents Python
            # from reusing its id for a later omission-notice candidate.
            token_cache[cache_key] = cached
        return cached[1]

    total_tokens = 0
    for message in messages:
        total_tokens += message_tokens(message)
        if total_tokens > input_budget:
            break
    else:
        # Budgeting is not a general history normalizer. Preserve unusual but
        # accepted provider sequences byte-for-byte until pruning is required.
        return list(messages)

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
        log.warning(
            "Reducing over-budget chat history to its newest message because "
            "it has no user request"
        )
        newest_message = messages[-1]
        if message_tokens(newest_message) <= input_budget:
            return [newest_message]
        truncated_message = _truncate_mandatory_message(
            newest_message,
            input_budget,
        )
        if truncated_message is not None:
            return [truncated_message]
        return [newest_message]

    latest_user = conversation[latest_user_index]
    trailing_messages = conversation[latest_user_index + 1:]
    if trailing_messages:
        log.warning(
            "Dropping %d trailing non-user chat messages while pruning; "
            "the newest user request must terminate an API chat request",
            len(trailing_messages),
        )
        trailing_messages = []
    preceding_messages = conversation[:latest_user_index]
    complete_turns, trailing_sequence = _partition_turns(preceding_messages)
    current_context = (
        trailing_sequence
        if all(message.get("role") == "user" for message in trailing_sequence)
        else []
    )
    base_mandatory_messages = [
        *system_messages,
        latest_user,
        *trailing_messages,
    ]
    base_mandatory_tokens = sum(
        message_tokens(message)
        for message in base_mandatory_messages
    )
    if base_mandatory_tokens > input_budget:
        candidate_system_messages = _with_omission_notice(
            system_messages,
            SHORT_CONTEXT_OMISSION_NOTICE,
            prepend=True,
        )
        non_user_mandatory_tokens = sum(
            message_tokens(message)
            for message in candidate_system_messages
        )
        truncated_latest_user = _truncate_mandatory_message(
            latest_user,
            max(0, input_budget - non_user_mandatory_tokens),
        )
        if truncated_latest_user is None:
            # When configured system instructions consume the whole model
            # window, reserve half the input budget for the actual request and
            # truncate both sides. Extremely tiny windows may still be unable
            # to fit even the per-message protocol overhead; those fall open.
            minimum_user_budget = MESSAGE_OVERHEAD_TOKENS + text_token_count(
                _IMAGE_OMISSION_TEXT + "\n" + TRUNCATION_MARKER
            )
            latest_user_tokens = message_tokens(latest_user)
            user_budget = min(
                input_budget,
                latest_user_tokens
                if latest_user_tokens <= input_budget
                else max(minimum_user_budget, input_budget // 2),
            )
            candidate_system_messages = _truncate_system_messages(
                candidate_system_messages,
                max(0, input_budget - user_budget),
            )
            remaining_for_user = input_budget - sum(
                message_tokens(message)
                for message in candidate_system_messages
            )
            truncated_latest_user = _truncate_mandatory_message(
                latest_user,
                remaining_for_user,
            )
            if truncated_latest_user is None:
                candidate_system_messages = []
                truncated_latest_user = _truncate_mandatory_message(
                    latest_user,
                    input_budget,
                )
        if truncated_latest_user is not None:
            log.warning(
                "Truncating mandatory system or user context because it "
                "requires %d estimated tokens for a %d-token input budget",
                base_mandatory_tokens,
                input_budget,
            )
            system_messages = candidate_system_messages
            latest_user = truncated_latest_user
        else:
            log.warning(
                "Mandatory chat context requires %d estimated tokens, "
                "exceeding the %d-token input budget; the system prompt "
                "leaves too little room to truncate the newest user request",
                base_mandatory_tokens,
                input_budget,
            )
    else:
        for notice in (
            CONTEXT_OMISSION_NOTICE,
            SHORT_CONTEXT_OMISSION_NOTICE,
        ):
            candidate_system_messages = _with_omission_notice(
                system_messages,
                notice,
            )
            candidate_mandatory_messages = [
                *candidate_system_messages,
                latest_user,
                *trailing_messages,
            ]
            if sum(
                message_tokens(message)
                for message in candidate_mandatory_messages
            ) <= input_budget:
                system_messages = candidate_system_messages
                break

    mandatory_messages = [*system_messages, latest_user, *trailing_messages]
    remaining_budget = max(
        0,
        input_budget
        - sum(
            message_tokens(message)
            for message in mandatory_messages
        ),
    )

    selected_context = []
    for message in reversed(current_context):
        context_tokens = message_tokens(message)
        if context_tokens <= remaining_budget:
            selected_context.append(message)
            remaining_budget -= context_tokens
            continue

        truncated = _truncate_text_message(message, remaining_budget)
        if truncated is not None:
            selected_context.append(truncated)
            remaining_budget -= message_tokens(truncated)
        continue
    selected_context.reverse()

    selected_turns = []
    for turn in reversed(complete_turns):
        turn_tokens = sum(message_tokens(message) for message in turn)
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


def budget_chat_messages(
    messages: list[dict],
    context_window: int,
) -> list[dict]:
    """Fail open if estimation encounters malformed data or runtime errors."""
    try:
        return _budget_chat_messages(messages, context_window)
    except Exception:
        log.exception(
            "Could not budget chat history; sending the original messages"
        )
        return list(messages)
