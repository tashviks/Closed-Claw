"""
Usage tracking — token counts and cost estimation per message.
"""
import json
import os
from datetime import datetime
from core.storage import load_json, save_json

USAGE_FILE = "usage.json"

# Cost per 1M tokens (input/output) in USD — approximate, update as needed
PRICING: dict[str, dict] = {
    "gpt-4o": {"input": 2.50, "output": 10.00},
    "gpt-4o-mini": {"input": 0.15, "output": 0.60},
    "claude-opus-4-5": {"input": 15.00, "output": 75.00},
    "claude-sonnet-4-5": {"input": 3.00, "output": 15.00},
    "claude-3-5-sonnet": {"input": 3.00, "output": 15.00},
    "claude-3-haiku": {"input": 0.25, "output": 1.25},
    "gemini-2.5-flash": {"input": 0.075, "output": 0.30},
    "gemini-2.5-pro": {"input": 1.25, "output": 10.00},
    "gemini-2.0-flash": {"input": 0.075, "output": 0.30},
    "mistral-large-latest": {"input": 2.00, "output": 6.00},
    "llama-3.3-70b-versatile": {"input": 0.59, "output": 0.79},
}


def estimate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """Estimate cost in USD."""
    # Find pricing by partial match
    pricing = None
    for key, p in PRICING.items():
        if key in model_name:
            pricing = p
            break
    if not pricing:
        return 0.0
    return (input_tokens * pricing["input"] + output_tokens * pricing["output"]) / 1_000_000


def record_usage(model: str, input_tokens: int, output_tokens: int, session_id: str = ""):
    data = load_json(USAGE_FILE, {"total_tokens": 0, "total_cost": 0.0, "sessions": {}})
    cost = estimate_cost(model, input_tokens, output_tokens)
    total = input_tokens + output_tokens

    data["total_tokens"] = data.get("total_tokens", 0) + total
    data["total_cost"] = round(data.get("total_cost", 0.0) + cost, 6)

    if session_id:
        if session_id not in data["sessions"]:
            data["sessions"][session_id] = {"tokens": 0, "cost": 0.0}
        data["sessions"][session_id]["tokens"] += total
        data["sessions"][session_id]["cost"] = round(
            data["sessions"][session_id].get("cost", 0.0) + cost, 6
        )

    save_json(USAGE_FILE, data)
    return {"tokens": total, "cost": cost, "input": input_tokens, "output": output_tokens}


def get_usage_summary() -> dict:
    return load_json(USAGE_FILE, {"total_tokens": 0, "total_cost": 0.0, "sessions": {}})
