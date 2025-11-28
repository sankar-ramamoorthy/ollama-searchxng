import os
import json
import logging
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple, Dict, Any

# Setup logging
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_api")

# Import your tool functions
from backend_svc.src.backend_api.tools.get_weather import get_weather
from backend_svc.src.backend_api.tools.searchxng import searchxng
from backend_svc.src.backend_api.tools.get_date import get_date


# ---------------------------------------------------------
# Load tool schemas
# ---------------------------------------------------------
app = FastAPI(title="Backend Service")

base_dir = os.path.dirname(__file__)

def load_tool_schema(filename: str) -> Dict[str, Any]:
    path = os.path.join(base_dir, filename)
    logger.debug(f"Loading tool schema from {path}")
    with open(path) as f:
        return json.load(f)

get_weather_tool = load_tool_schema("get_weather_tool.json")
searchxng_tool   = load_tool_schema("searchxng_tool.json")
get_date_tool    = load_tool_schema("get_date_tool.json")

TOOLS = [get_weather_tool, searchxng_tool, get_date_tool]


# ---------------------------------------------------------
# Config
# ---------------------------------------------------------
OLLAMA_URL = "http://host.docker.internal:11434/api/chat"
OLLAMA_MODEL = "granite4:350m"


# ---------------------------------------------------------
# Models
# ---------------------------------------------------------
class ChatRequest(BaseModel):
    message: str
    history: List[Tuple[str, str]] = []

class ChatResponse(BaseModel):
    response: str


# ---------------------------------------------------------
# Tool dispatcher
# ---------------------------------------------------------
def dispatch_tool(tool_name: str, arguments: dict) -> Any:
    logger.debug(f"Dispatching tool '{tool_name}' with arguments: {arguments}")

    try:
        if tool_name == "get_weather":
            return get_weather(**arguments)

        elif tool_name == "searchxng":
            return searchxng(**arguments)

        elif tool_name == "get_date":
            # no args expected
            return get_date()

        else:
            return {"error": f"Unknown tool: {tool_name}"}

    except Exception as e:
        logger.error(f"Error inside tool '{tool_name}': {e}", exc_info=True)
        return {"error": str(e)}


# ---------------------------------------------------------
# Chat endpoint
# ---------------------------------------------------------
@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):

    logger.debug(f"Received chat request message: {request.message}")
    logger.debug(f"Received chat history: {request.history}")

    # Build conversation for Ollama
    messages = []
    for user_msg, assistant_msg in request.history:
        messages.append({"role": "user", "content": str(user_msg)})
        messages.append({"role": "assistant", "content": str(assistant_msg)})

    # Add latest user message
    messages.append({"role": "user", "content": request.message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }

    try:
        # -----------------------------------------------------
        # 1. First call - model may request tools
        # -----------------------------------------------------
        ollama_resp = requests.post(OLLAMA_URL, json=payload, timeout=500)
        ollama_resp.raise_for_status()
        model_output = ollama_resp.json()

        logger.debug(f"Ollama response data: {model_output}")

        assistant_msg = model_output.get("message", {})
        tool_calls = assistant_msg.get("tool_calls", [])

        # No tool calls? Then send the assistant text
        if not tool_calls:
            result = assistant_msg.get("content", "")
            return ChatResponse(response=result)

        # -----------------------------------------------------
        # 2. Add assistant tool_call message to history
        # -----------------------------------------------------
        messages.append(assistant_msg)

        # -----------------------------------------------------
        # 3. Process each tool call
        # -----------------------------------------------------
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            func = tool_call["function"]
            func_name = func["name"]
            func_args = func.get("arguments", {})

            tool_result = dispatch_tool(func_name, func_args)

            # Granite requires an assistant acknowledgment first
            messages.append({
                "role": "assistant",
                "content": ""
            })

            # Tool result message
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": json.dumps(tool_result)
            })

        # -----------------------------------------------------
        # 4. Follow-up call with tool results
        # -----------------------------------------------------
        followup_payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }

        followup_resp = requests.post(OLLAMA_URL, json=followup_payload, timeout=500)
        followup_resp.raise_for_status()
        follow_data = followup_resp.json()

        final_text = follow_data.get("message", {}).get("content", "")

        return ChatResponse(response=final_text)

    except Exception as e:
        logger.error(f"Ollama communication error: {e}", exc_info=True)
        return ChatResponse(response=f"Ollama error: {e}")
