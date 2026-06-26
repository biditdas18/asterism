import json
import os

CONFIG_DIR = os.path.expanduser("~/.asterism")
CONFIG_PATH = os.path.join(CONFIG_DIR, "config.json")

DEFAULTS = {
    "anthropic_api_key": "",
    "extractor_mode": "local",
    "ollama_model": "llama3.2:3b",
    "db_path": "~/.asterism/asterism.db",
}


def load_config() -> dict:
    if not os.path.exists(CONFIG_PATH):
        return dict(DEFAULTS)
    with open(CONFIG_PATH) as f:
        return {**DEFAULTS, **json.load(f)}


def save_config(config: dict):
    os.makedirs(CONFIG_DIR, exist_ok=True)
    with open(CONFIG_PATH, "w") as f:
        json.dump(config, f, indent=2)


def get_db_path() -> str:
    return os.path.expanduser(load_config()["db_path"])


def is_configured() -> bool:
    return bool(load_config().get("anthropic_api_key", "").strip())
