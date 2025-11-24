import requests
import logging

SEARCHXNG_URL = "http://searchxng_svc:8080/search"  # Use internal Docker network name and port
#SEARCHXNG_URL = "http://host.docker.internal:8181/search"  # Use internal Docker network name and port

logger = logging.getLogger("searchxng")

def searchxng(query: str) -> str:
    try:
        headers1 = {
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
            "SEARXNG_SECRET": "KNVP1nRBAAuGcm3BtKs4lVVxomF9VAeo6JqxEb_T_Uk"  # From your .env
        }
        headers = {
            "User-Agent": "Mozilla/5.0 (compatible; backend_svc/1.0)",
            "Accept": "application/json",
            "Accept-Language": "en-US,en;q=0.9",
            "X-Forwarded-For": "127.0.0.1",
            "X-Real-IP": "127.0.0.1",
            "SEARXNG_SECRET": "KNVP1nRBAAuGcm3BtKs4lVVxomF9VAeo6JqxEb_T_Uk"  # From your .env
        }
        params = {
            'q': query,
            'format': 'json',  # Request JSON output
            'language': 'en',
            'count': 2        # Limit to top 2 results
        }
        #response = requests.get(SEARCHXNG_URL,params=params, timeout=500)
        response = requests.get(SEARCHXNG_URL, headers=headers,params=params, timeout=10)
        response.raise_for_status()
        data = response.json()

        # Extract top 3 results safely
        results = data.get('results', [])[:3]
        if not results:
            return f"No results found for '{query}'."

        result_texts = []
        for i, result in enumerate(results, start=1):
            title = result.get('title', 'No title')
            url = result.get('url', 'No URL')
            snippet = result.get('content', '')[:1200]  # Optional snippet trimming

            entry = f"{i}. {title}\nURL: {url}\nSnippet: {snippet.strip()}\n"
            result_texts.append(entry)

        return "\n".join(result_texts)
    except Exception as e:
        logger.error(f"Error querying SearchXNG for '{query}': {e}", exc_info=True)
        return f"Error querying SearchXNG: {e}"
