"""Tests for strands_tools_mcp.loader."""

import os
import tempfile
import textwrap
from unittest.mock import MagicMock, patch

import pytest

from strands_tools_mcp.loader import load_tools_from_names, load_tools_from_paths

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_TOOL_SOURCE = textwrap.dedent("""\
    from strands import tool

    @tool
    def test_echo(message: str) -> str:
        \"\"\"A test tool that echoes a message.

        Args:
            message: The message to echo

        Returns:
            The echoed message
        \"\"\"
        return f"Echo: {message}"
""")


def _make_mock_decorated_tool(name: str = "mock_tool") -> MagicMock:
    """Return a mock that quacks like a ``DecoratedFunctionTool``."""
    mock = MagicMock()
    mock.tool_name = name
    mock.tool_spec = {
        "name": name,
        "description": f"A mock tool called {name}",
        "inputSchema": {
            "json": {
                "type": "object",
                "properties": {
                    "arg1": {"type": "string", "description": "An argument"},
                },
                "required": ["arg1"],
            }
        },
    }
    return mock


# ---------------------------------------------------------------------------
# load_tools_from_names
# ---------------------------------------------------------------------------


class TestLoadToolsFromNames:
    """Tests for ``load_tools_from_names``."""

    def test_loads_tool_from_module(self) -> None:
        """A module with a DecoratedFunctionTool attribute is discovered."""
        from strands.tools.decorator import DecoratedFunctionTool

        mock_tool = _make_mock_decorated_tool("current_time")
        # Make mock pass isinstance check
        mock_tool.__class__ = DecoratedFunctionTool

        fake_module = MagicMock()
        fake_module.__dir__ = lambda self: ["current_time"]  # noqa: ARG005
        fake_module.current_time = mock_tool

        with patch("strands_tools_mcp.loader.importlib.import_module", return_value=fake_module):
            tools = load_tools_from_names(["current_time"])

        assert len(tools) == 1
        assert tools[0].tool_name == "current_time"

    def test_raises_on_missing_module(self) -> None:
        """ImportError propagates when a module does not exist."""
        with pytest.raises(ImportError):
            load_tools_from_names(["nonexistent_tool_xyz"])

    def test_empty_list_returns_empty(self) -> None:
        """An empty names list returns an empty tools list."""
        assert load_tools_from_names([]) == []


# ---------------------------------------------------------------------------
# load_tools_from_paths
# ---------------------------------------------------------------------------


class TestLoadToolsFromPaths:
    """Tests for ``load_tools_from_paths``."""

    def test_loads_tool_from_file(self) -> None:
        """A .py file with an @tool-decorated function is discovered."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_TOOL_SOURCE)
            f.flush()
            tmp_path = f.name

        try:
            tools = load_tools_from_paths([tmp_path])
            assert len(tools) == 1
            assert tools[0].tool_name == "test_echo"

            # Verify the tool is actually callable
            spec = tools[0].tool_spec
            assert "inputSchema" in spec
            assert spec["name"] == "test_echo"
        finally:
            os.unlink(tmp_path)

    def test_raises_on_missing_file(self) -> None:
        """FileNotFoundError is raised for a non-existent path."""
        with pytest.raises(FileNotFoundError, match="Tool file not found"):
            load_tools_from_paths(["/tmp/does_not_exist_abc123.py"])

    def test_empty_list_returns_empty(self) -> None:
        """An empty paths list returns an empty tools list."""
        assert load_tools_from_paths([]) == []

    def test_file_with_no_tools_returns_empty(self) -> None:
        """A .py file without @tool-decorated functions returns nothing."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write("x = 42\n")
            f.flush()
            tmp_path = f.name

        try:
            tools = load_tools_from_paths([tmp_path])
            assert tools == []
        finally:
            os.unlink(tmp_path)

    def test_multiple_tools_in_one_file(self) -> None:
        """A file with multiple @tool functions returns all of them."""
        source = textwrap.dedent("""\
            from strands import tool

            @tool
            def tool_a(x: str) -> str:
                \"\"\"Tool A.

                Args:
                    x: Input

                Returns:
                    Output
                \"\"\"
                return x

            @tool
            def tool_b(y: int) -> str:
                \"\"\"Tool B.

                Args:
                    y: A number

                Returns:
                    The number as string
                \"\"\"
                return str(y)
        """)

        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(source)
            f.flush()
            tmp_path = f.name

        try:
            tools = load_tools_from_paths([tmp_path])
            assert len(tools) == 2
            names = {t.tool_name for t in tools}
            assert names == {"tool_a", "tool_b"}
        finally:
            os.unlink(tmp_path)
