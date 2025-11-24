# src/backend_api/tools/__init__.py

from .get_weather import get_weather
from .get_date import get_date
from .searchxng import searchxng
from .tool_schemas import load_tool_schema

# Load the tool schemas (JSON files inside tools/)
get_weather_tool = load_tool_schema("get_weather_tool.json")
searchxng_tool = load_tool_schema("searchxng_tool.json")
get_date_tool = load_tool_schema("get_date_tool.json")

# The list passed to Ollama during the initial request
TOOLS = [get_weather_tool, searchxng_tool, get_date_tool]


def dispatch_tool(tool_name: str, arguments: dict):
    """
    Dispatches the tool call produced by the LLM
    into the appropriate Python function.
    """

    if tool_name == "get_weather":
        return get_weather(**arguments)

    elif tool_name == "searchxng":
        return searchxng(**arguments)

    elif tool_name == "get_date":
        # Your function takes no arguments
        return get_date()

    return {"error": f"Unknown tool: {tool_name}"}
