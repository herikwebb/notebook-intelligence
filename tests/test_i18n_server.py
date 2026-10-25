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
    monkeypatch.setattr(i18n, "_installed_language_packs", lambda: frozenset({"en"}))
    i18n._bundle.cache_clear()
    assert i18n.load("de_DE").__("Rule not found") == "Rule not found"
    monkeypatch.setattr(
        i18n, "_installed_language_packs", lambda: frozenset({"en", "de_DE"})
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
