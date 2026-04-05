"""
Agent loop — orchestrates LLM calls, tool execution, and SSE streaming.

Two modes:
  • native  — OpenAI/Anthropic/Mistral function calling
  • react   — ReAct text-based dispatch for all other models
"""
import json
import logging
from typing import AsyncIterator

from providers.base import ChatRequest, Message
from tools.registry import get_all_tools
from tools.executor import execute_tool
from tools.registry import save_user_tool
from core.security import validate_agent_tool_code
from agents import sse
from agents.parser import (
    extract_tool_call, extract_new_tool, extract_intent_action, clean_response
)
from agents.prompts import native_system_prompt, react_system_prompt

log = logging.getLogger("openclaw.loop")

MAX_ITERATIONS = 6


def _supports_native_tools(provider: str) -> bool:
    return provider in ("openai", "anthropic", "mistral")


def _build_messages(raw_messages: list, system: str) -> list[Message]:
    msgs = [Message(role="system", content=system)]
    for m in raw_messages:
        role = m["role"] if isinstance(m, dict) else m.role
        content = m["content"] if isinstance(m, dict) else m.content
        msgs.append(Message(role=role, content=content))
    return msgs


async def _create_and_run(tool_def: dict) -> tuple[str, dict]:
    """Save + execute a tool def. Returns (tool_name, result)."""
    import re
    name = re.sub(r"[^a-z0-9_]", "_", tool_def.get("name", "auto_tool").lower())[:64] or "auto_tool"
    code = tool_def.get("code", "").strip()
    description = tool_def.get("description", "")
    arguments = tool_def.get("arguments", {})
    if not isinstance(arguments, dict):
        arguments = {}

    save_user_tool({
        "name": name,
        "description": description,
        "code": code,
        "parameters": {"type": "object", "properties": {k: {"type": "string"} for k in arguments}},
        "enabled": True,
    })
    result = await execute_tool(name, arguments)
    return name, result


async def run_native(
    provider,
    model_name: str,
    raw_messages: list,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    """Native function-calling loop (OpenAI / Anthropic / Mistral)."""
    messages = _build_messages(raw_messages, native_system_prompt())
    tools = get_all_tools()

    request = ChatRequest(
        model=model_name, messages=messages,
        temperature=temperature, max_tokens=max_tokens,
        tools=tools, stream=True,
    )

    for iteration in range(MAX_ITERATIONS):
        log.info("[NATIVE] iteration %d", iteration + 1)
        full_response = ""
        pending: dict[int, dict] = {}

        try:
            async for chunk in provider.chat_stream(request):
                if chunk.startswith('{"tool_calls":'):
                    try:
                        data = json.loads(chunk)
                        for tc in data.get("tool_calls", []):
                            idx = tc.get("index", 0)
                            if idx not in pending:
                                pending[idx] = {
                                    "id": tc.get("id", f"call_{idx}"),
                                    "function": {"name": "", "arguments": ""},
                                }
                            fn = tc.get("function", {})
                            if fn.get("name"):
                                pending[idx]["function"]["name"] += fn["name"]
                            if fn.get("arguments"):
                                pending[idx]["function"]["arguments"] += fn["arguments"]
                    except json.JSONDecodeError:
                        pass
                else:
                    full_response += chunk
                    yield sse.token(chunk)
        except Exception as e:
            yield sse.error(str(e))
            return

        if not pending:
            break

        if full_response:
            messages.append(Message(role="assistant", content=full_response))

        for tc in pending.values():
            fn_name = tc["function"]["name"]
            try:
                args = json.loads(tc["function"]["arguments"] or "{}")
            except json.JSONDecodeError:
                args = {}

            yield sse.thinking(f"Calling {fn_name}…")
            yield sse.tool_call(fn_name, args)
            result = await execute_tool(fn_name, args)
            yield sse.tool_result(fn_name, result)
            messages.append(Message(
                role="tool", content=json.dumps(result),
                tool_call_id=tc["id"], name=fn_name,
            ))

        request = ChatRequest(
            model=model_name, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
            tools=tools, stream=True,
        )


async def run_react(
    provider,
    model_name: str,
    raw_messages: list,
    temperature: float,
    max_tokens: int,
) -> AsyncIterator[str]:
    """ReAct loop — works with any model via text-based tool dispatch."""
    messages = _build_messages(raw_messages, react_system_prompt())

    request = ChatRequest(
        model=model_name, messages=messages,
        temperature=temperature,
        max_tokens=max(max_tokens, 2048),
        tools=None, stream=True,
    )

    for iteration in range(MAX_ITERATIONS):
        log.info("[REACT] iteration %d", iteration + 1)
        yield sse.thinking("Thinking…")

        full_response = ""
        try:
            async for chunk in provider.chat_stream(request):
                full_response += chunk
        except Exception as e:
            yield sse.error(str(e))
            return

        log.info("[REACT] response (%d chars): %s", len(full_response), full_response[:200])

        # ── Handle truncated output (finish_reason: length) ───────────────────
        has_open_tag = (
            ("<create_tool>" in full_response and "</create_tool>" not in full_response) or
            ("<tool_call>" in full_response and "</tool_call>" not in full_response)
        )
        if has_open_tag:
            log.info("[REACT] truncated tag detected, requesting continuation")
            messages.append(Message(role="assistant", content=full_response))
            messages.append(Message(role="user", content="Continue from where you left off. Complete the JSON and close the tag."))
            cont_request = ChatRequest(
                model=model_name, messages=messages,
                temperature=0, max_tokens=1024, tools=None, stream=True,
            )
            continuation = ""
            try:
                async for chunk in provider.chat_stream(cont_request):
                    continuation += chunk
            except Exception:
                pass
            full_response += continuation
            log.info("[REACT] after continuation: %s", full_response[:200])

        # ── Priority 1: create_tool ───────────────────────────────────────────
        new_tool = extract_new_tool(full_response)
        if new_tool:
            code = new_tool.get("code", "")
            is_safe, reason = validate_agent_tool_code(code)
            if not is_safe:
                yield sse.error(f"Tool blocked: {reason}")
                break

            tool_name, result = await _create_and_run(new_tool)
            yield sse.tool_created(tool_name, new_tool.get("description", ""))
            yield sse.tool_call(tool_name, new_tool.get("arguments", {}))
            yield sse.tool_result(tool_name, result)

            if "error" in result:
                yield sse.token(f"Tool error: {result['error']}")
                break

            # Ask model to summarize
            messages.append(Message(role="assistant", content=full_response))
            messages.append(Message(
                role="user",
                content=f"Tool `{tool_name}` completed:\n```\n{json.dumps(result, indent=2)}\n```\nAnswer the user concisely.",
            ))
            request = ChatRequest(
                model=model_name, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
                tools=None, stream=True,
            )
            try:
                async for chunk in provider.chat_stream(request):
                    yield sse.token(chunk)
            except Exception as e:
                yield sse.error(str(e))
            break

        # ── Priority 2: existing tool_call ────────────────────────────────────
        tool_call_def = extract_tool_call(full_response)
        if tool_call_def:
            fn_name = tool_call_def.get("name", "")
            args = tool_call_def.get("arguments", {})

            # Stream any text before the tag
            tag_pos = full_response.find("<tool_call>")
            if tag_pos > 0:
                pre = clean_response(full_response[:tag_pos])
                if pre:
                    yield sse.token(pre + "\n\n")

            yield sse.thinking(f"Calling {fn_name}…")
            yield sse.tool_call(fn_name, args)
            result = await execute_tool(fn_name, args)
            yield sse.tool_result(fn_name, result)

            if "error" in result:
                yield sse.token(f"Tool error: {result['error']}")
                break

            messages.append(Message(role="assistant", content=full_response))
            messages.append(Message(
                role="user",
                content=f"Tool `{fn_name}` returned:\n```json\n{json.dumps(result, indent=2)}\n```\nAnswer the user concisely.",
            ))
            request = ChatRequest(
                model=model_name, messages=messages,
                temperature=temperature, max_tokens=max_tokens,
                tools=None, stream=True,
            )
            try:
                async for chunk in provider.chat_stream(request):
                    yield sse.token(chunk)
            except Exception as e:
                yield sse.error(str(e))
            break

        # ── Priority 3: intent detection (model ignored format instructions) ──
        intent = extract_intent_action(full_response)
        if intent:
            log.info("[REACT] intent detected: %s", intent.get("name"))
            code = intent.get("code", "")
            is_safe, reason = validate_agent_tool_code(code)
            if is_safe:
                tool_name, result = await _create_and_run(intent)
                yield sse.tool_created(tool_name, intent.get("description", ""))
                yield sse.tool_call(tool_name, {})
                yield sse.tool_result(tool_name, result)
                clean = clean_response(full_response)
                if clean:
                    yield sse.token(clean)
                else:
                    stdout = result.get("stdout", "").strip()
                    yield sse.token(stdout if stdout else "Done.")
                break

        # ── Priority 4: plain response ────────────────────────────────────────
        clean = clean_response(full_response)
        log.info("[REACT] plain response: %s", clean[:100])
        if clean:
            yield sse.token(clean)
        break


async def run(
    provider,
    provider_name: str,
    model_name: str,
    raw_messages: list,
    temperature: float,
    max_tokens: int,
    use_tools: bool,
) -> AsyncIterator[str]:
    """Entry point — picks native or ReAct based on provider."""
    if use_tools and _supports_native_tools(provider_name):
        log.info("[AGENT] mode=native provider=%s model=%s", provider_name, model_name)
        async for event in run_native(provider, model_name, raw_messages, temperature, max_tokens):
            yield event
    elif use_tools:
        log.info("[AGENT] mode=react provider=%s model=%s", provider_name, model_name)
        async for event in run_react(provider, model_name, raw_messages, temperature, max_tokens):
            yield event
    else:
        # Plain chat — no tools
        log.info("[AGENT] mode=plain provider=%s model=%s", provider_name, model_name)
        from agents.prompts import native_system_prompt
        messages = _build_messages(raw_messages, native_system_prompt())
        request = ChatRequest(
            model=model_name, messages=messages,
            temperature=temperature, max_tokens=max_tokens,
            tools=None, stream=True,
        )
        try:
            async for chunk in provider.chat_stream(request):
                yield sse.token(chunk)
        except Exception as e:
            yield sse.error(str(e))
