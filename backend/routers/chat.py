"""
Chat router — thin HTTP layer over the agent loop.
Adds: session commands, usage tracking, model failover, thinking mode.
"""
import logging
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from typing import Optional

from providers.factory import get_provider
from providers.base import get_provider_for_model, MODELS
from routers.settings import get_api_key
from core.security import sanitize_input
from agents import sse
from agents.loop import run

log = logging.getLogger("openclaw.chat")
router = APIRouter()

# Model failover chains — if primary fails, try these in order
FAILOVER_CHAINS: dict[str, list[str]] = {
    "google/gemini-2.5-flash": ["google/gemini-2.0-flash", "openrouter/stepfun/step-3.5-flash:free"],
    "openai/gpt-4o": ["openai/gpt-4o-mini"],
    "anthropic/claude-opus-4-5": ["anthropic/claude-sonnet-4-5", "anthropic/claude-3-5-sonnet"],
}


class ChatPayload(BaseModel):
    model: str
    messages: list
    temperature: float = 0.7
    max_tokens: int = 4096
    use_tools: bool = True
    stream: bool = True
    session_id: Optional[str] = None
    thinking: bool = False  # extended reasoning mode
    usage_tracking: bool = True


def _parse_command(messages: list) -> Optional[str]:
    """Check if the last user message is a slash command."""
    for m in reversed(messages):
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else m.content
        if role == "user" and content.strip().startswith("/"):
            return content.strip()
    return None


async def _stream(payload: ChatPayload):
    yield ": ping\n\n"

    # ── Handle slash commands ─────────────────────────────────────────────────
    command = _parse_command(payload.messages)
    if command:
        from routers.commands import handle_command, CommandRequest
        result = await handle_command(CommandRequest(
            session_id=payload.session_id or "default",
            command=command,
            model=payload.model,
        ))
        if "error" in result:
            yield sse.error(result["error"])
        else:
            msg = result.get("message", str(result))
            # For export, include the content
            if result.get("action") == "export":
                yield sse.evt("export", content=result["content"], filename=result["filename"])
                msg = f"Exported to {result['filename']}"
            elif result.get("action") == "compact" and result.get("summary"):
                yield sse.evt("compact_summary", summary=result["summary"])
            yield sse.token(msg)
        yield sse.done()
        return

    # ── Resolve provider + API key ────────────────────────────────────────────
    models_to_try = [payload.model] + FAILOVER_CHAINS.get(payload.model, [])
    provider_name = None
    provider = None
    model_name = None

    for candidate in models_to_try:
        pname = get_provider_for_model(candidate)
        try:
            api_key = get_api_key(pname)
            prov = get_provider(candidate, api_key)
            provider_name = pname
            provider = prov
            model_name = candidate.removeprefix(pname + "/")
            if candidate != payload.model:
                log.info("Failover: %s -> %s", payload.model, candidate)
                yield sse.evt("failover", from_model=payload.model, to_model=candidate)
            break
        except Exception:
            log.warning("Model %s unavailable, trying next", candidate)
            continue

    if not provider:
        yield sse.error(f"No API key configured for {get_provider_for_model(payload.model)}. Add one in Settings.")
        yield sse.done()
        return

    log.info("REQUEST model=%s provider=%s msgs=%d thinking=%s",
             model_name, provider_name, len(payload.messages), payload.thinking)

    # ── Sanitize messages ─────────────────────────────────────────────────────
    raw_messages = []
    for m in payload.messages:
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else m.content
        if role == "user":
            content = sanitize_input(content)
        raw_messages.append({"role": role, "content": content})

    # ── Thinking mode — inject extended reasoning instruction ─────────────────
    model_info = MODELS.get(payload.model, {})
    supports_thinking = model_info.get("supports_thinking", False)
    if payload.thinking and supports_thinking:
        raw_messages = [{"role": "system", "content": "Think step by step carefully before answering. Show your reasoning."}] + raw_messages

    # ── Run agent loop ────────────────────────────────────────────────────────
    input_chars = sum(len(m["content"]) for m in raw_messages)

    try:
        async for event in run(
            provider=provider,
            provider_name=provider_name,
            model_name=model_name,
            raw_messages=raw_messages,
            temperature=payload.temperature,
            max_tokens=payload.max_tokens,
            use_tools=payload.use_tools,
        ):
            yield event
    except Exception as e:
        log.exception("Unhandled agent error")
        yield sse.error(str(e))

    # ── Usage tracking ────────────────────────────────────────────────────────
    if payload.usage_tracking:
        try:
            from agents.usage import record_usage
            # Rough estimate: 4 chars per token
            input_tokens = input_chars // 4
            output_tokens = 200  # placeholder; real count needs non-streaming response
            usage = record_usage(model_name, input_tokens, output_tokens, payload.session_id or "")
            yield sse.evt("usage", tokens=usage["tokens"], cost=usage["cost"])
        except Exception:
            pass

    yield sse.done()


@router.post("/stream")
async def chat_stream(payload: ChatPayload):
    if not payload.messages:
        raise HTTPException(status_code=400, detail="No messages provided")
    return StreamingResponse(
        _stream(payload),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache, no-transform",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        },
    )


@router.post("/models")
async def list_models():
    return {"models": MODELS}


@router.get("/usage")
async def get_usage():
    from agents.usage import get_usage_summary
    return get_usage_summary()
