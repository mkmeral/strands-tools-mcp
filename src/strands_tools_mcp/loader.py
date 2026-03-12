"""Tool loading logic for strands-tools-mcp.

Loads Strands Agents tools from package names (strands-agents-tools) and from
custom file paths, returning DecoratedFunctionTool instances.
"""

import importlib
import importlib.util
import logging
import os
import sys
from typing import Any

logger = logging.getLogger(__name__)


def load_tools_from_names(names: list[str]) -> list[Any]:
    """Load Strands tools by name from the strands-agents-tools package.

    Each name corresponds to a module under ``strands_tools``. For example,
    the name ``"current_time"`` imports ``strands_tools.current_time`` and
    discovers any ``DecoratedFunctionTool`` instances defined in the module.

    Args:
        names: Tool module names to import (e.g. ``["current_time", "shell"]``).

    Returns:
        A list of ``DecoratedFunctionTool`` instances found in the modules.

    Raises:
        ImportError: If a module cannot be imported.
    """
    from strands.tools.decorator import DecoratedFunctionTool

    tools: list[Any] = []
    for name in names:
        try:
            module = importlib.import_module(f"strands_tools.{name}")
            for attr_name in dir(module):
                attr = getattr(module, attr_name)
                if isinstance(attr, DecoratedFunctionTool):
                    tools.append(attr)
                    logger.info("Loaded tool '%s' from strands_tools.%s", attr.tool_name, name)
        except ImportError as e:
            logger.error("Failed to import strands_tools.%s: %s", name, e)
            raise
    return tools


def load_tools_from_paths(paths: list[str]) -> list[Any]:
    """Load Strands tools from Python file paths.

    Each path should point to a ``.py`` file containing one or more functions
    decorated with ``@tool`` from the ``strands`` package.

    Args:
        paths: File paths to tool Python files.

    Returns:
        A list of ``DecoratedFunctionTool`` instances found in the files.

    Raises:
        FileNotFoundError: If a file path does not exist.
        ImportError: If a module cannot be loaded from a file.
    """
    from strands.tools.decorator import DecoratedFunctionTool

    tools: list[Any] = []
    for filepath in paths:
        filepath = os.path.expanduser(filepath)
        if not os.path.exists(filepath):
            raise FileNotFoundError(f"Tool file not found: {filepath}")

        module_name = os.path.basename(filepath).split(".")[0]
        spec = importlib.util.spec_from_file_location(module_name, os.path.abspath(filepath))
        if not spec or not spec.loader:
            raise ImportError(f"Could not load module from {filepath}")

        module = importlib.util.module_from_spec(spec)
        sys.modules[module_name] = module
        spec.loader.exec_module(module)

        for attr_name in dir(module):
            attr = getattr(module, attr_name)
            if isinstance(attr, DecoratedFunctionTool):
                tools.append(attr)
                logger.info("Loaded tool '%s' from %s", attr.tool_name, filepath)

    return tools
