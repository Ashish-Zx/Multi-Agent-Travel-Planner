import os
import re
import certifi
from dotenv import load_dotenv
from typing import TypedDict,Annotated
import operator 
import uuid
import psycopg
import asyncio
from psycopg.rows import dict_row
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import(
    AnyMessage,HumanMessage,AIMessage,SystemMessage
)
from langchain_openai import ChatOpenAI
from tools.flight_tool import search_flights
from tools.tavily_tool import tavily_search
# from mcp_client_test import tavily_mcp_search
from mcp_client import tavily_mcp_search,aviation_mcp_call,extract_destination,forecast_mcp_search,weather_mcp_search


load_dotenv()

# Set the CA bundle for SSL verification
os.environ["SSL_CERT_FILE"] = certifi.where()
os.environ["REQUESTS_CA_BUNDLE"] = certifi.where()


def get_database_url():
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        raise ValueError("DATABASE_URL environment variable is not set")

    if "sslmode=" not in database_url:
        seperator = "&" if "?" in database_url else "?"
        database_url += f"{seperator}sslmode=require"
    return database_url

INCEPTION_API_KEY = os.getenv("INCEPTION_API_KEY")
if not INCEPTION_API_KEY:
    raise ValueError("INCEPTION_API_KEY environment variable is not set")


# LLM (Inception Mercury-3 via OpenAI-compatible endpoint)
llm = ChatOpenAI(
    model="mercury-3",
    api_key=INCEPTION_API_KEY,
    base_url="https://api.inceptionlabs.ai/v1",
) 

# STATE

class TravelState(TypedDict):
    messages:Annotated[list[AnyMessage], operator.add]
    user_query:str
    flight_results:str
    hotel_results:str
    weather_results:str
    itinerary:str
    llm_calls:int

#FLIGHT AGENT

# def flight_agent(state: TravelState):
#     query =state["user_query"]
#     flight_data=search_flights(query)

#     return {
#         "flight_results": flight_data,
#         "messages":[
#             AIMessage(content="Flight results fetched")
#         ],
#         "llm_calls": state.get("llm_calls", 0) + 1
#     }
FLIGHT_AGENT_PROMPT="""
You are a travel flight expert.

User Query:
{query}

Airport Information:{airport_data}
Airline Information:{airline_data}

Generate:
1.Likely departure airport
2.Likely arrival airport
3.Airlines serving this route
4.Typical flight duration
5.Estimated airfare range
6.Peak season pricing warning
7.Booking advice
Return concise travel guidance.

"""

def flight_agent(state: TravelState):
    query = state["user_query"]

    try:
        airports = asyncio.run(aviation_mcp_call("list_airports"))

        airlines = asyncio.run(aviation_mcp_call("list_airlines"))

        prompt = FLIGHT_AGENT_PROMPT.format(
            query=query,
            airport_data=str(airports)[:3000],
            airline_data=str(airlines)[:3000]
        )
        response = llm.invoke([
            SystemMessage(content="You are a travel flight expert."),
            HumanMessage(content=prompt)
        ])

        flight_data = response.content
    except Exception as e:
        print(f"Error occurred while fetching flight data: {e}")
        flight_data = "Error occurred while fetching flight data."

    return {
        "flight_results": flight_data,
        "messages": [
            AIMessage(content="Flight results fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }    

#   HOTEL AGENT
def hotel_agent(state: TravelState):
    query = f"Best hotels in {state['user_query']}"
    # hotel_results= tavily_search(query)
    hotel_results= asyncio.run(tavily_mcp_search(query))
    
    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel results fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# Weather
def weather_agent(state: TravelState):
    city = extract_destination(state['user_query'])

    weather_data=asyncio.run(weather_mcp_search(city))
    forecast_data=asyncio.run(forecast_mcp_search(city))

    return{
        "weather_results":f"""
        Current Weather: {weather_data}
        Forecast: {forecast_data}
        """,
        "messages": [
            AIMessage(content="Weather results fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# ITENARY AGENT
def itinerary_agent(state: TravelState):
   prompt = f"Create an itinerary based on the following flight and hotel information and weather information: {state['flight_results']} and {state['hotel_results']} and {state['weather_results']}. Make the itinerary practical,budget-aware, and easy to follow."
   response= llm.invoke(
       [SystemMessage(content="YOU are an expert travel planner."),
        HumanMessage(content=prompt)
       ]
   )
   return{
       "itinerary": response.content,
       "messages": [response],
       "llm_calls": state.get("llm_calls", 0) + 1
   }

# FINAL RESPONSE AGENT
def final_agent(state: TravelState):
   final_prompt=f"""Genearate the final travel response for the user.User Request: {state['user_query']}
   Flight Results: {state['flight_results']}
   Hotel Results: {state['hotel_results']}
   Itinerary: {state['itinerary']} 
   Weather Results: {state['weather_results']}

   Format the final answer beautifully using these section:
   1.Trip Summary
   2.Flight Details
   3.Hotel Details
   4.Weather Details
   5.Day-by-Day Itinerary
   6.Estimated Budget
   7.Final Reccomendations

   Important:
   -Be clear and practical.
   -Mention that live flight api may not provide ticket prices if pricing in unavailable.
   -Keep the response useful for real travel panning
   -Use a professional and friendly tone.
   """
   response=llm.invoke(
       [SystemMessage(content="YOU are an expert AI travel planner assistant."),
        HumanMessage(content=final_prompt)
       ]
   )
   return {
       "messages": [response],
       "llm_calls": state.get("llm_calls", 0) + 1
   }

# GRAPH

graph= StateGraph(TravelState)
graph.add_node("flight_agent", flight_agent)
graph.add_node("hotel_agent", hotel_agent)
graph.add_node("itinerary_agent", itinerary_agent)
graph.add_node("final_agent", final_agent)

graph.add_edge(START, "flight_agent")
graph.add_edge("flight_agent", "hotel_agent")
graph.add_edge("hotel_agent", "itinerary_agent")
graph.add_edge("itinerary_agent", "final_agent")
graph.add_edge("final_agent", END)

# POSTGRES Checkpoints
DATABASE_URL=get_database_url()
_conn=psycopg.connect(
    DATABASE_URL,
    autocommit=True,
    row_factory=dict_row
)

checkpointer =PostgresSaver(_conn)
checkpointer.setup()

travel_graph= graph.compile(checkpointer=checkpointer)

def run_travel_agent(user_input:str,thread_id:str|None=None):
    if not thread_id:
        thread_id=f"user_{uuid.uuid4().hex}"

    config={
        "configurable": {
            "thread_id": thread_id
        }
    }    

    result =travel_graph.invoke(
        {
            "messages":[
                HumanMessage(content=user_input)
            ],
            "user_query": user_input,
            "flight_results": "",
            "hotel_results": "",
            "itinerary": "",
            "llm_calls": 0
        }, 
        config=config
    ) 
    final_answer=result["messages"][-1].content
    return {
        "thread_id": thread_id,
        "answer": final_answer,
        "flight_results": result.get("flight_results", ""),
        "hotel_results": result.get("hotel_results", ""),
        "itinerary": result.get("itinerary", ""),
        "llm_calls": result.get("llm_calls", 0)
    }















