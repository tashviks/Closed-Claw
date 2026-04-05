"""
Session commands — /new /compact /status /think /usage /export
Inspired by OpenClaw's chat command surface.
"""
import json
import logging
from fastapi import APIRouter
from pydantic import BaseModel
from core.storage import load_json, save_json

log = logging.getLogger("openclaw.commands")
router = APIRouter()

SESSIONS_FILE = "sessions.json"


class CommandRequest(BaseModel):
    session_id: str
    command: str  # e.g. "/compact", "/status", "/think high"
    model: str = "google/gemini-2.5-flash"


@router.post("/")
async def handle_command(req: CommandRequest):
    cmd = req.command.strip().lower()

    if cmd == "/new" or cmd == "/reset":
        return await _cmd_new(req.session_id)

    if cmd == "/compact":
        return await _cmd_compact(req.session_id, req.model)

    if cmd == "/status":
        return await _cmd_status(req.session_id)

    if cmd.startswith("/think"):
        level = cmd.replace("/think", "").strip() or "medium"
        return {"action": "set_thinking", "level": level, "message": f"Thinking level set to: {level}"}

    if cmd.startswith("/usage"):
        mode = cmd.replace("/usage", "").strip() or "tokens"
        return {"action": "set_usage", "mode": mode, "message": f"Usage display: {mode}"}

    if cmd == "/export":
        return await _cmd_export(req.session_id)

    return {"error": f"Unknown command: {cmd}", "available": ["/new", "/compact", "/status", "/think", "/usage", "/export"]}


async def _cmd_new(session_id: str) -> dict:
    data = load_json(SESSIONS_FILE, {"sessions": {}})
    if session_id in data["sessions"]:
        data["sessions"][session_id]["messages"] = []
        save_json(SESSIONS_FILE, data)
    return {"action": "reset", "message": "Session cleared. Starting fresh."}


async def _cmd_status(session_id: str) -> dict:
    data = load_json(SESSIONS_FILE, {"sessions": {}})
    session = data["sessions"].get(session_id, {})
    messages = session.get("messages", [])
    # Rough token estimate: ~4 chars per token
    total_chars = sum(len(m.get("content", "")) for m in messages)
    est_tokens = total_chars // 4
    return {
        "action": "status",
        "model": session.get("model", "unknown"),
        "messages": len(messages),
        "estimated_tokens": est_tokens,
        "message": f"Model: {session.get('model', 'unknown')} | Messages: {len(messages)} | ~{est_tokens:,} tokens",
    }


async def _cmd_compact(session_id: str, model: str) -> dict:
    """Summarize conversation history to reduce token usage."""
    from providers.factory import get_provider
    from providers.base import ChatRequest, Message, get_provider_for_model
    from routers.settings import get_api_key

    data = load_json(SESSIONS_FILE, {"sessions": {}})
    session = data["sessions"].get(session_id)
    if not session:
        return {"error": "Session not found"}

    messages = session.get("messages", [])
    if len(messages) < 6:
        return {"action": "compact", "message": "Not enough messages to compact (need 6+)."}

    # Keep last 2 messages, summarize the rest
    to_summarize = messages[:-2]
    keep = messages[-2:]

    provider_name = get_provider_for_model(model)
    try:
        api_key = get_api_key(provider_name)
    except Exception:
        return {"error": f"No API key for {provider_name}"}

    provider = get_provider(model, api_key)
    model_name = model.removeprefix(provider_name + "/")

    history_text = "\n".join(
        f"{m.get('role', 'user').upper()}: {m.get('content', '')[:500]}"
        for m in to_summarize
    )

    request = ChatRequest(
        model=model_name,
        messages=[
            Message(role="system", content="You are a conversation summarizer. Be concise."),
            Message(role="user", content=f"Summarize this conversation in 3-5 sentences, preserving key facts and decisions:\n\n{history_text}"),
        ],
        temperature=0.3,
        max_tokens=512,
        stream=False,
    )

    try:
        response = await provider.chat(request)
        summary = response.get("choices", [{}])[0].get("message", {}).get("content", "")
    except Exception as e:
        return {"error": f"Compaction failed: {e}"}

    # Replace history with summary
    summary_msg = {"role": "system", "content": f"[Conversation summary]: {summary}"}
    data["sessions"][session_id]["messages"] = [summary_msg] + keep
    save_json(SESSIONS_FILE, data)

    saved = len(to_summarize)
    return {
        "action": "compact",
        "message": f"Compacted {saved} messages into a summary. Context reduced.",
        "summary": summary,
    }


async def _cmd_export(session_id: str) -> dict:
    data = load_json(SESSIONS_FILE, {"sessions": {}})
    session = data["sessions"].get(session_id)
    if not session:
        return {"error": "Session not found"}

    messages = session.get("messages", [])
    lines = [f"# {session.get('title', 'Chat Export')}\n"]
    lines.append(f"Model: {session.get('model', 'unknown')}\n\n")
    for m in messages:
        role = m.get("role", "user").upper()
        content = m.get("content", "")
        lines.append(f"**{role}**\n{content}\n\n---\n\n")

    return {
        "action": "export",
        "format": "markdown",
        "content": "".join(lines),
        "filename": f"chat-{session_id[:8]}.md",
    }
