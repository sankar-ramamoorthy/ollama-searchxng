import os, json
from typing import Dict, Any

BASE_DIR = os.path.dirname(__file__)

def load_tool_schema(filename: str) -> Dict[str, Any]:
    path = os.path.join(BASE_DIR, filename)
    with open(path) as f:
        return json.load(f)
