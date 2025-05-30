from contextlib import asynccontextmanager
from typing import AsyncIterator, Iterator

import anyio
import click
from mcp import types
from mcp.server.lowlevel import Server

from mcp_server.agent import IFlySparkAgentClient


@asynccontextmanager
async def server_lifespan(server: Server) -> AsyncIterator[dict]:
    """Manage server startup and shutdown lifecycle."""
    # Initialize resources on startup
    print("############# Initializing IFlySparkAgentClient")
    yield {"ifly_spark_agent_client": IFlySparkAgentClient()}


@click.command()
@click.option("--port", default=8000, help="Port to listen on for SSE")
@click.option(
    "--transport",
    type=click.Choice(["stdio", "sse"]),
    default="stdio",
    help="Transport type",
)
def main(port: int, transport: str) -> int:
    app = Server("ifly-spark-agent-mcp", lifespan=server_lifespan)

    @app.call_tool()
    async def handle_call_tool(
            name: str, arguments: dict | None
    ) -> list[types.TextContent | types.ImageContent | types.EmbeddedResource]:
        """
        Process valid tool call requests and convert them to MCP responses
        :param name:        tool name
        :param arguments:   tool arguments
        :return:
        """
        spark_agent_client = app.request_context.lifespan_context["ifly_spark_agent_client"]
        if name not in spark_agent_client.name_idx:
            raise ValueError(f"Invalid tool name: {name}")
        agent = spark_agent_client.agents[spark_agent_client.name_idx[name]]
        if name == "upload_file":
            data = spark_agent_client.upload_file(
                arguments["file"],
            )
        elif agent["kindCode"] and agent["kindCode"] == "SKILL_TOOL":
            data = spark_agent_client.tool_debug(agent, arguments)
        else:
            data = await spark_agent_client.chat_completions(
                agent,
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

    @app.list_tools()
    async def handle_list_tools() -> list[types.Tool]:
        """
        List available tools，and convert them to MCP client can call.
        :return:
        """
        tools = []
        ctx = app.request_context
        agents = ctx.lifespan_context["ifly_spark_agent_client"].agents
        for i, agent in enumerate(agents):
            print(f"########## server list tools for flow-{i}.inputSchema: ", agent["inputSchema"])
            tools.append(
                types.Tool(
                    name=agent["name"],
                    description=agent["description"],
                    inputSchema=agent["inputSchema"],
                )
            )
        print("########## server list tools: ", tools)
        return tools

    if transport == "sse":
        from mcp.server.sse import SseServerTransport
        from starlette.applications import Starlette
        from starlette.routing import Mount, Route

        sse = SseServerTransport("/messages/")

        async def handle_sse(request):
            async with sse.connect_sse(
                    request.scope, request.receive, request._send
            ) as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        starlette_app = Starlette(
            debug=True,
            routes=[
                Route("/sse", endpoint=handle_sse),
                Mount("/messages/", app=sse.handle_post_message),
            ],
        )

        import uvicorn

        uvicorn.run(starlette_app, host="0.0.0.0", port=port)
    else:
        from mcp.server.stdio import stdio_server

        async def arun():
            async with stdio_server() as streams:
                await app.run(
                    streams[0], streams[1], app.create_initialization_options()
                )

        anyio.run(arun)

    return 0
