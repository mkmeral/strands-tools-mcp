"""Tests for strands_tools_mcp.server."""

import asyncio
import os
import tempfile
import textwrap
from unittest.mock import patch

import pytest

from strands_tools_mcp.server import _call_strands_tool, create_server

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TOOL_SOURCE = textwrap.dedent("""\
    from strands import tool

    @tool
    def greet(name: str) -> str:
        \"\"\"Greet someone by name.

        Args:
            name: The name to greet

        Returns:
            A greeting string
        \"\"\"
        return f"Hello, {name}!"
""")


# ---------------------------------------------------------------------------
# _call_strands_tool
# ---------------------------------------------------------------------------


class TestCallStrandsTool:
    """Tests for the ``_call_strands_tool`` helper."""

    def test_calls_decorated_tool(self) -> None:
        """A DecoratedFunctionTool can be invoked through stream()."""
        from strands.tools.loader import load_tools_from_module_path

        tools = load_tools_from_module_path("strands_tools.current_time")
        tool = tools[0]

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_call_strands_tool(tool, {"timezone": "UTC"}))

        assert isinstance(result, str)
        assert len(result) > 0  # Should be a timestamp

    def test_calls_toolspec_tool(self) -> None:
        """A PythonAgentTool (TOOL_SPEC) can be invoked through stream()."""
        from strands.tools.loader import load_tools_from_module_path

        tools = load_tools_from_module_path("strands_tools.http_request")
        tool = tools[0]

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(_call_strands_tool(tool, {"url": "https://httpbin.org/get", "method": "GET"}))

        assert isinstance(result, str)
        assert "200" in result  # Should contain status code 200

    def test_calls_file_based_tool(self) -> None:
        """A tool loaded from a temp file can be invoked."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            from strands.tools.loader import load_tools_from_file_path

            tools = load_tools_from_file_path(tmp_path)
            tool = tools[0]

            loop = asyncio.get_event_loop()
            result = loop.run_until_complete(_call_strands_tool(tool, {"name": "World"}))

            assert "Hello, World!" in result
        finally:
            os.unlink(tmp_path)


# ---------------------------------------------------------------------------
# create_server
# ---------------------------------------------------------------------------


class TestCreateServer:
    """Tests for ``create_server``."""

    def test_exits_when_no_env_vars(self) -> None:
        """Server exits with error when no tool env vars are set."""
        env = {k: v for k, v in os.environ.items() if k not in ("STRANDS_TOOLS", "STRANDS_TOOLS_PATHS")}
        with patch.dict(os.environ, env, clear=True), pytest.raises(SystemExit):
            create_server()

    def test_creates_server_with_names(self) -> None:
        """Server loads tools when STRANDS_TOOLS is set."""
        env_patch = {"STRANDS_TOOLS": "current_time", "STRANDS_TOOLS_PATHS": ""}
        with patch.dict(os.environ, env_patch):
            server, tools = create_server()

        assert len(tools) >= 1
        names = {t.tool_name for t in tools}
        assert "current_time" in names

    def test_creates_server_with_paths(self) -> None:
        """Server loads tools when STRANDS_TOOLS_PATHS is set."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            env_patch = {"STRANDS_TOOLS_PATHS": tmp_path, "STRANDS_TOOLS": ""}
            with patch.dict(os.environ, env_patch):
                server, tools = create_server()

            names = {t.tool_name for t in tools}
            assert "greet" in names
        finally:
            os.unlink(tmp_path)

    def test_creates_server_with_both(self) -> None:
        """Server loads tools from both env vars simultaneously."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            env_patch = {"STRANDS_TOOLS": "current_time", "STRANDS_TOOLS_PATHS": tmp_path}
            with patch.dict(os.environ, env_patch):
                server, tools = create_server()

            names = {t.tool_name for t in tools}
            assert "current_time" in names
            assert "greet" in names
        finally:
            os.unlink(tmp_path)

    def test_creates_server_with_toolspec_tool(self) -> None:
        """Server loads TOOL_SPEC-based tools (e.g. file_read)."""
        env_patch = {"STRANDS_TOOLS": "file_read", "STRANDS_TOOLS_PATHS": ""}
        with patch.dict(os.environ, env_patch):
            server, tools = create_server()

        names = {t.tool_name for t in tools}
        assert "file_read" in names

    def test_creates_server_with_mixed_tool_types(self) -> None:
        """Server loads both decorated and TOOL_SPEC tools together."""
        env_patch = {"STRANDS_TOOLS": "current_time,file_read", "STRANDS_TOOLS_PATHS": ""}
        with patch.dict(os.environ, env_patch):
            server, tools = create_server()

        names = {t.tool_name for t in tools}
        assert "current_time" in names
        assert "file_read" in names

    def test_server_has_handlers_registered(self) -> None:
        """The server has list_tools and call_tool handlers registered."""

        env_patch = {"STRANDS_TOOLS": "current_time", "STRANDS_TOOLS_PATHS": ""}
        with patch.dict(os.environ, env_patch):
            server, tools = create_server()

        # The MCP Server registers handlers keyed by request type classes
        handler_types = {type(k).__name__ if not isinstance(k, type) else k.__name__ for k in server.request_handlers}
        assert "ListToolsRequest" in handler_types
        assert "CallToolRequest" in handler_types
