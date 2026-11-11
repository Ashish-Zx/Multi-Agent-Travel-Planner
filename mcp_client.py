import os
import asyncio
import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")
AVIATION_STACK_API_KEY=os.getenv("AVIATION_STACK_API_KEY")



client = MultiServerMCPClient(
    {
        "tavily":{
            "transport":"streamable_http",
            "url":f"https://mcp.tavily.com/mcp?tavilyApikey={TAVILY_API_KEY}"
        },
        "Aviationstack":{
            "transport":"stdio",
            "command":"uvx",
            "args":[
                "aviationstack-mcp"
            ],
            "env":{
                "AVIATION_STACK_API_KEY": AVIATION_STACK_API_KEY
            }
        }
    }
)

async def get_all_tools():
    tools = await client.get_tools()
    for tool in tools:
        print(tool.name)

# Tavily and aviation tools
_tavily_tool = None
aviation_tools = {}


async def _get_tavily_tool():
    """Return the cached Tavily search MCP tool, initializing it on first use."""
    global _tavily_tool

    if _tavily_tool is not None:
        return _tavily_tool

    tools = await client.get_tools()

    print("\nAvailable tools:")
    for tool in tools:
        print(tool.name)

    _tavily_tool = next(
        (tool for tool in tools if tool.name.lower() == "tavily_search"),
        None,
    )
    if _tavily_tool is None:
        available = ", ".join(tool.name for tool in tools)
        raise RuntimeError(
            f"'tavily_search' tool not found on the Tavily MCP server. "
            f"Available tools: [{available}]"
        )

    return _tavily_tool


async def initialize_mcp():
    """Preload the MCP tools (Tavily search + Aviationstack)."""
    global aviation_tools

    await _get_tavily_tool()

    tools = await client.get_tools()
    aviation_tools = {
        tool.name: tool
        for tool in tools
        if tool.name in ("list_airlines", "list_airports")
    }


async def tavily_mcp_search(query: str):
    tool = await _get_tavily_tool()
    result = await tool.ainvoke({"query": query})
    return result

async def aviation_mcp_call(
        took_name:str,
        tool_args:dict=None):
    tools = await client.get_tools()

    tool = next((t for t in tools if t.name == took_name), None)

    if tool is None:
        raise ValueError(f"Tool {took_name} not found")

    result = await tool.ainvoke(tool_args or {})
    return result
