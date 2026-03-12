# strands-tools-mcp

Expose [Strands Agents](https://github.com/strands-agents/sdk-python) tools as an MCP server via stdio transport, so any MCP client (Kiro, Claude Desktop, etc.) can use them.

Supports both `@tool`-decorated functions and `TOOL_SPEC` module-based tools from the `strands-agents-tools` package, as well as custom tool files.

## Installation

```bash
pip install strands-tools-mcp
```

Or from source:

```bash
git clone https://github.com/mkmeral/strands-tools-mcp.git
cd strands-tools-mcp
pip install -e ".[dev]"
```

## Configuration

Configure which tools to expose via environment variables:

| Variable | Description | Example |
|---|---|---|
| `STRANDS_TOOLS` | Comma-separated tool names from the `strands-agents-tools` package | `shell,http_request,current_time,file_read` |
| `STRANDS_TOOLS_PATHS` | Comma-separated file paths **or URLs** to custom `.py` tool files | `/path/to/my_tool.py,https://raw.githubusercontent.com/user/repo/main/tool.py` |

Both variables can be used together. At least one must be set.

## Usage

### As a CLI

```bash
STRANDS_TOOLS=current_time,shell strands-tools-mcp
```

### In Kiro / Claude Desktop MCP Config

Add to your MCP configuration file:

```json
{
  "mcpServers": {
    "strands-tools": {
      "command": "strands-tools-mcp",
      "env": {
        "STRANDS_TOOLS": "shell,http_request,file_read,file_write"
      }
    }
  }
}
```

### With Custom Tools

You can combine built-in Strands tools with your own custom tool files:

```json
{
  "mcpServers": {
    "my-tools": {
      "command": "strands-tools-mcp",
      "env": {
        "STRANDS_TOOLS": "current_time",
        "STRANDS_TOOLS_PATHS": "/path/to/my_tool.py"
      }
    }
  }
}
```

### With Remote Tools (URLs)

Point directly at raw GitHub links, gists, or any hosted `.py` file:

```json
{
  "mcpServers": {
    "remote-tools": {
      "command": "strands-tools-mcp",
      "env": {
        "STRANDS_TOOLS_PATHS": "https://raw.githubusercontent.com/user/repo/main/my_tool.py"
      }
    }
  }
}
```

Local paths and URLs can be mixed in `STRANDS_TOOLS_PATHS`.

Custom tool files should use the `@tool` decorator from `strands`:

```python
from strands import tool

@tool
def my_custom_tool(message: str) -> str:
    """A custom tool that processes a message.

    Args:
        message: The message to process

    Returns:
        The processed message
    """
    return f"Processed: {message}"
```

## How It Works

The server uses the Strands SDK's built-in tool loader to discover tools, then exposes them via the MCP protocol's stdio transport using the raw `mcp` library (no FastMCP). Both tool patterns are supported:

- **`@tool` decorated functions** (`DecoratedFunctionTool`) — e.g. `current_time`, `shell`, `calculator`
- **`TOOL_SPEC` module-based tools** (`PythonAgentTool`) — e.g. `file_read`, `file_write`, `http_request`, `python_repl`

All tools are invoked through the unified `AgentTool.stream()` interface, so both types work identically.

## Development

```bash
# Install in dev mode
pip install -e ".[dev]"

# Run tests
pytest tests/ -v

# Lint and format
ruff check src/ tests/
ruff format src/ tests/
```

## License

Apache-2.0
