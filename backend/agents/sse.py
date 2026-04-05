"""SSE event helpers — single source of truth for all event types."""
import json
import logging

log = logging.getLogger("openclaw")


def evt(event_type: str, **kwargs) -> str:
    return "data: " + json.dumps({"type": event_type, **kwargs}) + "\n\n"


def thinking(msg: str) -> str:
    log.info("[THINK] %s", msg)
    return evt("thinking", message=msg)


def token(content: str) -> str:
    return evt("token", content=content)


def tool_call(name: str, args: dict) -> str:
    log.info("[TOOL_CALL] %s %s", name, str(args)[:100])
    return evt("tool_call", name=name, args=args)


def tool_result(name: str, result) -> str:
    log.info("[TOOL_RESULT] %s -> %s", name, str(result)[:150])
    return evt("tool_result", name=name, result=result)


def tool_created(name: str, description: str) -> str:
    log.info("[TOOL_CREATED] %s", name)
    return evt("tool_created", name=name, description=description)


def error(msg: str) -> str:
    log.error("[ERROR] %s", msg)
    return evt("error", message=msg)


def done() -> str:
    return evt("done")
