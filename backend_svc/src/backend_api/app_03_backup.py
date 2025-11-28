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

    messages = []

    # -----------------------------------------------------
    # Build conversation history string
    # -----------------------------------------------------
    chat_history_str = ""
    for user_msg, assistant_msg in request.history:
        chat_history_str += f"User: {user_msg}\nAssistant: {assistant_msg}\n"
    if not chat_history_str:
        chat_history_str = "No past history"

    # -----------------------------------------------------
    # First system message: we will fill in tool results after first model call
    # -----------------------------------------------------
    system_prompt_template_old = (
        "You are an AI assistant. Follow these instructions carefully:\n\n"
        "1. The user's **current query** is: '{latest_user_message}'\n"
        "2. Here are the **results returned from tools for this query**:\n"
        "{current_tool_results}\n"
        "   - ONLY use this data to answer the current query.\n"
        "3. Here is the **past conversation history** (for reference only):\n"
        "{chat_history}\n"
        "   - Do NOT use past tool outputs to answer the current query.\n\n"
        "Always answer clearly, using the tool outputs for the current query. "
        "Do NOT provide generic fallback responses."
    )

    system_prompt_template = (
        "You are an AI assistant with access to three tools:\n\n"
        "1. get_date(): Returns the current date. Use for queries about today's date or day of the week.\n"
        "2. get_weather(location): Returns weather forecasts for a given location. Use for queries about weather, temperature, or forecasts.\n"
        "3. searchxng(query): Returns web search results. Use for general knowledge questions, facts, or any query not covered by the above tools.\n\n"
        "Rules:\n"
        "- Always choose the most relevant tool for the user's current query.\n"
        "- Only call one tool per query unless absolutely necessary.\n"
        "- Use the tool output for the current query to answer it clearly.\n"
        "- Do NOT guess or provide generic fallback answers.\n\n"
        "Example queries and tool to use:\n"
        "- 'What is the weather in Paris?' → get_weather(location='Paris')\n"
        "- 'Who is the president of France?' → searchxng(query='president of France')\n"
        "- 'What is today’s date?' → get_date()\n\n"
        "Current user query: '{latest_user_message}'\n"
        "Results from tools for this query (if any):\n"
        "{current_tool_results}\n\n"
        "Always answer the user's query using only the tool output for this query."
        "Past conversation history (for reference only):\n"
        "{chat_history}\n\n"
    )

    followup_system_prompt = (
        "You are an AI assistant. You already have the output from a tool for the user's current query.\n\n"
        "Rules:\n"
        "- Use the tool output below to answer the user's query clearly.\n"
        "- Do NOT call any tools again.\n"
        "- Ignore past tool outputs from previous queries.\n\n"
        "User's current query: '{latest_user_message}'\n"
        "Tool output for this query:\n{current_tool_results}\n\n"
        "Past conversation history (for reference only):\n{chat_history}\n\n"
        "Answer clearly using only the tool output."
    )



    # -----------------------------------------------------
    # Append initial system message (placeholder for tool results)
    # -----------------------------------------------------
    messages.append({
        "role": "system",
        "content": system_prompt_template.format(
            latest_user_message=request.message,
            current_tool_results="No tools used yet",
            chat_history=chat_history_str
        )
    })

    # Append user message
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
        tool_results_str = ""
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            func = tool_call["function"]
            func_name = func["name"]
            func_args = func.get("arguments", {})

            tool_result = dispatch_tool(func_name, func_args)
            logger.debug(f"dispatch_tool result: {func_name} {func_args} :{tool_result}")

            # Append tool result for the follow-up
            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": json.dumps(tool_result)
            })

            # Build string summary for system prompt
            tool_results_str += f"- {func_name}({func_args}): {tool_result}\n"

        if not tool_results_str:
            tool_results_str = "No tools used"

        # -------------------------
        # Step 4: Follow-up call with tool results
        # -------------------------
        # Update system message with real tool results
        messages[0]["content"] = system_prompt_template.format(
            latest_user_message=request.message,
            current_tool_results=tool_results_str,
            chat_history=chat_history_str
        )

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
