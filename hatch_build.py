"""Compile Notebook Intelligence's translation catalogs when building a wheel.

Only the ``.po`` sources are committed. Each one is compiled next to itself
into the ``.json`` bundle JupyterLab's frontend loads, which
``jupyterlab_server`` finds through the ``jupyterlab.locale`` entry point. The
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
    for stale in locale_dir.glob(f"*/LC_MESSAGES/{DOMAIN}.json"):
        if not stale.with_suffix(".po").exists():
            stale.unlink()
    for po_path in sorted(locale_dir.glob(f"*/LC_MESSAGES/{DOMAIN}.po")):
        bundle = _jed_bundle(polib.pofile(str(po_path)), po_path, version)
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
