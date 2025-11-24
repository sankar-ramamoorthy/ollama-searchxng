import os
import json
import logging
import requests
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple, Dict, Any

# ---------------------------------------------------------
# Setup logging
# ---------------------------------------------------------
logging.basicConfig(
    level=logging.DEBUG,
    format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger("backend_api")

# ---------------------------------------------------------
# Import tool functions
# ---------------------------------------------------------
from src.backend_api.get_weather import get_weather
from src.backend_api.searchxng import searchxng
from src.backend_api.get_date import get_date

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
searchxng_tool = load_tool_schema("searchxng_tool.json")
get_date_tool = load_tool_schema("get_date_tool.json")

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

    # -----------------------------------------------------
    # Build conversation history for Ollama with system prompt
    # -----------------------------------------------------
    messages = [
    {
        "role": "system",
        "content": (
            "You are an AI assistant. Here is how you should respond:\n\n"
            "1. The user's **current query** is: '{latest_user_message}'\n"
            "2. Here are the **results returned from tools** (if any):\n"
            "   - Always use this data directly to answer the query.\n"
            "3. Here is the **past conversation history** (for context only):\n"
            "   - Do not let this override the latest query.\n\n"
            "Always answer the user's query clearly, using the tool results above. "
            "Do not give generic fallback answers."
        )
    }
    ]

    for user_msg, assistant_msg in request.history:
        messages.append({"role": "user", "content": str(user_msg)})
        messages.append({"role": "assistant", "content": str(assistant_msg)})

    messages.append({"role": "user", "content": request.message})

    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "tools": TOOLS,
        "stream": False
    }

    try:
        # -------------------------
        # Step 1: First call - model may request tools
        # -------------------------
        ollama_resp = requests.post(OLLAMA_URL, json=payload, timeout=500)
        ollama_resp.raise_for_status()
        model_output = ollama_resp.json()
        logger.debug(f"Ollama response data: {model_output}")

        assistant_msg = model_output.get("message", {})
        tool_calls = assistant_msg.get("tool_calls", [])

        # -------------------------
        # Step 2: If no tool calls, return assistant content
        # -------------------------
        if not tool_calls:
            result = assistant_msg.get("content", "")
            return ChatResponse(response=result)

        # -------------------------
        # Step 3: Process each tool call
        # -------------------------
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            func = tool_call["function"]
            func_name = func["name"]
            func_args = func.get("arguments", {})

            tool_result = dispatch_tool(func_name, func_args)
            logger.debug(f"dispatch_tool result: {func_name} {func_args} :{tool_result}")

            # Append tool result in the format Ollama expects
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": json.dumps(tool_result)
            })

        # -------------------------
        # Step 4: Follow-up call with tool results
        # -------------------------
        followup_payload = {
            "model": OLLAMA_MODEL,
            "messages": messages,
            "stream": False
        }

        logger.debug(f"Follow-up payload: {followup_payload}")

        followup_resp = requests.post(OLLAMA_URL, json=followup_payload, timeout=500)
        followup_resp.raise_for_status()
        follow_data = followup_resp.json()

        final_text = follow_data.get("message", {}).get("content", "")
        return ChatResponse(response=final_text)

    except Exception as e:
        logger.error(f"Ollama communication error: {e}", exc_info=True)
        return ChatResponse(response=f"Ollama error: {e}")
