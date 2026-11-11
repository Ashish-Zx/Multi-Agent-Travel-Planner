from tools.tavily_tool import tavily_search
from backend import run_travel_agent
from mcp_client import get_all_tools
import asyncio

# res=tavily_search("Best hotels in Kathmandu")
# print(res)

# result = run_travel_agent("Find the proper plan to travel to Paris for 3 days from Kathmandu Nepal")
# print(result["answer"])

if __name__ == "__main__":
    asyncio.run(get_all_tools())
    # asyncio.run(tavily_mcp_search("Best hotels in Kathmandu"))
