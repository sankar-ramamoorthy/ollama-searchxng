from src.backend_api.tools.searchxng import searchxng

def get_weather(location: str) -> str:
    # Create a query to get weather info for the location
    query = f"weather in {location}"

    # Call the SearchXNG tool to get search results for the weather query
    search_results = searchxng(query)

    # Optionally, parse or summarize search_results to pull out key weather details
    # For simplicity, just return the raw search results here
    return f"Weather information for {location}:\n{search_results}"
