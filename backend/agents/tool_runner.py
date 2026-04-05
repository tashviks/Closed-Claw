"""
Tool runner — creates, saves and executes tools from agent-parsed definitions.
"""
import json
import logging
from typing import AsyncIterator

from tools.executor import execute_tool
from tools.registry import save_user_tool
from core.security import validate_agent_tool_code
from agents import sse

log = logging.getLogger("openclaw.tool_runner")


async def run_tool(name: str, args: dict) -> tuple[dict, AsyncIterator[str]]:
    """Execute an existing tool and yield SSE events."""
    async def _events():
        yield sse.thinking(f"Calling {name}…")
        yield sse.tool_call(name, args)
        result = await execute_tool(name, args)
        yield sse.tool_result(name, result)
        return result

    result = await execute_tool(name, args)
    return result, _events()


async def create_and_run_tool(tool_def: dict):
    """
    Validate, save, and execute a new tool definition.
    Yields SSE events throughout.
    Returns (result, error_message).
    """
    name = tool_def.get("name", "auto_tool").strip()
    code = tool_def.get("code", "").strip()
    description = tool_def.get("description", "")
    arguments = tool_def.get("arguments", {})
    if not isinstance(arguments, dict):
        arguments = {}

    # Sanitize name
    import re
    name = re.sub(r"[^a-z0-9_]", "_", name.lower())[:64] or "auto_tool"

    yield sse.thinking(f"Creating tool: {name}…")

    is_safe, reason = validate_agent_tool_code(code)
    if not is_safe:
        yield sse.error(f"Tool blocked by security: {reason}")
        return

    # Save to registry
    save_user_tool({
        "name": name,
        "description": description,
        "code": code,
        "parameters": {
            "type": "object",
            "properties": {k: {"type": "string"} for k in arguments},
        },
        "enabled": True,
    })
    yield sse.tool_created(name, description)
    yield sse.thinking(f"Running {name}…")
    yield sse.tool_call(name, arguments)

    result = await execute_tool(name, arguments)
    yield sse.tool_result(name, result)

    # Store result on the generator for the caller to read
    create_and_run_tool._last_result = result
