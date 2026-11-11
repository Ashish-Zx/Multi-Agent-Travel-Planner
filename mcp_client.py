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
search_tool = None
aviation_tools = {}


async def initialize_mcp():
    global search_tool
    global aviation_tools

    if search_tool is not None and aviation_tools:
        return 

    tools = await client.get_tools()

    print ("\\nAvailable tools:")

    for tool in tools:
        print(tool.name)

    search_tool = next((tool for tool in tools if tool.name == "tavily_search"), None)
    aviation_tools = {tool.name: tool for tool in tools if tool.name == "list_airlines" or tool.name == "list_airports"}

async def tavily_mcp_search(query: str):
    result = await (await search_tool()).ainvoke(
        {"query": query}
    )
    
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
