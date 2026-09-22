# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""Keep MCP credentials out of the ``mcp-config-file`` round trip.

The Settings panel's **Add / Edit** button opens the MCP config in the
JupyterLab file editor. That editor only shows files the Contents API
serves, so the frontend copies the GET response into
``<jupyter root>/nbi.mcp.temp.json`` and POSTs the edited text back on save.
Whatever the GET response carries therefore lands in the workspace as a
plain file: created with the process umask rather than the ``0o600`` the
stored ``mcp.json`` gets, inside the working directory the agent modes read
from, and left there until the editor tab is closed (a browser close or
reload keeps it, and deletion goes through the trash).

The values this matters for are the ones the README documents under
``headers`` (``Authorization: Bearer ...``) and ``env`` (``*_API_KEY``,
``*_TOKEN``). The handler serves those as :data:`REDACTED_VALUE` and the
POST swaps the placeholder back for the stored value, so the editor keeps
working: non-secret entries round-trip untouched, a placeholder left in
place keeps the stored credential, and typing a new value replaces it.

Which entries count as credentials follows the same conservative,
name-based shape as ``util.redact_env_secrets``: an ``env`` or ``headers``
key whose name carries one of the sensitive substrings (``TOKEN``,
``SECRET``, ``API_KEY``, ``AUTH``, ``COOKIE``, ...; header names are
compared with ``-`` folded to ``_`` so ``X-API-Key`` matches). A value that
is a URL with embedded ``user:password@`` userinfo is treated as a
credential whatever its key is called. A secret stored under a name that
matches none of those patterns is not caught; that is the same known gap
the process-env scrubber documents.
"""

import copy
from typing import Any
from urllib.parse import urlsplit

from notebook_intelligence.util import _looks_like_secret_env_name

# Same literal ``util.redact_env_secrets`` emits into tool output, so a user
# reading the editor recognizes it for what it is.
REDACTED_VALUE = "<redacted>"

_SECRET_SECTIONS = ("env", "headers")


class MCPConfigSecretError(ValueError):
    """A posted config keeps a placeholder that has no stored value."""


def _looks_like_secret_key(key: str) -> bool:
    return _looks_like_secret_env_name(key.replace("-", "_"))


def _carries_url_credential(value: str) -> bool:
    if "://" not in value:
        return False
    try:
        parts = urlsplit(value)
    except ValueError:
        return False
    return bool(parts.username or parts.password)


def is_secret_mcp_value(key: str, value: Any) -> bool:
    """Whether an ``env`` / ``headers`` entry should leave the server masked."""
    if not isinstance(value, str) or not value:
        return False
    return _looks_like_secret_key(str(key)) or _carries_url_credential(value)


def _servers(config: Any) -> dict:
    servers = config.get("mcpServers") if isinstance(config, dict) else None
    return servers if isinstance(servers, dict) else {}


def redact_mcp_secrets(config: Any) -> Any:
    """Return a deep copy of ``config`` with credential values masked.

    Anything that is not the documented ``mcpServers -> <name> -> env /
    headers -> <key>: <str>`` shape is passed through unchanged; the shape
    validator owns rejecting it on the way back in.
    """
    redacted = copy.deepcopy(config)
    for server in _servers(redacted).values():
        if not isinstance(server, dict):
            continue
        for section in _SECRET_SECTIONS:
            entries = server.get(section)
            if not isinstance(entries, dict):
                continue
            for key, value in entries.items():
                if is_secret_mcp_value(key, value):
                    entries[key] = REDACTED_VALUE
    return redacted


def restore_mcp_secrets(posted: Any, stored: Any) -> Any:
    """Swap every :data:`REDACTED_VALUE` in ``posted`` for the stored value.

    ``stored`` is the merged config the GET was rendered from. Returns
    ``posted`` itself when it carries no placeholder, otherwise a deep copy
    with the placeholders resolved. A placeholder resolves only to a value
    :func:`redact_mcp_secrets` would have masked; any other placeholder (a
    renamed server, a key the stored config never had, one the user typed
    over a value that was served in the clear) raises
    :class:`MCPConfigSecretError`, since persisting the literal placeholder
    would silently replace a working credential.
    """
    placeholders = [
        (name, section, key)
        for name, server in _servers(posted).items()
        if isinstance(server, dict)
        for section in _SECRET_SECTIONS
        if isinstance(server.get(section), dict)
        for key, value in server[section].items()
        if value == REDACTED_VALUE
    ]
    if not placeholders:
        return posted
    restored = copy.deepcopy(posted)
    stored_servers = _servers(stored)
    for name, section, key in placeholders:
        stored_server = stored_servers.get(name)
        stored_entries = (
            stored_server.get(section) if isinstance(stored_server, dict) else None
        )
        stored_value = (
            stored_entries.get(key) if isinstance(stored_entries, dict) else None
        )
        if stored_value == REDACTED_VALUE or not is_secret_mcp_value(key, stored_value):
            raise MCPConfigSecretError(
                f"mcpServers.{name}.{section}.{key}: {REDACTED_VALUE!r} stands in "
                "for a stored value, and there is none to restore for this entry; "
                "enter the actual value"
            )
        restored["mcpServers"][name][section][key] = stored_value
    return restored
