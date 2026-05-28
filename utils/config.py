"""Shared configuration loader."""
import json
import os

_SECRETS_PATH = os.getenv("SECRETS_PATH", ".secrets")


def load_api_config() -> dict:
    if not os.path.exists(_SECRETS_PATH):
        return {}
    with open(_SECRETS_PATH, "r", encoding="utf-8") as f:
        return json.load(f)
