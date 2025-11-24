# src/backend_api/utils.py

def summarize_tool_results(tool_output, user_query: str) -> str:
    """
    Create a compact summary of tool output so the LLM is not overwhelmed.
    """

    # Weather/date tools return strings
    if isinstance(tool_output, str):
        return f"Tool result: {tool_output}"

    # searchxng returns a dict with "results"
    if isinstance(tool_output, dict) and "results" in tool_output:
        results = tool_output["results"]
        summary_lines = []

        for i, item in enumerate(results[:3], start=1):
            title = item.get("title", "No Title")
            url = item.get("url", "No URL")
            snippet = item.get("snippet", "")

            summary_lines.append(
                f"{i}. {title}\nURL: {url}\nSnippet: {snippet}"
            )

        return "\n\n".join(summary_lines)

    # Unexpected format
    return f"Raw tool output: {tool_output}"
