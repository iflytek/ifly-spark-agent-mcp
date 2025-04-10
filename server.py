import asyncio
from contextlib import asynccontextmanager
from typing import AsyncIterator, Iterator

import mcp
from mcp import types
from mcp.server import Server, InitializationOptions, NotificationOptions

from agent import IflySparkAgentClient


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup
    yield {"ifly_spark_agent_client": IflySparkAgentClient()}


server = Server("ifly_spark_agent_mcp", lifespan=server_lifespan)


@server.list_tools()
async def handle_list_tools() -> list[types.Tool]:
    """
    List available tools，and convert them to MCP client can call.
    :return:
    """
    tools = []
    ctx = server.request_context
    for i, flow in enumerate(ctx.lifespan_context["ifly_client"].flows):
        tools.append(
            types.Tool(
                name=flow.name,
                description=flow.description,
                inputSchema=flow.input_schema,
            )
        )
    return tools

@server.call_tool()
async def handle_call_tool(
        name: str, arguments: dict | None
) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
    """
    Process valid tool call requests and convert them to MCP responses
    :param name:        tool name
    :param arguments:   tool arguments
    :return:
    """
    ifly_client = server.request_context.lifespan_context["ifly_client"]
    if name not in ifly_client.name_idx:
        raise ValueError(f"Invalid tool name: {name}")
    flow = ifly_client.flows[ifly_client.name_idx[name]]
    if name == SysTool.SYS_UPLOAD_FILE.value:
        data = ifly_client.upload_file(
            flow.api_key,
            arguments["file"],
        )
    else:
        data = ifly_client.chat_message(
            flow,
            arguments,
        )
    mcp_out = []

    if isinstance(data, Iterator):
        for res in data:
            mcp_out.append(
                types.TextContent(
                    type='text',
                    text=res
                )
            )
    else:
        mcp_out.append(
            types.TextContent(
                type='text',
                text=data
            )
        )
    return mcp_out


async def main():
    # Run the server using stdin/stdout streams
    async with mcp.server.stdio.stdio_server() as (read_stream, write_stream):
        await server.run(
            read_stream,
            write_stream,
            InitializationOptions(
                server_name="ifly_spark_agent_mcp",
                server_version="0.1.0",
                capabilities=server.get_capabilities(
                    notification_options=NotificationOptions(),
                    experimental_capabilities={},
                ),
            ),
        )


if __name__ == "__main__":
    asyncio.run(main())
