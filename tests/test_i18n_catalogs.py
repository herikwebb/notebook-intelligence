"""The wheel build hook compiles each committed .po catalog into the JSON
bundle JupyterLab's frontend loads."""

import importlib.util
import json
import re
import sys
import types
from pathlib import Path

import polib
import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture
def hatch_build(monkeypatch):
    # The hook subclasses hatchling's interface, which only build
    # environments have; compiling catalogs does not touch it.
    try:
        import hatchling.builders.hooks.plugin.interface  # noqa: F401
    except ImportError:
        interface = types.ModuleType("hatchling.builders.hooks.plugin.interface")
        interface.BuildHookInterface = object
        for name in (
            "hatchling",
            "hatchling.builders",
            "hatchling.builders.hooks",
            "hatchling.builders.hooks.plugin",
        ):
            if name not in sys.modules:
                monkeypatch.setitem(sys.modules, name, types.ModuleType(name))
        monkeypatch.setitem(sys.modules, interface.__name__, interface)
    spec = importlib.util.spec_from_file_location("hatch_build", ROOT / "hatch_build.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_tour_contexts_match_the_frontend():
    """scripts/i18n.py extracts the tour's strings under contexts that
    src/tour/tour-text.ts must look them up with; a mismatch would leave the
    whole tour English with no error."""
    spec = importlib.util.spec_from_file_location(
        "nbi_i18n_script", ROOT / "scripts" / "i18n.py"
    )
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    tour_text = (ROOT / "src" / "tour" / "tour-text.ts").read_text(encoding="utf-8")
    template_branch = tour_text.index("includes('{launchers}')")
    template_context = tour_text.index(f'"{script.TOUR_TEMPLATE_CONTEXT}"')
    plain_context = tour_text.index(f"'{script.TOUR_CONTEXT}'")
    # The {launchers} branch looks up the template context; the other the
    # plain one.
    assert template_branch < template_context < plain_context
