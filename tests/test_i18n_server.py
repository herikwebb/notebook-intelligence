"""The server translates the text it writes for the user from the same
catalogs the frontend uses, in the language each request asks for."""

import types

import polib
import pytest

from notebook_intelligence import i18n


@pytest.fixture
def german(tmp_path, monkeypatch):
    po = polib.POFile()
    po.metadata = {
        "Language": "de_DE",
        "Plural-Forms": "nplurals=2; plural=(n != 1);",
        "Content-Type": "text/plain; charset=utf-8",
    }
    po.append(polib.POEntry(msgid="Rule not found", msgstr="Regel nicht gefunden"))
    po.append(
        polib.POEntry(
            msgctxt="approval button", msgid="Approve", msgstr="Genehmigen"
        )
    )
    po.append(
        polib.POEntry(
            msgid="Skill '%1' not found in %2 scope",
            msgstr="Skill '%1' im Bereich %2 nicht gefunden",
        )
    )
    po.append(
        polib.POEntry(
            msgid="%1 model available.",
            msgid_plural="%1 models available.",
            msgstr_plural={0: "%1 Modell verfügbar.", 1: "%1 Modelle verfügbar."},
        )
    )
    directory = tmp_path / "de_DE" / "LC_MESSAGES"
    directory.mkdir(parents=True)
    po.save_as_mofile(str(directory / f"{i18n.DOMAIN}.mo"))
    monkeypatch.setattr(i18n, "LOCALE_DIR", tmp_path)
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: None)
    i18n._bundle.cache_clear()
    yield
    i18n._bundle.cache_clear()


def test_english_output_is_the_msgid():
    trans = i18n.english()
    assert trans.__("Skill '%1' not found in %2 scope", "x", "user") == (
        "Skill 'x' not found in user scope"
    )
    assert trans._n("%1 model available.", "%1 models available.", 3) == (
        "3 models available."
    )
    assert trans._p("approval button", "Approve") == "Approve"


def test_placeholders_follow_the_frontend():
    trans = i18n.english()
    # %% is a literal percent sign; a placeholder without an argument stays.
    assert trans.__("%1%% done, %2", 50) == "50% done, %2"
    # An argument is inserted as is, percent signs and all.
    assert trans.__("Error: %1", "100%% of %1") == "Error: 100%% of %1"
    assert trans._n("%1 file in %2", "%1 files in %2", 1, "src") == "1 file in src"


def test_translates_from_the_compiled_catalog(german):
    trans = i18n.load("de_DE")
    assert trans.__("Rule not found") == "Regel nicht gefunden"
    assert trans._p("approval button", "Approve") == "Genehmigen"
    assert trans._p("question card button", "Approve") == "Approve"
    assert trans.__("Skill '%1' not found in %2 scope", "x", "user") == (
        "Skill 'x' im Bereich user nicht gefunden"
    )
    assert trans._n("%1 model available.", "%1 models available.", 1) == (
        "1 Modell verfügbar."
    )
    assert trans.__("Not in the catalog") == "Not in the catalog"


def test_catalogs_are_matched_like_the_frontends(german, tmp_path):
    """jupyterlab_server matches the folder name exactly, ignoring case, so a
    de catalog does not serve de_AT; the server must not either, or it would
    translate what the frontend shows in English."""
    assert i18n.load("de_de").__("Rule not found") == "Regel nicht gefunden"
    (tmp_path / "de_DE").rename(tmp_path / "de")
    i18n._bundle.cache_clear()
    assert i18n.load("de_AT").__("Rule not found") == "Rule not found"
    assert i18n.load("de").__("Rule not found") == "Regel nicht gefunden"


def test_no_translation_without_a_jupyterlab_language_pack(german, monkeypatch):
    """jupyterlab_server serves the frontend no translations for a locale
    without a language pack, so the server must not translate either."""
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: {"en": "English"})
    i18n._bundle.cache_clear()
    assert i18n.load("de_DE").__("Rule not found") == "Rule not found"
    monkeypatch.setattr(
        i18n,
        "_installed_language_packs",
        lambda: {"en": "English", "de_DE": "German (Germany)"},
    )
    i18n._bundle.cache_clear()
    assert i18n.load("de-DE").__("Rule not found") == "Regel nicht gefunden"


def test_toolset_descriptions_match_what_the_model_sees():
    """The picker's English description is a copy of Toolset.description."""
    from notebook_intelligence.built_in_toolsets import (
        built_in_toolsets,
        toolset_description,
    )

    for toolset in built_in_toolsets.values():
        assert toolset_description(i18n.english(), toolset) == toolset.description


def test_an_unreadable_catalog_falls_back_to_english(german, tmp_path):
    mo = tmp_path / "de_DE" / "LC_MESSAGES" / f"{i18n.DOMAIN}.mo"
    mo.write_bytes(b"not a catalog")
    assert i18n.load("de_DE").__("Rule not found") == "Rule not found"


@pytest.mark.parametrize(
    "value, expected",
    [
        ("de_DE", "de_DE"),
        ("de-DE", "de_DE"),
        ("zh_Hant_TW", "zh_Hant_TW"),
        ("en", None),
        ("default", None),
        ("", None),
        (None, None),
        ("../../etc", None),
        ("de_DE; rm -rf", None),
    ],
)
def test_normalize_locale(value, expected):
    assert i18n.normalize_locale(value) == expected


def _handler(query=None):
    return types.SimpleNamespace(
        get_query_argument=lambda name, default=None: (query or {}).get(
            name, default
        ),
    )


def test_request_bundle_reads_the_query(german):
    assert i18n.request_bundle(_handler({"nbi_locale": "de-DE"})).locale == "de_DE"
    assert i18n.request_bundle(_handler()).locale == "en"
    assert i18n.request_bundle(object()).locale == "en"


def test_every_admin_gate_message_is_translatable():
    """An admin-gate message missing from the table would stay English with
    no extraction error."""
    from notebook_intelligence import extension

    def subclasses(cls):
        for sub in cls.__subclasses__():
            yield sub
            yield from subclasses(sub)

    listed = extension._policy_messages(i18n.english())
    messages = {
        handler.policy_disabled_message
        for handler in subclasses(extension.PolicyGatedHandler)
    } | {extension.PolicyGatedHandler.policy_disabled_message,
         extension.CHATBOOK_DISABLED_MESSAGE}
    assert messages <= set(listed)
    # English maps to itself, so the table cannot drift from the handlers.
    assert all(key == value for key, value in listed.items())


PACKS = {
    "en": "English",
    "de_DE": "German (Germany)",
    "pt_BR": "Portuguese (Brazil)",
    "ach_UG": "Acoli (Uganda)",
}


@pytest.mark.parametrize(
    "locale, expected",
    [
        ("de_DE", "German (Germany)"),
        ("de-DE", "German (Germany)"),
        ("pt_BR", "Portuguese (Brazil)"),
        # No pack: JupyterLab is shown in English, so replies stay as is.
        ("fr_FR", None),
        # The translators' pseudo-language is not a language to reply in.
        ("ach_UG", None),
        ("en", None),
        (None, None),
        ("not a locale", None),
    ],
)
def test_reply_language_is_the_language_packs_name(monkeypatch, locale, expected):
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: PACKS)
    assert i18n.reply_language(locale) == expected


def test_reply_language_when_the_packs_cannot_be_listed(monkeypatch):
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: None)
    assert i18n.reply_language("sv_SE") == "the language of locale sv_SE"


def test_a_failed_pack_listing_is_unknown_not_empty(monkeypatch):
    """jupyterlab_server reports no packs at all when one fails to load;
    that must not switch the feature off for the packs that work."""
    import jupyterlab_server.translation_utils as utils

    monkeypatch.setattr(utils, "get_language_packs", lambda: ({}, "a pack failed to load"))
    i18n._installed_language_packs.cache_clear()
    try:
        assert i18n._installed_language_packs() is None
    finally:
        i18n._installed_language_packs.cache_clear()


def test_reply_language_instruction():
    assert i18n.reply_language_instruction(None) == ""
    instruction = i18n.reply_language_instruction("German")
    assert instruction.startswith("Reply in German")
    assert "Leave code, identifiers" in instruction
    assert i18n.with_reply_language("Be brief.", None) == "Be brief."
    assert i18n.with_reply_language("Be brief.", "German") == (
        "Be brief.\n\n" + instruction
    )
    assert i18n.with_reply_language("", "German") == instruction


def test_request_reply_language_needs_the_setting(monkeypatch):
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: PACKS)
    handler = _handler({"nbi_locale": "de_DE"})
    assert i18n.request_reply_language(handler, True) == "German (Germany)"
    assert i18n.request_reply_language(handler, False) is None
    # Anything but True (a mocked or malformed config value) leaves it off.
    assert i18n.request_reply_language(handler, "yes") is None


def test_chatbook_descriptions_follow_the_reply_language():
    from notebook_intelligence.chatbook_generate import cell_summary_instructions

    default = cell_summary_instructions("python")
    assert "Use English unless" in default
    german = cell_summary_instructions("python", "German")
    assert "Write the prompt in German" in german
    assert "Use English unless" not in german


def test_tool_using_participants_get_the_reply_language():
    """handle_chat_request_with_tools is where agent mode, @mcp and extension
    participants build their system prompt, so one place covers them all."""
    import asyncio
    import types
    from unittest.mock import Mock

    from notebook_intelligence.api import ChatParticipant, ChatRequest

    def run(options, reply_language):
        chat_model = Mock()
        request = ChatRequest(
            host=Mock(chat_model=chat_model),
            chat_history=[{"role": "user", "content": "Hallo"}],
            cancel_token=Mock(),
            reply_language=reply_language,
        )
        participant = types.SimpleNamespace(tools=[])
        asyncio.run(
            ChatParticipant.handle_chat_request_with_tools(
                participant, request, Mock(), options
            )
        )
        return chat_model.completions.call_args[0][0]

    assert run({}, None)[0] == {"role": "user", "content": "Hallo"}
    assert run({"system_prompt": "Be brief."}, None)[0]["content"] == "Be brief."
    german = run({}, "German (Germany)")[0]
    assert german["role"] == "system"
    assert german["content"].startswith("Reply in German (Germany),")
    combined = run({"system_prompt": "Be brief."}, "German (Germany)")[0]
    assert combined["content"].startswith("Be brief.\n\nReply in German (Germany),")


def test_a_pack_babel_cannot_name_is_named_by_its_code(monkeypatch):
    """jupyterlab_server reports the display locale ("En") for no_NO."""
    import jupyterlab_server.translation_utils as utils

    monkeypatch.setattr(
        utils,
        "get_language_packs",
        lambda: (
            {
                "en": {"displayName": "English"},
                "no_NO": {"displayName": "En"},
                "de_DE": {"displayName": "German (Germany)"},
            },
            "The following locales are invalid: ['sr_SP']!",
        ),
    )
    i18n._installed_language_packs.cache_clear()
    try:
        # The warning does not discard the valid list.
        assert i18n._installed_language_packs()["de_DE"] == "German (Germany)"
        assert i18n.reply_language("no_NO") == "the language of locale no_NO"
        assert i18n.reply_language("fr_FR") is None
    finally:
        i18n._installed_language_packs.cache_clear()


def test_session_previews_leave_out_the_instruction():
    instruction = i18n.reply_language_instruction("German (Germany)")
    assert i18n.without_reply_instruction("Hallo\n\n" + instruction) == "Hallo"
    # A title the agent cut short inside the instruction's second sentence.
    assert i18n.without_reply_instruction("Hallo " + instruction[:75] + "...") == "Hallo"
    assert i18n.without_reply_instruction("Please reply in kind.") == (
        "Please reply in kind."
    )
