# Copyright (c) Mehmet Bektas <mbektasgh@outlook.com>

"""stdio MCP servers start in NBI's user directory, not the Jupyter cwd.

The Jupyter server's working directory is the JupyterLab root in the
documented ``jupyter lab`` flow. Tools such as ``npx`` and ``python -m``
resolve what they run from their cwd, and NBI starts every configured
stdio server on extension load, so a server inheriting that cwd would let
a checkout opened as the root decide what runs. ``MCPManager`` therefore
pins an explicit cwd on every ``StdioServerParameters`` it builds and the
client shim forwards it to the SDK.
"""

import asyncio
import os
import sys
import tempfile
import textwrap
from unittest.mock import Mock, patch

import pytest
from mcp import StdioServerParameters
from mcp.types import Implementation

from notebook_intelligence import mcp_manager as mcp_manager_module
from notebook_intelligence.mcp_client import Client, StdioTransport
from notebook_intelligence.mcp_manager import (
    MCPManager,
    MCPServerImpl,
    default_stdio_server_cwd,
)


def test_default_cwd_is_the_nbi_user_dir(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    assert default_stdio_server_cwd() == os.path.join(
        str(tmp_path), ".jupyter", "nbi"
    )
    manager = MCPManager({})
    assert manager.stdio_cwd == default_stdio_server_cwd()


def test_create_mcp_server_pins_the_configured_cwd(tmp_path):
    cwd = tmp_path / "nbi"
    manager = MCPManager({}, stdio_cwd=str(cwd))
    with patch("notebook_intelligence.mcp_manager.MCPServerImpl") as impl:
        manager.create_mcp_server(
            "fs", {"command": "npx", "args": ["-y", "some-server"]}
        )
    _, kwargs = impl.call_args
    params = kwargs["stdio_params"]
    assert params.command == "npx"
    assert params.cwd == str(cwd)
    # The directory is created ahead of the spawn so a fresh install, where
    # nothing has written ~/.jupyter/nbi yet, does not fail to start.
    assert cwd.is_dir()


def test_create_mcp_server_never_leaves_cwd_unset():
    manager = MCPManager({})
    with patch("notebook_intelligence.mcp_manager.MCPServerImpl") as impl:
        manager.create_mcp_server("x", {"command": "cmd", "env": {"A": "b"}})
    _, kwargs = impl.call_args
    assert kwargs["stdio_params"].cwd == manager.stdio_cwd
    assert kwargs["stdio_params"].env["A"] == "b"


def test_client_transport_carries_the_cwd(tmp_path):
    server = MCPServerImpl.__new__(MCPServerImpl)
    server._manager = Mock(websocket_connector=None)
    server._stdio_params = StdioServerParameters(
        command="cmd", args=["a"], env=None, cwd=str(tmp_path)
    )
    server._streamable_http_params = None
    server._mcp_client_info = Implementation(name="t", title="t", version="0")
    client = server._create_client()
    assert isinstance(client._transport, StdioTransport)
    assert client._transport.cwd == str(tmp_path)


_CWD_SERVER = textwrap.dedent(
    """
    import asyncio
    import os
    from mcp.server import Server
    from mcp.server.stdio import stdio_server
    from mcp.types import Tool, TextContent

    server = Server("nbi-cwd-test")

    @server.list_tools()
    async def list_tools():
        return [Tool(name="cwd", description="Report cwd.",
                     inputSchema={"type": "object", "properties": {}})]

    @server.call_tool()
    async def call_tool(name, args):
        return [TextContent(type="text", text=os.getcwd())]

    async def main():
        async with stdio_server() as (read, write):
            await server.run(read, write, server.create_initialization_options())

    asyncio.run(main())
    """
)


@pytest.fixture
def cwd_server_script():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(_CWD_SERVER)
        path = f.name
    try:
        yield path
    finally:
        try:
            os.unlink(path)
        except OSError:
            pass


def _report_cwd(script: str, cwd):
    async def go():
        transport = StdioTransport(
            command=sys.executable, args=[script], env=dict(os.environ), cwd=cwd
        )
        client = Client(transport, client_info=Implementation(
            name="t", title="t", version="0"
        ))
        async with client:
            result = await client.call_tool("cwd", {})
        return result.content[0].text

    return asyncio.run(go())


def test_shim_starts_the_server_in_the_requested_cwd(cwd_server_script, tmp_path):
    reported = _report_cwd(cwd_server_script, str(tmp_path))
    assert os.path.realpath(reported) == os.path.realpath(str(tmp_path))
    assert os.path.realpath(reported) != os.path.realpath(os.getcwd())


def test_shim_without_cwd_keeps_the_sdk_default(cwd_server_script):
    # ``None`` is the SDK default (inherit): the manager never passes it,
    # but the shim's other callers may.
    reported = _report_cwd(cwd_server_script, None)
    assert os.path.realpath(reported) == os.path.realpath(os.getcwd())
