# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

from notebook_intelligence.chatbook_kernel.danger import (
    merge_danger_scans,
    parse_llm_danger_response,
    scan_generated_code,
    scan_generated_python,
)
from notebook_intelligence.chatbook_kernel.execution import (
    clamp_execution_mode,
    parse_execution_mode,
    should_execute_generated,
)
from notebook_intelligence.chatbook_generate import classify_generated_code_danger


def test_scan_flags_subprocess_and_shell():
    scan = scan_generated_python("import subprocess\nsubprocess.run(['ls'])\n")
    assert scan["level"] == "risky"
    assert any("subprocess" in reason for reason in scan["reasons"])

    magic = scan_generated_python("%pip install pandas\n")
    assert magic["level"] == "risky"
    assert any("pip" in reason for reason in magic["reasons"])

    bang = scan_generated_python("!rm -rf tmp\n")
    assert bang["level"] == "risky"


def test_scan_flags_writes_and_eval():
    write = scan_generated_python('open("out.csv", "w").write("a")\n')
    assert write["level"] == "risky"
    assert any("write" in reason.lower() for reason in write["reasons"])

    frame = scan_generated_python("df.to_csv('out.csv')\n")
    assert frame["level"] == "risky"

    dyn = scan_generated_python("eval('1')\n")
    assert dyn["level"] == "risky"


def test_scan_clean_analysis_code():
    scan = scan_generated_python("total = sum(values)\ntotal\n")
    assert scan == {"level": "clean", "reasons": []}


def test_scan_parse_failure_is_risky():
    scan = scan_generated_python("def (\n")
    assert scan["level"] == "risky"
    assert scan["reasons"]


def test_scan_flags_hidden_bidi_controls():
    # Trojan-Source style: the string literal carries a RIGHT-TO-LEFT OVERRIDE
    # so the line displays in a different order from how Python reads it.
    # Otherwise clean analysis code must still confirm, and the reason must
    # name the control so the confirm bar can show what is hidden.
    hidden = 'label = "total\u202e"  # sum\ntotal = sum(values)\n'
    scan = scan_generated_python(hidden)
    assert scan["level"] == "risky"
    assert scan["reasons"] == [
        "Hidden Unicode bidirectional controls "
        "(U+202E RIGHT-TO-LEFT OVERRIDE)"
    ]

    several = scan_generated_python("x = '\u2066a\u2069\u202e\u2066'\n")
    assert several["level"] == "risky"
    assert several["reasons"] == [
        "Hidden Unicode bidirectional controls (U+2066 LEFT-TO-RIGHT ISOLATE, "
        "U+2069 POP DIRECTIONAL ISOLATE, U+202E RIGHT-TO-LEFT OVERRIDE)"
    ]

    # Plain right-to-left text is not a control and stays clean.
    assert scan_generated_python('name = "\u05e9\u05dc\u05d5\u05dd"\n') == {
        "level": "clean",
        "reasons": [],
    }

    # Non-Python backends already fail closed; the hidden control is still
    # named alongside the missing-scanner reason.
    other = scan_generated_code("x <- '\u202e'\n", "r")
    assert other["level"] == "risky"
    assert other["reasons"][0] == "No static scanner for r code"
    assert other["reasons"][1].startswith("Hidden Unicode bidirectional controls")


def test_merge_and_llm_parse():
    static = {"level": "risky", "reasons": ["Import of os"]}
    llm_clean = parse_llm_danger_response('{"risky": false, "reasons": []}')
    assert llm_clean["level"] == "clean"
    merged = merge_danger_scans(static, llm_clean)
    assert merged["level"] == "risky"
    assert "Import of os" in merged["reasons"]

    llm_bad = parse_llm_danger_response("not json")
    assert llm_bad["level"] == "risky"
    assert parse_llm_danger_response('{"level": "risky"}')["level"] == "risky"

    no_reason = merge_danger_scans({"level": "risky", "reasons": []})
    assert no_reason["level"] == "risky"
    assert no_reason["reasons"]

    llm_raise = parse_llm_danger_response(
        'Sure.\n{"risky": true, "reasons": ["network"]}\n'
    )
    assert llm_raise["level"] == "risky"
    assert llm_raise["reasons"] == ["network"]


def test_execution_mode_clamp_and_run_policy():
    assert parse_execution_mode("nope") == "always-confirm"
    assert parse_execution_mode("generate-only") == "always-confirm"
    assert clamp_execution_mode("auto-run", "generate-only") == "always-confirm"
    assert clamp_execution_mode("auto-run", "always-confirm") == "always-confirm"
    from notebook_intelligence.chatbook_kernel.execution import (
        effective_execution_mode,
    )

    assert (
        effective_execution_mode("auto-run", "auto-run", "always-confirm")
        == "always-confirm"
    )
    assert (
        effective_execution_mode("auto-run", "always-confirm", "auto-run")
        == "always-confirm"
    )
    assert should_execute_generated("auto-run", "risky") is True
    assert should_execute_generated("confirm-if-risky", "clean") is True
    assert should_execute_generated("confirm-if-risky", "risky") is False
    assert should_execute_generated("always-confirm", "clean") is False


def test_llm_classifier_uses_json_only():
    class Model:
        def completions(self, messages, tools=None, response=None, cancel_token=None, options=None):
            assert "untrusted" not in messages[1]["content"]
            response.stream({
                "choices": [{"delta": {"content": '{"risky": true, "reasons": ["shell"]}'}}]
            })
            response.finish()

    class Manager:
        chat_model = Model()

    scan = classify_generated_code_danger(Manager(), "print(1)")
    assert scan["level"] == "risky"
    assert scan["reasons"] == ["shell"]
