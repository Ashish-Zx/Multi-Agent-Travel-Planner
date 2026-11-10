from pathlib import Path
import traceback
import uvicorn
from fastapi import FastAPI, Path,Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.responses import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
from backend import run_travel_agent



BASE_DIR=Path(__file__).resolve().parent

app= FastAPI(
    title="AI Travel Planning System",
    description="LangGraph Multi-agent Travel Planning With FastAPI Frontend",
    version="1.0.0"
)









