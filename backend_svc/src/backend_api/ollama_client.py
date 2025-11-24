import requests

OLLAMA_URL = "http://host.docker.internal:11434/api/chat"
OLLAMA_MODEL = "granite4:350m"

def call_ollama(messages: list, tools: list = None, stream: bool = False):
    payload = {
        "model": OLLAMA_MODEL,
        "messages": messages,
        "stream": stream
    }
    if tools:
        payload["tools"] = tools
    resp = requests.post(OLLAMA_URL, json=payload, timeout=500)
    resp.raise_for_status()
    return resp.json()
