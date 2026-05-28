"""Shared helpers for LLM response parsing."""
import json
import re


def extract_json_object(raw: str) -> dict | None:
    """Extract the first JSON object from LLM response text."""
    match = re.search(r'\{[^{}]*(?:\{[^{}]*\}[^{}]*)*\}', raw, re.DOTALL)
    if not match:
        return None
    try:
        return json.loads(match.group())
    except json.JSONDecodeError:
        return None
