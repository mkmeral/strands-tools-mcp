"""Tool loading logic for strands-tools-mcp.

Uses the Strands SDK's built-in loader to resolve tool strings into ``AgentTool``
instances, handling both ``@tool``-decorated functions (``DecoratedFunctionTool``)
and ``TOOL_SPEC`` module-based tools (``PythonAgentTool``) transparently.
"""

import logging

from strands.tools.loader import load_tools_from_file_path, load_tools_from_module_path
from strands.types.tools import AgentTool

logger = logging.getLogger(__name__)


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
    """Load Strands tools from Python file paths.

    Uses the SDK's ``load_tools_from_file_path`` which handles both
    ``@tool``-decorated and ``TOOL_SPEC`` module-based tools.

    Args:
        paths: File paths to ``.py`` tool files.

    Returns:
        A list of :class:`AgentTool` instances.

    Raises:
        FileNotFoundError: If a file does not exist.
        ImportError: If a module cannot be loaded.
    """
    tools: list[AgentTool] = []
    for filepath in paths:
        loaded = load_tools_from_file_path(filepath)
        for t in loaded:
            logger.info("Loaded tool '%s' from %s (%s)", t.tool_name, filepath, type(t).__name__)
        tools.extend(loaded)
    return tools
