from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import logging, json

from src.backend_api.tools import TOOLS, dispatch_tool
from src.backend_api.prompts import build_initial_system_prompt, build_followup_system_prompt
from src.backend_api.ollama_client import call_ollama

logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger("backend_api")

app = FastAPI(title="Backend Service")

class ChatRequest(BaseModel):
    message: str
    history: List[Tuple[str, str]] = []

class ChatResponse(BaseModel):
    response: str

@app.post("/chat", response_model=ChatResponse)
async def chat_endpoint(request: ChatRequest):
    logger.debug(f"Received message: {request.message}")
    logger.debug(f"Chat history: {request.history}")

    # --- Build messages for initial call ---
    system_prompt = build_initial_system_prompt(request.message)
    messages = [{"role": "system", "content": system_prompt}]
    for user_msg, assistant_msg in request.history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})
    messages.append({"role": "user", "content": request.message})

    try:
        # Step 1: Initial call to Ollama
        ollama_resp = call_ollama(messages, tools=TOOLS)
        assistant_msg = ollama_resp.get("message", {})
        tool_calls = assistant_msg.get("tool_calls", [])

        # If no tool calls, return content directly
        if not tool_calls:
            return ChatResponse(response=assistant_msg.get("content", ""))

        # Step 2: Dispatch each tool
        for tool_call in tool_calls:
            tool_id = tool_call["id"]
            func = tool_call["function"]
            func_name = func["name"]
            func_args = func.get("arguments", {})

            tool_result = dispatch_tool(func_name, func_args)
            logger.debug(f"Tool result: {func_name} {func_args} -> {tool_result}")

            messages.append({
                "role": "tool",
                "tool_call_id": tool_id,
                "content": json.dumps(tool_result)
            })

        # Step 3: Follow-up call with tool results
        chat_history_str = "\n".join([f"{u}: {a}" for u, a in request.history])
        followup_prompt = build_followup_system_prompt(
            latest_user_message=request.message,
            current_tool_results=json.dumps(tool_result),
            chat_history=chat_history_str
        )

        followup_messages = [{"role": "system", "content": followup_prompt}]
        followup_messages.append({"role": "user", "content": request.message})
        followup_messages.append({"role": "tool", "tool_call_id": tool_id, "content": json.dumps(tool_result)})

        followup_resp = call_ollama(followup_messages)
        final_text = followup_resp.get("message", {}).get("content", "")
        return ChatResponse(response=final_text)

    except Exception as e:
        logger.error(f"Ollama error: {e}", exc_info=True)
        return ChatResponse(response=f"Ollama error: {e}")
