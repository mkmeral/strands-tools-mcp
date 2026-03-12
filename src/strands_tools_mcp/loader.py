"""Tool loading logic for strands-tools-mcp.

Uses the Strands SDK's built-in loader to resolve tool strings into ``AgentTool``
instances, handling both ``@tool``-decorated functions (``DecoratedFunctionTool``)
and ``TOOL_SPEC`` module-based tools (``PythonAgentTool``) transparently.

Paths that look like URLs (``http://`` / ``https://``) are downloaded to a
temporary file first, so you can point directly at a raw GitHub link or any
other hosted ``.py`` file.
"""

import logging
import os
import tempfile
import urllib.request

from strands.tools.loader import load_tools_from_file_path, load_tools_from_module_path
from strands.types.tools import AgentTool

logger = logging.getLogger(__name__)


def _is_url(path: str) -> bool:
    """Return ``True`` if *path* looks like an HTTP(S) URL."""
    return path.startswith("http://") or path.startswith("https://")


def _download_to_tempfile(url: str) -> str:
    """Download *url* to a temporary ``.py`` file and return its path.

    The caller is responsible for the lifetime of the file (it lives in the
    system temp directory and will be cleaned up on reboot at the latest).

    Raises:
        urllib.error.URLError: On network errors.
        ValueError: If the response doesn't look like a Python file.
    """
    # Derive a sensible module name from the URL's basename
    basename = os.path.basename(url.split("?")[0].split("#")[0])
    if not basename.endswith(".py"):
        basename = f"{basename}.py"

    tmp_dir = tempfile.gettempdir()
    dest = os.path.join(tmp_dir, f"strands_mcp_{basename}")

    logger.info("Downloading tool from %s -> %s", url, dest)
    urllib.request.urlretrieve(url, dest)  # noqa: S310
    return dest


def load_tools_from_names(names: list[str]) -> list[AgentTool]:
    """Load Strands tools by module name from the ``strands-agents-tools`` package.

    Each *name* is resolved as ``strands_tools.<name>`` through the SDK's
    ``load_tools_from_module_path``, which discovers both ``@tool``-decorated
    functions and ``TOOL_SPEC`` module-based tools.

    Args:
        names: Tool module names (e.g. ``["current_time", "file_read"]``).

    Returns:
        A list of :class:`AgentTool` instances.

    Raises:
        AttributeError: If a module is not a valid tool module.
        ImportError: If a module cannot be found.
    """
    tools: list[AgentTool] = []
    for name in names:
        module_path = f"strands_tools.{name}"
        loaded = load_tools_from_module_path(module_path)
        for t in loaded:
            logger.info("Loaded tool '%s' from %s (%s)", t.tool_name, module_path, type(t).__name__)
        tools.extend(loaded)
    return tools


def load_tools_from_paths(paths: list[str]) -> list[AgentTool]:
    """Load Strands tools from local file paths **or** URLs.

    Each entry in *paths* can be:

    * A local file path (absolute or relative) — loaded directly.
    * An ``http://`` or ``https://`` URL — downloaded to a temp file first,
      then loaded.  This lets you point at raw GitHub links, gists, etc.

    Uses the SDK's ``load_tools_from_file_path`` which handles both
    ``@tool``-decorated and ``TOOL_SPEC`` module-based tools.

    Args:
        paths: File paths or URLs to ``.py`` tool files.

    Returns:
        A list of :class:`AgentTool` instances.

    Raises:
        FileNotFoundError: If a local file does not exist.
        ImportError: If a module cannot be loaded.
        urllib.error.URLError: If a URL cannot be fetched.
    """
    tools: list[AgentTool] = []
    for entry in paths:
        if _is_url(entry):
            filepath = _download_to_tempfile(entry)
        else:
            filepath = entry

        loaded = load_tools_from_file_path(filepath)
        for t in loaded:
            logger.info("Loaded tool '%s' from %s (%s)", t.tool_name, entry, type(t).__name__)
        tools.extend(loaded)
    return tools
