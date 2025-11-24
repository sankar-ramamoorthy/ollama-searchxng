# src/backend_api/app.py
from fastapi import FastAPI
from pydantic import BaseModel
from typing import List, Tuple
import logging, json

from src.backend_api.tools import TOOLS, dispatch_tool
from src.backend_api.prompts import (
    build_initial_system_prompt,
    build_followup_system_prompt
)
from src.backend_api.ollama_client import call_ollama
from src.backend_api.utils import summarize_tool_results

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

    # Build messages for initial call
    initial_system_prompt = build_initial_system_prompt(request.message)

    # Only include past LLM responses (not tool outputs!)
    messages = [{"role": "system", "content": initial_system_prompt}]
    for user_msg, assistant_msg in request.history:
        messages.append({"role": "user", "content": user_msg})
        messages.append({"role": "assistant", "content": assistant_msg})

    # Current user message
    messages.append({"role": "user", "content": request.message})
    logger.debug(f"initial_messages: {messages}")

    try:
        # ---- Step 1: Initial LLM call ----
        initial_resp = call_ollama(messages, tools=TOOLS)
        logger.debug(f"initial_resp: {initial_resp}")

        assistant_msg = initial_resp.get("message", {})
        tool_calls = assistant_msg.get("tool_calls", [])

        # OPTION B — Only ONE tool call allowed
        if not tool_calls:
            final_answer = assistant_msg.get("content", "")
            return ChatResponse(response=final_answer)

        tool_call = tool_calls[0]  # Only first tool call is supported
        tool_name = tool_call["function"]["name"]
        tool_args = tool_call["function"].get("arguments", {})

        # ---- Step 2: Run the tool ----
        tool_output = dispatch_tool(tool_name, tool_args)
        logger.debug(f"Tool result: {tool_name} {tool_args} -> {tool_output}")

        # Summarize for the follow-up pass
        summarized_tool_text = summarize_tool_results(tool_output, request.message)

        # ---- Step 3: Follow-up LLM call ----
        past_llm_history = "\n".join([f"User: {u}\nAssistant: {a}" for u, a in request.history])

        followup_prompt = build_followup_system_prompt(
            latest_user_message=request.message,
            summarized_tool_results=summarized_tool_text,
            chat_history=past_llm_history
        )

        followup_messages = [
            {"role": "system", "content": followup_prompt},
            {"role": "user", "content": request.message},
            {
                "role": "tool",
                "tool_call_id": tool_call["id"],
                "content": json.dumps(tool_output)
            }
        ]

        logger.debug(f"followup_messages: {followup_messages}")

        followup_resp = call_ollama(followup_messages)
        logger.debug(f"followup_resp: {followup_resp}")

        final_answer = followup_resp.get("message", {}).get("content", "")
        return ChatResponse(response=final_answer)

    except Exception as e:
        logger.error(f"Ollama error: {e}", exc_info=True)
        return ChatResponse(response=f"Ollama error: {e}")
