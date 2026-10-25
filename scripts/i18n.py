"""Maintain Notebook Intelligence's translation catalogs.

    python scripts/i18n.py extract                # rewrite the .pot template
    python scripts/i18n.py update [-l ll_CC ...]  # merge it into .po files
    python scripts/i18n.py compile                # build the .json and .mo files
    python scripts/i18n.py check                  # fail if the .pot is stale

Strings are extracted from ``src/`` with jupyterlab-translate's TypeScript
extractor (``pip install jupyterlab-translate``), the tool JupyterLab and its
language packs use. Its own CLI walks every top-level folder of the
repository, ``.venv`` and ``node_modules`` included, so this runs only the
extractor. Python strings are extracted from ``notebook_intelligence/`` by an
AST walk (``extract_py_strings``) for ``notebook_intelligence/i18n.py``,
which loads NBI's own ``.mo`` files. Occurrences are recorded without line
numbers so the template changes only when strings do.

The settings schema is deliberately not scanned: the server translates
schema strings only from JupyterLab language packs, never from an
extension's own catalog, so they stay English.
"""

import argparse
import ast
import contextlib
import json
import os
import re
import subprocess
import sys
import sysconfig
import tempfile
from pathlib import Path

import polib

ROOT = Path(__file__).resolve().parent.parent
DOMAIN = "notebook_intelligence"
SRC_DIR = ROOT / "src"
# The first-run tour's English copy. It doubles as the admin override
# template, so it stays JSON; src/tour/tour-text.ts translates its strings
# under this context when the tour is shown.
TOUR_DEFAULTS_PATH = SRC_DIR / "tour" / "tour-defaults.json"
TOUR_CONTEXT = "first-run tour"
TOUR_TEMPLATE_CONTEXT = (
    "first-run tour; keep {launchers} as written, and 'Coding Agent' as "
    "JupyterLab's Launcher names it"
)
LOCALE_DIR = ROOT / DOMAIN / "locale"
POT_PATH = LOCALE_DIR / f"{DOMAIN}.pot"
WRAP = 100000
LOG_TAIL = 4000

# A string literal passed as the msgid of a singular `trans` call. The lint
# rule in package.json guarantees msgids are literals.
_SINGULAR_CALL = re.compile(
    r"""\btrans\.(?:__|gettext)\(\s*(['"])((?:\\.|(?!\1).)*)\1"""
)


@contextlib.contextmanager
def _captured_output():
    """Silence the extractor's logging, replaying its tail on failure."""
    sys.stdout.flush()
    sys.stderr.flush()
    saved = os.dup(1), os.dup(2)
    with tempfile.TemporaryFile() as log:
        os.dup2(log.fileno(), 1)
        os.dup2(log.fileno(), 2)
        try:
            yield
        except BaseException:
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            log.seek(0)
            # The extractor is a minified bundle; its stack traces quote it.
            sys.stderr.write(log.read().decode("utf-8", "replace")[-LOG_TAIL:])
            raise
        finally:
            os.dup2(saved[0], 1)
            os.dup2(saved[1], 2)
            os.close(saved[0])
            os.close(saved[1])


def _singular_msgids() -> dict:
    """Msgids passed to `trans.__`, mapped to a file that passes them."""
    found = {}
    for path in sorted(SRC_DIR.rglob("*.ts*")):
        text = path.read_text(encoding="utf-8")
        for match in _SINGULAR_CALL.finditer(text):
            msgid = re.sub(
                r"\\(.)",
                lambda m: {"n": "\n", "t": "\t"}.get(m.group(1), m.group(1)),
                match.group(2),
            )
            found.setdefault(msgid, path.relative_to(ROOT).as_posix())
    return found


PY_DIR = ROOT / "notebook_intelligence"
# trans.<method> -> (has context, has plural)
_PY_METHODS = {"__": (False, False), "_n": (False, True), "_p": (True, False), "_np": (True, True)}


def extract_py_strings(package_dir: Path = PY_DIR) -> list:
    """Messages from ``trans.__``/``_n``/``_p``/``_np`` calls in the server.

    Mirrors the TypeScript extractor's rule: only calls on a name literally
    ``trans``, and only string-literal arguments, so the template never
    depends on runtime values.
    """
    items = []
    for path in sorted(package_dir.rglob("*.py")):
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
        for node in ast.walk(tree):
            if (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and node.func.attr in _PY_METHODS
                and isinstance(node.func.value, ast.Attribute)
                and node.func.value.attr == "trans"
            ):
                raise SystemExit(
                    f"{path.relative_to(ROOT).as_posix()}:{node.lineno}: bind the "
                    "bundle to a local first (trans = ...); the extractor only "
                    "reads calls on a name `trans`."
                )
            if not (
                isinstance(node, ast.Call)
                and isinstance(node.func, ast.Attribute)
                and isinstance(node.func.value, ast.Name)
                and node.func.value.id == "trans"
                and node.func.attr in _PY_METHODS
            ):
                continue
            has_context, has_plural = _PY_METHODS[node.func.attr]
            needed = 1 + has_context + has_plural
            literals = node.args[:needed]
            where = f"{path.relative_to(ROOT).as_posix()}:{node.lineno}"
            if len(literals) < needed or not all(
                isinstance(arg, ast.Constant) and isinstance(arg.value, str)
                for arg in literals
            ):
                raise SystemExit(
                    f"{where}: trans.{node.func.attr} needs string literals; "
                    "pass runtime values as %1, %2 arguments."
                )
            values = [arg.value for arg in literals]
            msgctxt = values.pop(0) if has_context else None
            items.append(
                {
                    "msgid": values[0],
                    "msgid_plural": values[1] if has_plural else None,
                    "msgctxt": msgctxt,
                    "occurrence": path.relative_to(ROOT).as_posix(),
                }
            )
    return items


def build_template() -> polib.POFile:
    from jupyterlab_translate.utils import extract_tsx_strings

    entries = {}

    def add(msgid, occurrence, msgctxt=None, msgid_plural=None):
        if not msgid:
            return
        # gettext keys a message by context and msgid alone, so one msgid
        # cannot be both a singular and a plural (or two plurals).
        key = (msgctxt or "", msgid)
        entry = entries.get(key)
        if entry is not None and entry.msgid_plural != (msgid_plural or ""):
            raise SystemExit(
                f"{msgid!r} is used with different plural forms "
                f"({entry.occurrences[0][0]} and {occurrence}); give one of "
                "them a different msgid or a context."
            )
        if entry is None:
            entry = entries[key] = polib.POEntry(
                msgid=msgid, msgctxt=msgctxt, msgid_plural=msgid_plural or ""
            )
            if msgid_plural:
                entry.msgstr_plural = {0: "", 1: ""}
        if (occurrence, "") not in entry.occurrences:
            entry.occurrences.append((occurrence, ""))

    with _captured_output():
        tsx_items = extract_tsx_strings(SRC_DIR)

    def tour_strings(node):
        if isinstance(node, str):
            yield node
        elif isinstance(node, dict):
            for value in node.values():
                yield from tour_strings(value)

    tour_ref = TOUR_DEFAULTS_PATH.relative_to(ROOT).as_posix()
    tour_defaults = json.loads(TOUR_DEFAULTS_PATH.read_text(encoding="utf-8"))
    for text in tour_strings(tour_defaults):
        context = TOUR_TEMPLATE_CONTEXT if "{launchers}" in text else TOUR_CONTEXT
        add(text, tour_ref, context)

    for item in tsx_items:
        for path, _line in item["occurrences"]:
            add(
                item["msgid"],
                f"src/{path}",
                item.get("msgctxt"),
                item.get("msgid_plural"),
            )

    for item in extract_py_strings():
        add(
            item["msgid"],
            item["occurrence"],
            item["msgctxt"],
            item["msgid_plural"],
        )

    # The extractor merges `trans.__('X')` and `trans._n('X', 'Xs', n)` into
    # one plural entry. gettext keys by msgid, and a plural entry never
    # answers a singular lookup, so the `trans.__` call would stay English.
    singular = _singular_msgids()
    for (msgctxt, msgid), entry in entries.items():
        if entry.msgid_plural and not msgctxt and msgid in singular:
            raise SystemExit(
                f"{msgid!r} is used as a singular ({singular[msgid]}) and as a "
                f"plural ({entry.occurrences[0][0]}); give one of them a "
                "different msgid or a context."
            )

    pot = polib.POFile(wrapwidth=WRAP)
    pot.metadata = {
        "Project-Id-Version": DOMAIN,
        "MIME-Version": "1.0",
        "Content-Type": "text/plain; charset=utf-8",
        "Content-Transfer-Encoding": "8bit",
    }
    for key in sorted(entries):
        entry = entries[key]
        entry.occurrences.sort()
        pot.append(entry)
    return pot


def _keys(pofile: polib.POFile) -> set:
    return {
        (entry.msgctxt or "", entry.msgid, entry.msgid_plural or "")
        for entry in pofile
        if not entry.obsolete
    }


def extract(_args) -> int:
    LOCALE_DIR.mkdir(parents=True, exist_ok=True)
    pot = build_template()
    pot.save(str(POT_PATH))
    print(f"{len(pot)} strings written to {POT_PATH.relative_to(ROOT)}")
    return 0


def _locales() -> list:
    return sorted(
        path.parent.parent.name
        for path in LOCALE_DIR.glob(f"*/LC_MESSAGES/{DOMAIN}.po")
    )


def update(args) -> int:
    locales = args.locale or _locales()
    for locale in locales:
        po_path = LOCALE_DIR / locale / "LC_MESSAGES" / f"{DOMAIN}.po"
        command = ["update", "--ignore-obsolete"] if po_path.exists() else ["init"]
        kept = {}
        if po_path.exists():
            kept = {
                key: value
                for key, value in polib.pofile(str(po_path)).metadata.items()
                if key in ("Language", "Plural-Forms")
            }
        subprocess.check_call(
            [
                sys.executable,
                "-m",
                "babel.messages.frontend",
                *command,
                "--no-wrap",
                f"--domain={DOMAIN}",
                f"--input-file={POT_PATH}",
                f"--output-dir={LOCALE_DIR}",
                f"--locale={locale}",
            ]
        )
        _drop_format_flags(po_path)
        _restore_headers(po_path, kept)
    return 0


def _restore_headers(po_path: Path, kept: dict) -> None:
    """Babel drops Plural-Forms on update for a locale it does not know
    (no_NO), and the build then refuses the catalog; put back what the
    catalog had."""
    po = polib.pofile(str(po_path), wrapwidth=WRAP)
    missing = {k: v for k, v in kept.items() if not po.metadata.get(k)}
    if missing:
        po.metadata.update(missing)
        po.save(str(po_path))


def _drop_format_flags(po_path: Path) -> None:
    """Babel flags msgids with % or {name} in them as Python format strings,
    but NBI's %1 placeholders and {launchers} token are not, and the flag
    makes `msgfmt -c` reject valid translations ("%1 s" for "%1s")."""
    po = polib.pofile(str(po_path), wrapwidth=WRAP)
    changed = False
    for entry in po:
        for flag in ("python-format", "python-brace-format"):
            if flag in entry.flags:
                entry.flags.remove(flag)
                changed = True
    if changed:
        po.save(str(po_path))


def compile_(_args) -> int:
    sys.path.insert(0, str(ROOT))
    from hatch_build import compile_catalogs

    version = json.loads((ROOT / "package.json").read_text(encoding="utf-8"))[
        "version"
    ]
    for path in compile_catalogs(ROOT, version):
        print(path.relative_to(ROOT))
    return 0


def check(_args) -> int:
    if not POT_PATH.exists():
        print(f"{POT_PATH.relative_to(ROOT)} is missing; run `jlpm i18n:extract`.")
        return 1
    expected = _keys(build_template())
    committed = _keys(polib.pofile(str(POT_PATH), wrapwidth=WRAP))
    missing = sorted(expected - committed)
    stale = sorted(committed - expected)
    for label, keys in (("Not in the template", missing), ("No longer used", stale)):
        for msgctxt, msgid, _plural in keys:
            print(f"{label}: {msgctxt + ' | ' if msgctxt else ''}{msgid!r}")
    if missing or stale:
        print("The translation template is out of date; run `jlpm i18n:extract`.")
        return 1
    print(f"Translation template is current ({len(committed)} strings).")
    return 0


def main(argv=None) -> int:
    # jupyterlab-translate runs its `gettext-extract` console script by name,
    # so put this interpreter's scripts directories first even when its
    # environment is not activated.
    scripts_dirs = {sysconfig.get_path("scripts")}
    try:
        scripts_dirs.add(sysconfig.get_path("scripts", f"{os.name}_user"))
    except KeyError:
        pass
    os.environ["PATH"] = os.pathsep.join(
        [*sorted(d for d in scripts_dirs if d), os.environ.get("PATH", "")]
    )
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    sub.add_parser("extract").set_defaults(func=extract)
    update_parser = sub.add_parser("update")
    update_parser.add_argument("-l", "--locale", action="append")
    update_parser.set_defaults(func=update)
    sub.add_parser("compile").set_defaults(func=compile_)
    sub.add_parser("check").set_defaults(func=check)
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
