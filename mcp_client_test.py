import os
import asyncio
import certifi
from dotenv import load_dotenv
from langchain_mcp_adapters.client import MultiServerMCPClient

load_dotenv()
TAVILY_API_KEY=os.getenv("TAVILY_API_KEY")

client = MultiServerMCPClient(
    {
        "tavily":{
            "transport":"streamable_http",
            "url":f"https://mcp.tavily.com/mcp?tavilyApikey={TAVILY_API_KEY}"
        }
    }
)

async def get_all_tools():
    tools = await client.get_tools()
    for tool in tools:
        print(tool.name)

async def get_tavily_search_tool():
    tools = await client.get_tools()
    for tool in tools:
        if tool.name == "tavily_search":
            return tool
    return None

async def tavily_mcp_search(query: str):

    result = await (await get_tavily_search_tool()).ainvoke(
        {"query": query}
    )
    print(result)


