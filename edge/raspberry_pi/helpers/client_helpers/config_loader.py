import json
import os
from pathlib import Path

CONFIG_PATH = Path("edge/raspberry_pi/config.json")

def load_config():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)

    config["tomtom_api_key"] = os.getenv("TOMTOM_API_KEY") or config.get("tomtom_api_key")
    return config