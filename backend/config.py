import os
import json
from typing import Dict, Any

CONFIG_FILE = os.path.join(os.path.dirname(__file__), "config.json")

def load_config() -> Dict[str, Any]:
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r") as f:
                return json.load(f)
        except Exception:
            return {}
    return {}

def save_config(data: Dict[str, Any]):
    with open(CONFIG_FILE, "w") as f:
        json.dump(data, f, indent=2)

def get_api_key() -> str:
    config = load_config()
    return config.get("groq_api_key") or os.environ.get("GROQ_API_KEY", "")