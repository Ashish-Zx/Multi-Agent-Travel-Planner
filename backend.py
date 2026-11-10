import os
import certifi
from dotenv import load_dotenv
from typing import TypedDict,Annotated
import operator 
import uuid
import psycopg
from psycopg.rows import dict_row
from langgraph.graph import StateGraph,START,END
from langgraph.checkpoint.postgres import PostgresSaver
from langchain_core.messages import(
    AnyMessage,HumanMessage,AIMessage,SystemMessage
)
from langchain_groq import ChatGroq
from tools.flight_tool import search_flights
from tools.tavily_tool import tavily_search


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

GROQ_API_KEY = os.getenv("GROQ_API_KEY")
if not GROQ_API_KEY:
    raise ValueError("GROQ_API_KEY environment variable is not set")


# LLM

llm =ChatGroq(
    model= "llama-3.3-70b-versatile",
    api_key=GROQ_API_KEY
)

# STATE

class TravelState(TypedDict):
    messages:Annotated[list[AnyMessage], operator.add]
    user_query:str
    flight_results:str
    hotel_results:str
    itinerary:str
    llm_calls:int

#FLIGHT AGENT

def flight_agent(state: TravelState):
    query =state["user_query"]
    flight_data=search_flights(query)

    return {
        "flight_results": flight_data,
        "messages":[
            AIMessage(content="Flight results fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

#   HOTEL AGENT
def hotel_agent(state: TravelState):
    query = f"Best hotels in {state['user_query']}"
    hotel_results= tavily_search(query)

    return {
        "hotel_results": hotel_results,
        "messages": [
            AIMessage(content="Hotel results fetched")
        ],
        "llm_calls": state.get("llm_calls", 0) + 1
    }

# ITENARY AGENT
def itinerary_agent(state: TravelState):
   prompt = f"Create an itinerary based on the following flight and hotel information: {state['flight_results']} and {state['hotel_results']} Make the itinerary practical,budget-aware, and easy to follow."
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
   Format the final answer beautifully using these section:
   1.Trip Summary
   2.Flight Details
   3.Hotel Details
   4.Day-by-Day Itinerary
   5.Estimated Budget
   6.Final Reccomendations

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
