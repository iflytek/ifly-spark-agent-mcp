# ifly-spark-agent-mcp

This is a simple example of using MCP Server to invoke the task chain of the  iFlytek SparkAgent Platform.

## Usage

### Local debugging

Start the server using either stdio (default) or SSE transport:

```bash
# Using stdio transport (default)
uv run ifly-spark-agent-mcp

# Using SSE transport on custom port
uv run ifly-spark-agent-mcp --transport sse --port 8000
```

By default, the server exposes a tool named "upload_file" that accepts one required argument:

- `file`: The path of the uploaded file

### MCP Client Example

Using the MCP client, you can use the tool like this using the STDIO transport:

```python
import asyncio
from mcp.client.session import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client


async def main():
    async with stdio_client(
        StdioServerParameters(command="uv", args=["run", "ifly-spark-agent-mcp"])
    ) as (read, write):
        async with ClientSession(read, write) as session:
            await session.initialize()

            # List available tools
            tools = await session.list_tools()
            print(tools)

            # Call the upload_file tool
            result = await session.call_tool("upload_file", {"file": "/path/to/file"})
            print(result)


asyncio.run(main())

```

### Usage with MCP client

#### Use on Claude
To add a persistent client, add the following to your `claude_desktop_config.json` or `mcp.json` file:

##### 1. Use uv
```json
{
  "mcpServers": {
    "ifly-spark-agent-mcp": {
      "command": "uv",
      "args": [
        "--directory",
        "/path/to/ifly-spark-agent-mcp",
        "run",
        "ifly-spark-agent-mcp"
      ],
      "env": {
        "IFLY_SPARK_AGENT_BASE_URL": "xxxx",
        "IFLY_SPARK_AGENT_APP_ID": "xxxx",
        "IFLY_SPARK_AGENT_APP_SECRET": "xxxx"
      }
    }
  }
}
```

##### 2. Use uvx with github repository
```json
{
    "mcpServers": {
        "ifly-spark-agent-mcp": {
            "command": "uvx",
            "args": [
                "--from",
                "git+https://github.com/iflytek/ifly-spark-agent-mcp",
                "ifly-spark-agent-mcp"
            ],
            "env": {
              "IFLY_SPARK_AGENT_BASE_URL": "xxxx",
              "IFLY_SPARK_AGENT_APP_ID": "xxxx",
              "IFLY_SPARK_AGENT_APP_SECRET": "xxxx"
            }
        }
    }
}
```

