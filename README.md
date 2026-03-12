# strands-tools-mcp

Expose [Strands Agents](https://github.com/strands-agents/sdk-python) tools as an MCP server using [FastMCP](https://github.com/jlowin/fastmcp), so any MCP client (Kiro, Claude Desktop, etc.) can use them.

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
| `STRANDS_TOOLS_PATHS` | Comma-separated file paths to custom `.py` tool files | `/path/to/my_tool.py,/path/to/another.py` |

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
