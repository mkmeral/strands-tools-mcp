"""FastMCP server that exposes Strands Agents tools over MCP stdio transport.

Configuration is done through environment variables:

- ``STRANDS_TOOLS``: Comma-separated tool names from the ``strands-agents-tools``
  package (e.g. ``"shell,http_request,current_time"``).
- ``STRANDS_TOOLS_PATHS``: Comma-separated file paths to custom ``.py`` tool files
  (e.g. ``"/path/to/my_tool.py,/path/to/another.py"``).

At least one of the two variables must be set.
"""

import logging
import os
import re
import sys
from typing import Any

from fastmcp import FastMCP

from strands_tools_mcp.loader import load_tools_from_names, load_tools_from_paths

logger = logging.getLogger(__name__)

# Mapping from JSON Schema types to Python type names used in code generation.
_JSON_TYPE_TO_PYTHON: dict[str, str] = {
    "string": "str",
    "integer": "int",
    "number": "float",
    "boolean": "bool",
    "array": "list",
    "object": "dict",
}

# Valid Python identifier pattern
_VALID_IDENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")


def _build_handler(strands_tool: Any, schema: dict[str, Any]) -> Any:
    """Dynamically build an async handler function with typed parameters.

    FastMCP requires tool functions to have explicit parameters (no ``**kwargs``).
    This function reads the JSON Schema from the Strands tool and generates a
    function whose signature matches the schema, then delegates to the original
    Strands tool at runtime.

    Args:
        strands_tool: The Strands ``DecoratedFunctionTool`` to wrap.
        schema: The ``inputSchema.json`` dict from the tool spec.

    Returns:
        An async callable with explicit typed parameters.
    """
    properties = schema.get("properties", {})
    required = set(schema.get("required", []))

    # Build parameter strings – required params first, then optional.
    params: list[str] = []
    for pname in sorted(properties, key=lambda p: p not in required):
        if not _VALID_IDENT.match(pname):
            logger.warning("Skipping parameter '%s' – not a valid Python identifier", pname)
            continue
        ptype = _JSON_TYPE_TO_PYTHON.get(properties[pname].get("type", "string"), "str")
        if pname in required:
            params.append(f"{pname}: {ptype}")
        else:
            params.append(f"{pname}: {ptype} = None")

    param_str = ", ".join(params)

    # Generate the handler function source.  ``_call`` is captured in the
    # namespace so the generated code can invoke the Strands tool.
    func_source = f"""\
async def _handler({param_str}) -> str:
    kwargs = {{k: v for k, v in locals().items() if v is not None}}
    return _call(**kwargs)
"""

    def _call(**kwargs: Any) -> str:
        result = strands_tool(**kwargs)
        if isinstance(result, dict):
            content = result.get("content", [])
            texts = [c.get("text", str(c)) for c in content if isinstance(c, dict)]
            return "\n".join(texts) if texts else str(result)
        return str(result)

    namespace: dict[str, Any] = {"_call": _call}
    exec(func_source, namespace)  # noqa: S102
    return namespace["_handler"]


def register_tool(mcp: FastMCP, strands_tool: Any) -> None:
    """Register a single Strands tool as an MCP tool on the server.

    Creates a dynamically-typed async handler function from the tool's input
    schema and registers it with FastMCP.

    Args:
        mcp: The FastMCP server instance.
        strands_tool: A ``DecoratedFunctionTool`` from the Strands SDK.
    """
    spec = strands_tool.tool_spec
    name = spec["name"]
    description = spec.get("description", "")
    schema = spec.get("inputSchema", {}).get("json", {})

    handler = _build_handler(strands_tool, schema)
    handler.__name__ = name
    handler.__doc__ = description

    mcp.tool(name=name, description=description)(handler)


def create_server() -> FastMCP:
    """Create and configure the MCP server with tools from environment variables.

    Reads ``STRANDS_TOOLS`` and ``STRANDS_TOOLS_PATHS``, loads the
    corresponding Strands tools, wraps each one, and registers them on
    a new ``FastMCP`` instance.

    Returns:
        A configured ``FastMCP`` server ready to run.
    """
    mcp = FastMCP("strands-tools-mcp")

    tool_names_env = os.environ.get("STRANDS_TOOLS", "")
    tool_paths_env = os.environ.get("STRANDS_TOOLS_PATHS", "")

    if not tool_names_env and not tool_paths_env:
        logger.error("No tools configured. Set STRANDS_TOOLS and/or STRANDS_TOOLS_PATHS environment variables.")
        sys.exit(1)

    tools: list[Any] = []

    if tool_names_env:
        names = [n.strip() for n in tool_names_env.split(",") if n.strip()]
        tools.extend(load_tools_from_names(names))

    if tool_paths_env:
        paths = [p.strip() for p in tool_paths_env.split(",") if p.strip()]
        tools.extend(load_tools_from_paths(paths))

    for strands_tool in tools:
        register_tool(mcp, strands_tool)

    logger.info("Registered %d tool(s) with MCP server", len(tools))
    return mcp


def main() -> None:
    """Entry point for the ``strands-tools-mcp`` CLI command."""
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    server = create_server()
    server.run(transport="stdio")


if __name__ == "__main__":
    main()
