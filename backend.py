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

    