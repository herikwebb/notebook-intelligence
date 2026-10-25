"""The wheel build hook compiles each committed .po catalog into the JSON
bundle JupyterLab's frontend loads."""

import importlib.util
import json
import re
import sys
from pathlib import Path

import polib
import pytest

ROOT = Path(__file__).resolve().parent.parent


def _load_hatch_build():
    spec = importlib.util.spec_from_file_location("hatch_build", ROOT / "hatch_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def hatch_build():
    return _load_hatch_build()


def test_catalogs_compile_without_hatchling(monkeypatch):
    """`jlpm i18n:compile` imports hatch_build.py in a dev environment, which
    has no hatchling: only the build backend's isolated environment does."""
    for name in list(sys.modules):
        if name == "hatchling" or name.startswith("hatchling."):
            monkeypatch.delitem(sys.modules, name)
    monkeypatch.setitem(sys.modules, "hatchling", None)
    module = _load_hatch_build()
    assert callable(module.compile_catalogs)


HEADERS = {
    "Project-Id-Version": "notebook_intelligence",
    "Language": "de_DE",
    "Plural-Forms": "nplurals=2; plural=(n != 1);",
    "Content-Type": "text/plain; charset=utf-8",
}


def _write_catalog(root: Path, headers=HEADERS) -> Path:
    po = polib.POFile()
    po.metadata = dict(headers)
    po.append(polib.POEntry(msgid="Close", msgstr="Schließen"))
    po.append(polib.POEntry(msgctxt="schema", msgid="Settings", msgstr="Einstellungen"))
    po.append(
        polib.POEntry(
            msgid="%1 file",
            msgid_plural="%1 files",
            msgstr_plural={0: "%1 Datei", 1: "%1 Dateien"},
        )
    )
    po.append(polib.POEntry(msgid="Untranslated", msgstr=""))
    fuzzy = polib.POEntry(msgid="Unreviewed", msgstr="Ungeprüft")
    fuzzy.flags.append("fuzzy")
    po.append(fuzzy)
    path = root / "notebook_intelligence" / "locale" / "de_DE" / "LC_MESSAGES"
    path.mkdir(parents=True)
    po_path = path / "notebook_intelligence.po"
    po.save(str(po_path))
    return po_path


def test_json_bundle_matches_jupyterlab_layout(tmp_path, hatch_build):
    po_path = _write_catalog(tmp_path)
    compiled = hatch_build.compile_catalogs(tmp_path, "6.3.0")
    assert compiled == [po_path.with_suffix(".json")]

    bundle = json.loads(po_path.with_suffix(".json").read_text(encoding="utf-8"))
    assert bundle[""] == {
        "domain": "notebook_intelligence",
        "version": "6.3.0",
        "language": "de-DE",
        "plural_forms": "nplurals=2; plural=(n != 1);",
    }
    assert bundle["Close"] == ["Schließen"]
    assert bundle["schema\x04Settings"] == ["Einstellungen"]
    assert bundle["%1 file"] == ["%1 Datei", "%1 Dateien"]
    # Missing and unreviewed strings fall back to English in the frontend.
    assert "Untranslated" not in bundle
    assert "Unreviewed" not in bundle


@pytest.mark.parametrize("missing", ["Language", "Plural-Forms"])
def test_catalog_without_required_headers_fails_the_build(
    tmp_path, hatch_build, missing
):
    """@jupyterlab/translation throws on a bundle without these headers, which
    would stop NBI activating in that language."""
    headers = {k: v for k, v in HEADERS.items() if k != missing}
    _write_catalog(tmp_path, headers)
    with pytest.raises(ValueError, match="Language and Plural-Forms"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def test_no_catalogs_compiles_nothing(tmp_path, hatch_build):
    assert hatch_build.compile_catalogs(tmp_path, "6.3.0") == []


def test_invalid_plural_forms_fails_the_build(tmp_path, hatch_build):
    """Gettext checks Plural-Forms only when a plural is first looked up, so a
    typo would break that call site instead of the build."""
    headers = dict(HEADERS, **{"Plural-Forms": "nplurals=2; plural=n!=1 ? 1 : 0 x"})
    _write_catalog(tmp_path, headers)
    with pytest.raises(ValueError, match="invalid Plural-Forms"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def test_bundle_of_a_removed_catalog_is_deleted(tmp_path, hatch_build):
    po_path = _write_catalog(tmp_path)
    hatch_build.compile_catalogs(tmp_path, "6.3.0")
    po_path.unlink()
    assert hatch_build.compile_catalogs(tmp_path, "6.3.0") == []
    assert not po_path.with_suffix(".json").exists()
    assert not po_path.with_suffix(".mo").exists()


def test_server_catalog_is_compiled_beside_the_bundle(tmp_path, hatch_build):
    """notebook_intelligence/i18n.py reads the .mo with Python's gettext."""
    import gettext

    po_path = _write_catalog(tmp_path)
    hatch_build.compile_catalogs(tmp_path, "6.3.0")
    with po_path.with_suffix(".mo").open("rb") as mo:
        catalog = gettext.GNUTranslations(mo)
    assert catalog.gettext("Close") == "Schließen"
    assert catalog.pgettext("schema", "Settings") == "Einstellungen"
    assert catalog.ngettext("%1 file", "%1 files", 2) == "%1 Dateien"
    # As in the frontend, unreviewed strings stay English.
    assert catalog.gettext("Unreviewed") == "Unreviewed"


@pytest.mark.parametrize(
    "msgstr",
    ["Datei geöffnet", "%1 geöffnet in %2"],
    ids=["missing", "extra"],
)
def test_placeholder_mismatch_fails_the_build(tmp_path, hatch_build, msgstr):
    po_path = _write_catalog(tmp_path)
    po = polib.pofile(str(po_path))
    po.append(polib.POEntry(msgid="%1 opened", msgstr=msgstr))
    po.save(str(po_path))
    with pytest.raises(ValueError, match="placeholders"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def test_plural_forms_may_leave_out_the_count(tmp_path, hatch_build):
    po_path = _write_catalog(tmp_path)
    po = polib.pofile(str(po_path))
    po.append(
        polib.POEntry(
            msgid="%1 file in %2",
            msgid_plural="%1 files in %2",
            msgstr_plural={0: "eine Datei in %2", 1: "%1 Dateien in %2"},
        )
    )
    po.append(polib.POEntry(msgid="100%% done", msgstr="100%% fertig"))
    po.save(str(po_path))
    hatch_build.compile_catalogs(tmp_path, "6.3.0")



def test_frontend_labels_every_built_in_toolset():
    """src/builtin-toolset-labels.ts translates the built-in toolsets by id;
    the frontend's id list must match the server's, or a new toolset shows
    its English name in every language."""
    # The i18n CI job does not install NBI; the main build job runs this.
    api = pytest.importorskip("notebook_intelligence.api")
    BuiltinToolset = api.BuiltinToolset

    tokens = (ROOT / "src" / "tokens.ts").read_text(encoding="utf-8")
    enum_body = tokens.split("export enum BuiltinToolsetType {", 1)[1].split("}", 1)[0]
    frontend = set(re.findall(r"=\s*'([^']+)'", enum_body))
    assert frontend == {toolset.value for toolset in BuiltinToolset}


def test_template_token_must_survive_translation(tmp_path, hatch_build):
    po_path = _write_catalog(tmp_path)
    po = polib.pofile(str(po_path))
    po.append(
        polib.POEntry(
            msgid="Tiles for {launchers}.",
            msgstr="Kacheln für die Werkzeuge.",
        )
    )
    po.save(str(po_path))
    with pytest.raises(ValueError, match="placeholders"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def _script():
    spec = importlib.util.spec_from_file_location(
        "nbi_i18n_script", ROOT / "scripts" / "i18n.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    return script


def test_tour_contexts_match_the_frontend():
    """scripts/i18n.py extracts the tour's strings under contexts that
    src/tour/tour-text.ts must look them up with; a mismatch would leave the
    whole tour English with no error."""
    script = _script()
    tour_text = (ROOT / "src" / "tour" / "tour-text.ts").read_text(encoding="utf-8")
    template_branch = tour_text.index("includes('{launchers}')")
    template_context = tour_text.index(f'"{script.TOUR_TEMPLATE_CONTEXT}"')
    plain_context = tour_text.index(f"'{script.TOUR_CONTEXT}'")
    # The {launchers} branch looks up the template context; the other the
    # plain one.
    assert template_branch < template_context < plain_context


def test_server_strings_are_extracted(tmp_path):
    (tmp_path / "server.py").write_text(
        "def f(trans, n, name):\n"
        "    trans.__('Rule not found')\n"
        "    trans._p('approval button', 'Approve')\n"
        "    trans._n('%1 model', '%1 models', n)\n"
        "    trans._np('ctx', '%1 issue', '%1 issues', n)\n"
        "    other.__('Not a bundle')\n",
        encoding="utf-8",
    )
    script = _script()
    script.ROOT = tmp_path
    items = script.extract_py_strings(tmp_path)
    assert [(i["msgctxt"], i["msgid"], i["msgid_plural"]) for i in items] == [
        (None, "Rule not found", None),
        ("approval button", "Approve", None),
        (None, "%1 model", "%1 models"),
        ("ctx", "%1 issue", "%1 issues"),
    ]


def test_a_non_literal_server_msgid_fails_extraction(tmp_path):
    """A msgid built at runtime can never be in the catalog."""
    (tmp_path / "server.py").write_text(
        "def f(trans, name):\n    trans.__(f'Skill {name} not found')\n",
        encoding="utf-8",
    )
    script = _script()
    script.ROOT = tmp_path
    with pytest.raises(SystemExit, match="string literals"):
        script.extract_py_strings(tmp_path)


def test_a_bundle_reached_through_an_attribute_fails_extraction(tmp_path):
    """`self.trans.__(...)` would be skipped, and its string never translated."""
    (tmp_path / "server.py").write_text(
        "def f(self):\n    self.trans.__('Shell')\n", encoding="utf-8"
    )
    script = _script()
    script.ROOT = tmp_path
    with pytest.raises(SystemExit, match="local first"):
        script.extract_py_strings(tmp_path)



def test_every_committed_catalog_builds(tmp_path, hatch_build):
    """The shipped catalogs pass the build's checks (headers, plural forms,
    placeholders), so a bad edit fails here rather than at release."""
    import shutil

    source = ROOT / "notebook_intelligence" / "locale"
    catalogs = sorted(source.glob("*/LC_MESSAGES/notebook_intelligence.po"))
    if not catalogs:
        pytest.skip("no catalogs committed")
    for po_path in catalogs:
        target = tmp_path / po_path.relative_to(ROOT)
        target.parent.mkdir(parents=True)
        shutil.copy(po_path, target)
    compiled = hatch_build.compile_catalogs(tmp_path, "0.0.0")
    assert len(compiled) == len(catalogs)


def test_language_header_must_name_the_folder(tmp_path, hatch_build):
    """The frontend keys the bundle by JupyterLab's locale id, the folder
    name; Babel's `init` writes zh_Hans_CN for zh_CN, which it never matches."""
    _write_catalog(tmp_path, dict(HEADERS, Language="de_Latn_DE"))
    with pytest.raises(ValueError, match="loads it as 'de_DE'"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def test_update_names_the_folder_in_the_language_header(tmp_path):
    """`jlpm i18n:update -l zh_CN` must leave a catalog the build accepts."""
    po_path = _write_catalog(tmp_path, dict(HEADERS, Language="de_Latn_DE"))
    script = _script()
    script._fix_headers(po_path, "de_DE", {})
    assert polib.pofile(str(po_path)).metadata["Language"] == "de_DE"


def test_update_restores_plural_forms_babel_dropped(tmp_path):
    headers = {k: v for k, v in HEADERS.items() if k != "Plural-Forms"}
    po_path = _write_catalog(tmp_path, headers)
    script = _script()
    script._fix_headers(po_path, "de_DE", {"Plural-Forms": HEADERS["Plural-Forms"]})
    assert polib.pofile(str(po_path)).metadata["Plural-Forms"] == HEADERS["Plural-Forms"]


def test_a_plural_entry_needs_every_form(tmp_path, hatch_build):
    """Russian has three plural forms; an entry with two would show form 0 in
    the frontend and English on the server for the third."""
    po = polib.POFile()
    po.metadata = dict(
        HEADERS,
        Language="ru_RU",
        **{
            "Plural-Forms": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : "
            "n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
        },
    )
    po.append(
        polib.POEntry(
            msgid="%1 file",
            msgid_plural="%1 files",
            msgstr_plural={0: "%1 файл", 1: "%1 файла"},
        )
    )
    path = tmp_path / "notebook_intelligence" / "locale" / "ru_RU" / "LC_MESSAGES"
    path.mkdir(parents=True)
    po.save(str(path / "notebook_intelligence.po"))
    with pytest.raises(ValueError, match="needs 3 plural forms"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")


def test_a_partly_translated_plural_is_refused(tmp_path, hatch_build):
    """Editors write every msgstr[n] slot; one left empty must fail the build
    rather than drop the entry silently."""
    po = polib.POFile()
    po.metadata = dict(
        HEADERS,
        Language="ru_RU",
        **{
            "Plural-Forms": "nplurals=3; plural=(n%10==1 && n%100!=11 ? 0 : "
            "n%10>=2 && n%10<=4 && (n%100<10 || n%100>=20) ? 1 : 2);"
        },
    )
    po.append(
        polib.POEntry(
            msgid="%1 file",
            msgid_plural="%1 files",
            msgstr_plural={0: "%1 файл", 1: "%1 файла", 2: ""},
        )
    )
    path = tmp_path / "notebook_intelligence" / "locale" / "ru_RU" / "LC_MESSAGES"
    path.mkdir(parents=True)
    po.save(str(path / "notebook_intelligence.po"))
    with pytest.raises(ValueError, match="needs 3 plural forms"):
        hatch_build.compile_catalogs(tmp_path, "6.3.0")

