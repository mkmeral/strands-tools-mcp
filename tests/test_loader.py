"""Tests for strands_tools_mcp.loader."""

import http.server
import os
import tempfile
import textwrap
import threading

import pytest

from strands_tools_mcp.loader import _download_to_tempfile, _is_url, load_tools_from_names, load_tools_from_paths

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

SAMPLE_DECORATED_TOOL = textwrap.dedent("""\
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


# ---------------------------------------------------------------------------
# load_tools_from_names
# ---------------------------------------------------------------------------


class TestLoadToolsFromNames:
    """Tests for ``load_tools_from_names``."""

    def test_loads_decorated_tool(self) -> None:
        """A @tool-decorated module is loaded (e.g. current_time)."""
        tools = load_tools_from_names(["current_time"])
        assert len(tools) >= 1
        assert tools[0].tool_name == "current_time"

    def test_loads_toolspec_tool(self) -> None:
        """A TOOL_SPEC module is loaded (e.g. file_read)."""
        tools = load_tools_from_names(["file_read"])
        assert len(tools) >= 1
        assert tools[0].tool_name == "file_read"

    def test_loads_multiple_tools(self) -> None:
        """Multiple tool names are loaded together."""
        tools = load_tools_from_names(["current_time", "file_read"])
        names = {t.tool_name for t in tools}
        assert "current_time" in names
        assert "file_read" in names

    def test_raises_on_missing_module(self) -> None:
        """An error is raised for a non-existent module."""
        with pytest.raises((ImportError, AttributeError)):
            load_tools_from_names(["nonexistent_tool_xyz_999"])

    def test_empty_list_returns_empty(self) -> None:
        """An empty names list returns no tools."""
        assert load_tools_from_names([]) == []

    def test_tool_has_valid_spec(self) -> None:
        """Loaded tools have a well-formed tool_spec."""
        tools = load_tools_from_names(["current_time"])
        spec = tools[0].tool_spec
        assert "name" in spec
        assert "description" in spec
        assert "inputSchema" in spec
        assert "json" in spec["inputSchema"]


# ---------------------------------------------------------------------------
# load_tools_from_paths
# ---------------------------------------------------------------------------


class TestLoadToolsFromPaths:
    """Tests for ``load_tools_from_paths``."""

    def test_loads_tool_from_file(self) -> None:
        """A .py file with an @tool-decorated function is discovered."""
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(SAMPLE_DECORATED_TOOL)
            f.flush()
            tmp_path = f.name

        try:
            tools = load_tools_from_paths([tmp_path])
            assert len(tools) == 1
            assert tools[0].tool_name == "test_echo"
        finally:
            os.unlink(tmp_path)

    def test_raises_on_missing_file(self) -> None:
        """An error is raised for a non-existent path."""
        with pytest.raises((FileNotFoundError, ImportError)):
            load_tools_from_paths(["/tmp/does_not_exist_abc123.py"])

    def test_empty_list_returns_empty(self) -> None:
        """An empty paths list returns no tools."""
        assert load_tools_from_paths([]) == []

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


# ---------------------------------------------------------------------------
# URL helpers
# ---------------------------------------------------------------------------


class TestIsUrl:
    """Tests for ``_is_url``."""

    def test_https_url(self) -> None:
        assert _is_url("https://raw.githubusercontent.com/user/repo/main/tool.py") is True

    def test_http_url(self) -> None:
        assert _is_url("http://example.com/tool.py") is True

    def test_local_path(self) -> None:
        assert _is_url("/home/user/tool.py") is False

    def test_relative_path(self) -> None:
        assert _is_url("./tools/my_tool.py") is False


class TestDownloadToTempfile:
    """Tests for ``_download_to_tempfile`` using a local HTTP server."""

    def _start_server(self, content: str) -> tuple[http.server.HTTPServer, int]:
        """Start a throwaway HTTP server serving *content* on any path."""

        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(content.encode())

            def log_message(self, *args):  # noqa: ARG002
                pass  # silence logs

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, port

    def test_downloads_file(self) -> None:
        """A URL is downloaded to a local temp file."""
        server, port = self._start_server(SAMPLE_DECORATED_TOOL)
        try:
            path = _download_to_tempfile(f"http://127.0.0.1:{port}/my_tool.py")
            assert os.path.exists(path)
            with open(path) as f:
                assert "test_echo" in f.read()
        finally:
            server.shutdown()

    def test_adds_py_extension(self) -> None:
        """If the URL basename doesn't end in .py, .py is appended."""
        server, port = self._start_server("x = 1\n")
        try:
            path = _download_to_tempfile(f"http://127.0.0.1:{port}/no_extension")
            assert path.endswith(".py")
        finally:
            server.shutdown()


# ---------------------------------------------------------------------------
# load_tools_from_paths — URL integration
# ---------------------------------------------------------------------------


class TestLoadToolsFromUrls:
    """Tests for URL support in ``load_tools_from_paths``."""

    def _start_server(self, content: str) -> tuple[http.server.HTTPServer, int]:
        class Handler(http.server.BaseHTTPRequestHandler):
            def do_GET(self):  # noqa: N802
                self.send_response(200)
                self.send_header("Content-Type", "text/plain")
                self.end_headers()
                self.wfile.write(content.encode())

            def log_message(self, *args):  # noqa: ARG002
                pass

        server = http.server.HTTPServer(("127.0.0.1", 0), Handler)
        port = server.server_address[1]
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        return server, port

    def test_loads_tool_from_url(self) -> None:
        """A tool .py served over HTTP is loaded correctly."""
        server, port = self._start_server(SAMPLE_DECORATED_TOOL)
        try:
            tools = load_tools_from_paths([f"http://127.0.0.1:{port}/my_tool.py"])
            assert len(tools) == 1
            assert tools[0].tool_name == "test_echo"
        finally:
            server.shutdown()

    def test_mixed_paths_and_urls(self) -> None:
        """Local paths and URLs can be mixed in the same list."""
        # Local file
        with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False, dir=tempfile.gettempdir()) as f:
            f.write(
                textwrap.dedent("""\
                from strands import tool

                @tool
                def local_tool(x: str) -> str:
                    \"\"\"Local.

                    Args:
                        x: Input

                    Returns:
                        Output
                    \"\"\"
                    return x
            """)
            )
            f.flush()
            local_path = f.name

        # URL
        server, port = self._start_server(SAMPLE_DECORATED_TOOL)
        try:
            tools = load_tools_from_paths([local_path, f"http://127.0.0.1:{port}/remote_tool.py"])
            names = {t.tool_name for t in tools}
            assert "local_tool" in names
            assert "test_echo" in names
        finally:
            server.shutdown()
            os.unlink(local_path)
