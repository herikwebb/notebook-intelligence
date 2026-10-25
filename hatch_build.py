"""Compile Notebook Intelligence's translation catalogs when building a wheel.

Only the ``.po`` sources are committed. Each one is compiled next to itself
into the ``.json`` bundle JupyterLab's frontend loads, which
``jupyterlab_server`` finds through the ``jupyterlab.locale`` entry point, and
the ``.mo`` file ``notebook_intelligence/i18n.py`` reads for the server's own
text. The
layout mirrors ``jupyterlab_translate.converters``, which this does not import
so the build only needs ``polib``.
"""

import json
import re
from pathlib import Path

import polib
from hatchling.builders.hooks.plugin.interface import BuildHookInterface

DOMAIN = "notebook_intelligence"
# The check @jupyterlab/translation's Gettext applies when it first resolves a
# plural; failing it there breaks the call site, so fail the build instead.
_PLURAL_FORMS = re.compile(
    r"^\s*nplurals\s*=\s*[0-9]+\s*;\s*plural\s*=\s*(?:\s|[-?|&=!<>+*/%:;n0-9_()])+$"
)


# %1, %2 ... for trans.__ arguments, and {name} for the template tokens the
# tour's launcher step fills in ({launchers}).
_PLACEHOLDER = re.compile(r"%(\d+)|(\{[a-z_]+\})")


def _placeholders(text: str) -> set:
    # Gettext.strfmt reads %% as a literal percent sign, not a placeholder.
    return {
        number or token
        for number, token in _PLACEHOLDER.findall(text.replace("%%", ""))
    }


def _check_placeholders(entry: polib.POEntry, po_path: Path) -> None:
    """A translation must use the source's %N placeholders: a missing one
    drops a value (or a link, through interpolate), and an extra one renders
    as the word "undefined". Plural forms may leave out the count."""
    source = _placeholders(entry.msgid) | _placeholders(entry.msgid_plural or "")
    if entry.msgid_plural:
        translations = [text for _, text in sorted(entry.msgstr_plural.items())]
        required = source - {"1"}
    else:
        translations = [entry.msgstr]
        required = source
    for text in translations:
        found = _placeholders(text)
        if found - source or required - found:
            raise ValueError(
                f"{po_path}: the translation of {entry.msgid!r} uses "
                f"placeholders {sorted(found)}, but the source has {sorted(source)}"
            )


def _jed_bundle(po: polib.POFile, po_path: Path, version: str) -> dict:
    # @jupyterlab/translation refuses a bundle without these two headers,
    # which would stop NBI loading in that language; fail the build instead.
    language = po.metadata.get("Language", "").strip()
    plural_forms = po.metadata.get("Plural-Forms", "").strip()
    if not language or not plural_forms:
        raise ValueError(
            f"{po_path} needs Language and Plural-Forms headers; create "
            "catalogs with `jlpm i18n:update -l <locale>`."
        )
    if not _PLURAL_FORMS.match(plural_forms):
        raise ValueError(f"{po_path} has an invalid Plural-Forms: {plural_forms!r}")
    bundle = {
        "": {
            "domain": DOMAIN,
            # jupyterlab_server prefers a package's own catalog over a
            # language pack's copy only when it carries the newer version.
            "version": version,
            "language": language.replace("_", "-"),
            "plural_forms": plural_forms,
        }
    }
    for entry in po.translated_entries():
        _check_placeholders(entry, po_path)
        key = f"{entry.msgctxt}\x04{entry.msgid}" if entry.msgctxt else entry.msgid
        if entry.msgid_plural:
            plural = [text for _, text in sorted(entry.msgstr_plural.items())]
            if len(plural) == 1:
                plural.append("")
            bundle[key] = plural
        else:
            bundle[key] = [entry.msgstr]
    return bundle


def compile_catalogs(root, version: str) -> list:
    """Compile every ``.po`` catalog under ``root``; return the bundle paths."""
    compiled = []
    locale_dir = Path(root, DOMAIN, "locale")
    # Bundles are gitignored build outputs that the wheel picks up by glob, so
    # one left behind by a deleted or renamed catalog would still ship.
    for suffix in (".json", ".mo"):
        for stale in locale_dir.glob(f"*/LC_MESSAGES/{DOMAIN}{suffix}"):
            if not stale.with_suffix(".po").exists():
                stale.unlink()
    for po_path in sorted(locale_dir.glob(f"*/LC_MESSAGES/{DOMAIN}.po")):
        po = polib.pofile(str(po_path))
        bundle = _jed_bundle(po, po_path, version)
        # Python's gettext decodes a catalog without a declared charset as
        # ASCII and fails on the first accented string, so write UTF-8 and
        # say so.
        po.encoding = "utf-8"
        po.metadata["Content-Type"] = "text/plain; charset=UTF-8"
        # Untranslated and fuzzy entries are left out, as msgfmt does, so the
        # server falls back to English for them just as the frontend does.
        po.save_as_mofile(str(po_path.with_suffix(".mo")))
        json_path = po_path.with_suffix(".json")
        json_path.write_text(
            json.dumps(bundle, ensure_ascii=False, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
        compiled.append(json_path)
    return compiled


class CustomBuildHook(BuildHookInterface):
    def initialize(self, version, build_data):
        if self.target_name == "wheel":
            compile_catalogs(self.root, self.metadata.version)
