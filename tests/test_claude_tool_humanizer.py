"""Regression tests for the Claude-mode tool-call surfacing helpers
(see `notebook_intelligence/claude.py`).

Three pure surfaces are pinned here:

1. `humanize_claude_tool_name` — the known-tool map, the
   `mcp__<server>__<tool>` wrapper-stripping, and the unknown-tool
   sentence-case fallback. Failures turn into raw kebab-case identifiers
   on the tool-call cards.
2. `claude_tool_kind` — the read/edit/execute/other categorization that
   picks each card's icon, including the whole-token heuristic for
   unfamiliar MCP tools.
3. `ToolCallData` — the dataclass shape and defaults streamed to the
   frontend.

The worker loop's tool-block dispatch (which calls these helpers and
emits `ToolCallData`) lives inside a deeply-nested closure and is covered
at the integration level rather than here.
"""

from notebook_intelligence.api import ResponseStreamDataType, ToolCallData
from notebook_intelligence.claude import claude_tool_kind, humanize_claude_tool_name


class TestHumanizeClaudeToolName:
    def test_known_nbi_tool_maps_to_friendly_label(self):
        assert humanize_claude_tool_name("run-cell") == "Running cell"
        assert humanize_claude_tool_name("add-code-cell") == "Adding code cell"
        assert humanize_claude_tool_name("save-notebook") == "Saving notebook"

    def test_known_claude_builtin_maps_to_friendly_label(self):
        # Claude's built-ins keep CamelCase names through the SDK; the
        # map covers them so the indicator says "Running shell command"
        # not "Bash".
        assert humanize_claude_tool_name("Bash") == "Running shell command"
        assert humanize_claude_tool_name("Read") == "Reading file"
        assert humanize_claude_tool_name("Edit") == "Editing file"

    def test_mcp_wrapper_is_stripped_when_inner_is_known(self):
        # MCP server tools surface to the agent as
        # `mcp__<server>__<tool>`. The label map keys are the inner
        # names; stripping the wrapper before lookup means NBI's own
        # MCP-routed tools still resolve.
        assert (
            humanize_claude_tool_name("mcp__nbi__add-code-cell")
            == "Adding code cell"
        )

    def test_mcp_wrapper_strip_falls_back_when_inner_is_unknown(self):
        # An unknown inner name still gets the sentence-case treatment
        # (not the bare mcp__ prefix), so unknown MCP servers surface
        # readably.
        result = humanize_claude_tool_name("mcp__custom__do-something")
        assert result == "Do something"

    def test_unknown_kebab_name_falls_back_to_sentence_case(self):
        assert (
            humanize_claude_tool_name("future-builtin-tool")
            == "Future builtin tool"
        )

    def test_unknown_snake_name_falls_back_to_sentence_case(self):
        assert humanize_claude_tool_name("future_tool") == "Future tool"

    def test_empty_string_returns_input_unchanged(self):
        # Pathological: SDK shouldn't yield an empty name, but if it
        # does we should hand back the raw value rather than producing
        # the empty string in the indicator.
        assert humanize_claude_tool_name("") == ""

    def test_camelcase_unknown_is_returned_unchanged(self):
        # Unknown CamelCase has no separator to humanize; preserving the
        # original is the least surprising fallback.
        assert humanize_claude_tool_name("Foo") == "Foo"


class TestClaudeToolKind:
    def test_known_tools_map_to_their_kind(self):
        assert claude_tool_kind("Read") == "read"
        assert claude_tool_kind("get-cell-output") == "read"
        assert claude_tool_kind("Edit") == "edit"
        assert claude_tool_kind("add-code-cell") == "edit"
        assert claude_tool_kind("Bash") == "execute"
        assert claude_tool_kind("run-cell") == "execute"
        assert claude_tool_kind("Task") == "other"

    def test_mcp_wrapper_is_unwrapped_for_known_inner(self):
        assert claude_tool_kind("mcp__nbi__run-cell") == "execute"

    def test_heuristic_categorizes_unknown_tools_by_verb_token(self):
        assert claude_tool_kind("mcp__srv__execute_query") == "execute"
        assert claude_tool_kind("create_dashboard") == "edit"
        assert claude_tool_kind("list_tables") == "read"

    def test_heuristic_matches_whole_tokens_not_substrings(self):
        # "widget" must not read as "get"; "command" must not read as "and".
        assert claude_tool_kind("frobnicate_widget") == "other"

    def test_heuristic_precedence_is_execute_then_edit_then_read(self):
        # A name carrying tokens from multiple buckets resolves by the
        # execute -> edit -> read order, so reordering the checks would
        # change these results.
        assert claude_tool_kind("save-and-run-cell") == "execute"
        assert claude_tool_kind("get-and-delete") == "edit"

    def test_unrecognized_tool_falls_back_to_other(self):
        assert claude_tool_kind("frobnicate") == "other"
        assert claude_tool_kind("") == "other"


class TestToolCallData:
    def test_data_type_is_tool_call(self):
        data = ToolCallData(id="t1", title="Reading file", kind="read", status="in_progress")
        assert data.data_type == ResponseStreamDataType.ToolCall

    def test_defaults_are_in_progress_other(self):
        data = ToolCallData()
        assert data.kind == "other"
        assert data.status == "in_progress"
