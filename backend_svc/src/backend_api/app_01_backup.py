import os
import json
import logging
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple

# Setup basic logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_api")

# Import your tool functions (ensure correct import paths)
from backend_svc.src.backend_api.tools.get_weather import get_weather
from backend_svc.src.backend_api.tools.searchxng import searchxng
from backend_svc.src.backend_api.tools.get_date import get_date

app = FastAPI(title="Backend Service")

# Load tool schemas from JSON files relative to this file
base_dir = os.path.dirname(__file__)
get_weather_path = os.path.join(base_dir, "get_weather_tool.json")
searchxng_path = os.path.join(base_dir, "searchxng_tool.json")
get_date_path = os.path.join(base_dir, "get_date_tool.json")

logger.debug(f"Loading tool schema from {get_weather_path}")
with open(get_weather_path) as f:
    get_weather_tool = json.load(f)

logger.debug(f"Loading tool schema from {searchxng_path}")
with open(searchxng_path) as f:
    searchxng_tool = json.load(f)

logger.debug(f"Loading tool schema from {get_date_path}")
with open(get_date_path) as f:
    get_date_tool = json.load(f)



TOOLS = [get_weather_tool, searchxng_tool,get_date_tool]

OLLAMA_URL = "http://host.docker.internal:11434/api/chat"  # Adjust as needed
OLLAMA_MODEL = "granite4:350m"

class ChatRequest(BaseModel):
    message: str
    history: List[Tuple[str, str]] = []

class ChatResponse(BaseModel):
    response: str

def dispatch_tool(tool_name: str, arguments: dict) -> str:
    logger.debug(f"Dispatching tool '{tool_name}' with arguments: {arguments}")
    if tool_name == "get_weather":
        result = get_weather(**arguments)
    elif tool_name == "searchxng":
        result = searchxng(**arguments)
    elif tool_name == "get_date":
        result = get_date()
    else:
        result = f"Unknown tool: {tool_name}"
    logger.debug(f"Tool '{tool_name}' returned: {result}")
    return result

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.debug(f"Received chat request message: {request.message}")
    logger.debug(f"Received chat history: {request.history}")

    # Build conversation history for Ollama in correct message dictionary format
    messages = []
    for human, assistant in request.history:
        # Safety: Ensure human and assistant are strings
        human_str = str(human)
        assistant_str = str(assistant)
        messages.append({"role": "user", "content": human_str})
        messages.append({"role": "assistant", "content": assistant_str})
    messages.append({"role": "user", "content": request.message})

    logger.debug(f"Constructed messages for Ollama: {messages}")

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }

    try:
        ollama_resp = requests.post(OLLAMA_URL, json=payload, timeout=500)
        ollama_resp.raise_for_status()
        ollama_data = ollama_resp.json()

        logger.debug(f"Ollama response data: {ollama_data}")

        tool_calls = ollama_data["message"].get("tool_calls", [])
        logger.debug(f"Tool calls received: {tool_calls}")

        # If no tool calls, return direct content response
        if not tool_calls:
            model_reply = ollama_data["message"]["content"]
            logger.debug(f"Returning direct model reply: {model_reply}")
            return ChatResponse(response=model_reply)

        # Process tool calls
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            func_name = tool_call["function"]["name"]
            args = tool_call["function"]["arguments"]

            tool_result = dispatch_tool(func_name, args)

            # Append proper tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": json.dumps(tool_result)
            })


        # Send updated conversation (with tool outputs) again to Ollama
        payload["messages"] = messages
        logger.debug(f"Sending follow-up request with messages: {messages}")

        ollama_resp_followup = requests.post(OLLAMA_URL, json=payload, timeout=120)
        ollama_resp_followup.raise_for_status()
        ollama_data_followup = ollama_resp_followup.json()

        model_reply = ollama_data_followup["message"]["content"]
        logger.debug(f"Received follow-up model reply: {model_reply}")

        return ChatResponse(response=model_reply)

    except Exception as e:
        logger.error(f"Error communicating with Ollama: {e}", exc_info=True)
        return ChatResponse(response=f"Ollama error: {e}")
