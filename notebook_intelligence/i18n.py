# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Translations for text the server writes for the user.

The frontend translates its own strings through JupyterLab; this module does
the same for text the server produces and the UI shows as is (the readiness
report, approval card buttons, toolset descriptions). Both read the same
catalogs: ``locale/<locale>/LC_MESSAGES/notebook_intelligence.po``, compiled
at build time into the ``.json`` the frontend loads and the ``.mo`` read
here. jupyterlab_server's own Python translator reads only JupyterLab
language packs' catalogs, so NBI loads its own.

The locale comes with each request, as an ``nbi_locale`` query parameter on
REST calls and the chat WebSocket, not from a process-wide setting, since one
server can serve tabs in different languages. A query parameter rather than a
header: a custom header would make every cross-origin request need a CORS
preflight that jupyter_server's default allow-list refuses.

A catalog is used only when jupyterlab_server would serve the frontend's
for the same locale: a JupyterLab language pack for exactly that locale is
installed, and NBI's folder is named as the locale, ignoring case, with no
fallback from de_AT to de. So the server never translates what the
frontend shows in English.

Strings use the frontend's conventions, so one msgid serves both: ``%1``,
``%2`` placeholders, ``%%`` for a literal percent sign, ``__``/``_n``/``_p``/
``_np``. Name the bundle ``trans`` at the call site: ``scripts/i18n.py``
extracts calls on that name. Text sent to a model stays English.
"""

from __future__ import annotations

import functools
import gettext
import logging
import re
from pathlib import Path
from typing import Any, Optional

DOMAIN = "notebook_intelligence"
LOCALE_DIR = Path(__file__).parent / "locale"
LOCALE_QUERY_ARG = "nbi_locale"

log = logging.getLogger(__name__)

# A locale setting as JupyterLab writes it (de_DE, zh_TW, sr_Latn_RS) or a
# BCP 47 tag; anything else is ignored rather than handed to gettext.
_LOCALE_PATTERN = re.compile(r"^[A-Za-z]{2,3}(?:[_-][A-Za-z0-9]{2,8}){0,3}$")
_PLACEHOLDER = re.compile(r"%%|%(\d+)")


def _strfmt(text: str, args: tuple) -> str:
    """Fill %1, %2 ... the way @jupyterlab/translation's Gettext.strfmt does,
    with %% for a literal percent sign. One pass, so an argument containing
    a percent sign is inserted unchanged."""

    def substitute(match: re.Match) -> str:
        if match.group(1) is None:
            return "%"
        index = int(match.group(1)) - 1
        return str(args[index]) if 0 <= index < len(args) else match.group(0)

    return _PLACEHOLDER.sub(substitute, text)


class TranslationBundle:
    """The server-side counterpart of the frontend's TranslationBundle."""

    def __init__(self, translations: gettext.NullTranslations, locale: str):
        self._translations = translations
        self.locale = locale

    def __(self, msgid: str, *args: Any) -> str:
        return _strfmt(self._translations.gettext(msgid), args)

    def _n(self, msgid: str, msgid_plural: str, n: int, *args: Any) -> str:
        return _strfmt(
            self._translations.ngettext(msgid, msgid_plural, n), (n,) + args
        )

    def _p(self, msgctxt: str, msgid: str, *args: Any) -> str:
        return _strfmt(self._translations.pgettext(msgctxt, msgid), args)

    def _np(
        self, msgctxt: str, msgid: str, msgid_plural: str, n: int, *args: Any
    ) -> str:
        return _strfmt(
            self._translations.npgettext(msgctxt, msgid, msgid_plural, n),
            (n,) + args,
        )


def normalize_locale(locale: Optional[str]) -> Optional[str]:
    """A gettext locale (``de_DE``) from a request value, or None for English
    or anything malformed."""
    if not isinstance(locale, str):
        return None
    value = locale.strip()
    if not value or not _LOCALE_PATTERN.match(value):
        return None
    value = value.replace("-", "_")
    if value.lower() in ("en", "default"):
        return None
    return value


def _catalog_path(locale: str) -> Optional[Path]:
    try:
        folders = [path for path in LOCALE_DIR.iterdir() if path.is_dir()]
    except OSError:
        return None
    for folder in folders:
        if folder.name.lower() == locale.lower():
            path = folder / "LC_MESSAGES" / f"{DOMAIN}.mo"
            return path if path.is_file() else None
    return None


@functools.lru_cache(maxsize=1)
def _installed_language_packs() -> Optional[dict]:
    """Each locale with a JupyterLab language pack, mapped to its English
    display name ("German (Germany)"), or None if they cannot be listed
    (a pack that fails to load makes jupyterlab_server report none at all).
    Cached: jupyterlab_server scans the installed packages and parses each
    pack, and installing a pack needs a server restart to take effect
    anyway."""
    try:
        from jupyterlab_server.translation_utils import get_language_packs

        packs, message = get_language_packs()
    except Exception as error:
        log.warning("Could not list JupyterLab language packs: %s", error)
        return None
    if message:
        # Also reported alongside a valid list ("The following locales are
        # invalid: ..."), which is kept.
        log.warning("JupyterLab language packs: %s", message)
    if not packs:
        return None
    return {locale: _pack_name(locale, info) for locale, info in packs.items()}


def _pack_name(locale: str, info: Any) -> str:
    """A pack's English display name, or its locale code when there is no
    usable one: babel cannot name some locales jupyterlab_server accepts
    (no_NO), and jupyterlab_server then reports the display locale ("En")."""
    name = str((info or {}).get("displayName") or "").strip()
    if not name or (
        name.lower() in ("en", "english") and not locale.lower().startswith("en")
    ):
        return locale
    return name


def _displayed(locale: str) -> bool:
    """Whether JupyterLab shows its UI in this locale: it does only with a
    language pack installed for exactly that locale (or when the installed
    packs cannot be listed, in which case the request is taken at its word)."""
    packs = _installed_language_packs()
    return packs is None or locale in packs


@functools.lru_cache(maxsize=64)
def _bundle(locale: Optional[str]) -> TranslationBundle:
    if locale is None:
        return TranslationBundle(gettext.NullTranslations(), "en")
    # Without a language pack JupyterLab serves the frontend no translations
    # (and matches its name exactly), so NBI's own UI is English.
    if not _displayed(locale):
        return TranslationBundle(gettext.NullTranslations(), locale)
    path = _catalog_path(locale)
    if path is None:
        return TranslationBundle(gettext.NullTranslations(), locale)
    try:
        with path.open("rb") as catalog:
            translations = gettext.GNUTranslations(catalog)
    except Exception as error:
        # As in the frontend, a catalog that cannot be read must not break
        # the requests that ask for it; they get English.
        log.warning("Could not load translations from %s: %s", path, error)
        translations = gettext.NullTranslations()
    return TranslationBundle(translations, locale)


def load(locale: Optional[str] = None) -> TranslationBundle:
    """The bundle for a locale; English when it is unset or unknown."""
    return _bundle(normalize_locale(locale))


def english() -> TranslationBundle:
    return _bundle(None)


def response_bundle(response: Any) -> TranslationBundle:
    """``response.trans`` for any chat response, English for one without it."""
    trans = getattr(response, "trans", None)
    return trans if isinstance(trans, TranslationBundle) else english()


def request_bundle(handler: Any) -> TranslationBundle:
    """The bundle for the locale a REST or WebSocket request asked for."""
    try:
        locale = handler.get_query_argument(LOCALE_QUERY_ARG, None)
    except Exception:
        locale = None
    return load(locale)


# Crowdin's in-context translation pseudo-language: shown, but not a
# language to reply in.
_PSEUDO_LANGUAGE = "ach_UG"


def reply_language(locale: Optional[str]) -> Optional[str]:
    """The language a model should reply in for the user's JupyterLab
    locale, by the English name its language pack gives it ("German
    (Germany)"), or None to leave prompts unchanged: English, unset,
    malformed, the pseudo-language, or a locale JupyterLab does not display.
    When the packs cannot be listed it is named by its locale code, which
    models understand."""
    value = normalize_locale(locale)
    if value is None or value == _PSEUDO_LANGUAGE or not _displayed(value):
        return None
    if value.split("_")[0].lower() == "en":
        return None
    name = (_installed_language_packs() or {}).get(value)
    return name if name and name != value else f"the language of locale {value}"


def request_reply_language(handler: Any, enabled: bool) -> Optional[str]:
    """The language a model should reply in for this request, or None when
    the user has not asked for replies in their language (``enabled``) or
    JupyterLab is in English."""
    if enabled is not True:
        return None
    try:
        locale = handler.get_query_argument(LOCALE_QUERY_ARG, None)
    except Exception:
        locale = None
    return reply_language(locale)


def with_reply_language(prompt: Optional[str], language: Optional[str]) -> Optional[str]:
    """``prompt`` with the reply-language instruction appended, or unchanged
    when there is no language to ask for."""
    instruction = reply_language_instruction(language)
    if not instruction:
        return prompt
    return f"{prompt}\n\n{instruction}" if prompt else instruction


# From the instruction's first sentence to the end, so a title the agent
# truncated inside the second sentence is matched too; or the first sentence
# itself cut short at the agent's truncation marker (codex-acp keeps 117
# characters, claude-code-acp 127), which a prompt of 60 to 120 characters
# lands in.
_REPLY_INSTRUCTION = re.compile(
    r"\s*Reply in [^\n]*?, the user's JupyterLab language\.[\s\S]*$"
    r"|\s*Reply in [^\n.]*(?:\.\.\.|…)$"
)


def without_reply_instruction(text: str) -> str:
    """``text`` without a trailing reply-language instruction: an agent's
    session transcript holds the query as sent, and a session preview or
    title should show only what the user asked."""
    return _REPLY_INSTRUCTION.sub("", text)


def reply_language_instruction(language: Optional[str]) -> str:
    """The instruction that asks a model to write its prose in ``language``.
    Empty when there is no language to ask for, so prompts stay unchanged."""
    if not language:
        return ""
    return (
        f"Reply in {language}, the user's JupyterLab language. Leave code, "
        "identifiers, file names, file contents, commands and quoted output "
        "as they are."
    )

