from tools.tavily_tool import tavily_search
from backend import run_travel_agent

# res=tavily_search("Best hotels in Kathmandu")
# print(res)

result = run_travel_agent("Find the proper plan to travel to Paris for 3 days from Kathmandu Nepal")
print(result["answer"])