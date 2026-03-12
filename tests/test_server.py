"""Tests for strands_tools_mcp.server."""

import asyncio
import os
import tempfile
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from strands_tools_mcp.server import create_server, register_tool

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


def _make_mock_strands_tool(name: str = "mock_tool", return_value: str = "ok") -> MagicMock:
    """Create a mock that mimics a DecoratedFunctionTool."""
    mock = MagicMock()
    mock.tool_name = name
    mock.tool_spec = {
        "name": name,
        "description": f"Mock tool: {name}",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "input": {"type": "string", "description": "Some input"},
                },
                "required": ["input"],
            }
        },
    }
    mock.return_value = return_value
    return mock


def _get_registered_tool_names(mcp) -> set[str]:
    """Get the set of tool names registered on the FastMCP server."""
    loop = asyncio.get_event_loop()
    tools = loop.run_until_complete(mcp.list_tools())
    return {t.name for t in tools}


def _get_registered_tool(mcp, name: str):
    """Get a registered tool by name from the FastMCP server."""
    loop = asyncio.get_event_loop()
    return loop.run_until_complete(mcp.get_tool(name))


# ---------------------------------------------------------------------------
# register_tool
# ---------------------------------------------------------------------------


class TestRegisterTool:
    """Tests for ``register_tool``."""

    def test_registers_tool_on_mcp(self) -> None:
        """Calling register_tool adds a tool to the FastMCP server."""
        from fastmcp import FastMCP

        mcp = FastMCP("test")
        mock_tool = _make_mock_strands_tool("echo")

        register_tool(mcp, mock_tool)

        names = _get_registered_tool_names(mcp)
        assert "echo" in names

    def test_handler_calls_strands_tool(self) -> None:
        """The registered handler delegates to the underlying Strands tool."""
        from fastmcp import FastMCP

        mcp = FastMCP("test")
        mock_tool = _make_mock_strands_tool("delegator", return_value="delegated result")

        register_tool(mcp, mock_tool)

        # Retrieve the registered tool and invoke its fn
        registered = _get_registered_tool(mcp, "delegator")
        handler = registered.fn

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(handler(input="test"))
        mock_tool.assert_called_once_with(input="test")
        assert result == "delegated result"

    def test_handler_formats_dict_result(self) -> None:
        """Dict results with 'content' key are formatted as text."""
        from fastmcp import FastMCP

        mcp = FastMCP("test")
        mock_tool = _make_mock_strands_tool("formatter")
        mock_tool.return_value = {
            "status": "success",
            "content": [
                {"text": "line one"},
                {"text": "line two"},
            ],
        }

        register_tool(mcp, mock_tool)

        registered = _get_registered_tool(mcp, "formatter")
        handler = registered.fn

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(handler(input="x"))

        assert result == "line one\nline two"

    def test_tool_with_no_properties(self) -> None:
        """A Strands tool with no input properties is registered correctly."""
        from fastmcp import FastMCP

        mcp = FastMCP("test")
        mock_tool = MagicMock()
        mock_tool.tool_name = "no_args"
        mock_tool.tool_spec = {
            "name": "no_args",
            "description": "Tool with no args",
            "inputSchema": {"json": {"type": "object", "properties": {}, "required": []}},
        }
        mock_tool.return_value = "done"

        register_tool(mcp, mock_tool)

        names = _get_registered_tool_names(mcp)
        assert "no_args" in names

    def test_tool_with_optional_params(self) -> None:
        """Optional params default to None and are excluded from the call."""
        from fastmcp import FastMCP

        mcp = FastMCP("test")
        mock_tool = MagicMock()
        mock_tool.tool_name = "opt_tool"
        mock_tool.tool_spec = {
            "name": "opt_tool",
            "description": "Tool with optional",
            "inputSchema": {
                "json": {
                    "type": "object",
                    "properties": {
                        "required_param": {"type": "string"},
                        "optional_param": {"type": "integer"},
                    },
                    "required": ["required_param"],
                }
            },
        }
        mock_tool.return_value = "result"

        register_tool(mcp, mock_tool)

        registered = _get_registered_tool(mcp, "opt_tool")
        handler = registered.fn

        loop = asyncio.get_event_loop()
        result = loop.run_until_complete(handler(required_param="hello"))
        # Only the required param should be passed (optional is None, filtered out)
        mock_tool.assert_called_once_with(required_param="hello")
        assert result == "result"


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

    def test_loads_tools_from_paths_env(self) -> None:
        """Server loads tools when STRANDS_TOOLS_PATHS is set."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            env_patch = {"STRANDS_TOOLS_PATHS": tmp_path, "STRANDS_TOOLS": ""}
            with patch.dict(os.environ, env_patch):
                server = create_server()

            names = _get_registered_tool_names(server)
            assert "greet" in names
        finally:
            os.unlink(tmp_path)

    def test_loads_tools_from_names_env(self) -> None:
        """Server loads tools when STRANDS_TOOLS is set (mocked import)."""
        from strands.tools.decorator import DecoratedFunctionTool

        mock_tool = _make_mock_strands_tool("current_time")
        mock_tool.__class__ = DecoratedFunctionTool

        fake_module = MagicMock()
        fake_module.__dir__ = lambda self: ["current_time"]  # noqa: ARG005
        fake_module.current_time = mock_tool

        env_patch = {"STRANDS_TOOLS": "current_time", "STRANDS_TOOLS_PATHS": ""}
        with (
            patch.dict(os.environ, env_patch),
            patch("strands_tools_mcp.loader.importlib.import_module", return_value=fake_module),
        ):
            server = create_server()

        names = _get_registered_tool_names(server)
        assert "current_time" in names

    def test_loads_from_both_env_vars(self) -> None:
        """Server loads tools from both env vars simultaneously."""
        from strands.tools.decorator import DecoratedFunctionTool

        # Mock a named tool
        mock_tool = _make_mock_strands_tool("named_tool")
        mock_tool.__class__ = DecoratedFunctionTool

        fake_module = MagicMock()
        fake_module.__dir__ = lambda self: ["named_tool"]  # noqa: ARG005
        fake_module.named_tool = mock_tool

        # Create a file-based tool
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            env_patch = {"STRANDS_TOOLS": "named_tool", "STRANDS_TOOLS_PATHS": tmp_path}
            with (
                patch.dict(os.environ, env_patch),
                patch("strands_tools_mcp.loader.importlib.import_module", return_value=fake_module),
            ):
                server = create_server()

            names = _get_registered_tool_names(server)
            assert "named_tool" in names
            assert "greet" in names
        finally:
            os.unlink(tmp_path)
