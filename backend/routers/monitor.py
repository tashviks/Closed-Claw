"""
Monitor Mode — perpetually running agent jobs.
Flow:
  1. POST /plan   — LLM generates a plan + tools needed
  2. POST /start  — user approves, agent creates tools and starts loop
  3. GET  /stream/{id} — SSE stream of monitor events
  4. POST /stop/{id}  — stop a running monitor
  5. GET  /          — list all monitors
"""
import asyncio
import json
import logging
import os
import uuid
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

from providers.factory import get_provider
from providers.base import ChatRequest, Message
from routers.settings import get_api_key
from providers.base import get_provider_for_model
from tools.executor import execute_tool
from tools.registry import save_user_tool, get_user_tools
from core.security import sanitize_input, validate_agent_tool_code
from core.storage import load_json, save_json
from agents.parser import _try_json

log = logging.getLogger("openclaw.monitor")
router = APIRouter()

MONITORS_FILE = "monitors.json"
HOME = os.path.expanduser("~")

# In-memory running tasks: monitor_id -> asyncio.Task
_running: dict[str, asyncio.Task] = {}
# Event queues: monitor_id -> asyncio.Queue
_queues: dict[str, asyncio.Queue] = {}


# ── Storage helpers ───────────────────────────────────────────────────────────

def _load_monitors() -> dict:
    return load_json(MONITORS_FILE, {"monitors": {}})


def _save_monitors(data: dict):
    save_json(MONITORS_FILE, data)


def _get_monitor(mid: str) -> Optional[dict]:
    return _load_monitors()["monitors"].get(mid)


def _update_monitor(mid: str, updates: dict):
    data = _load_monitors()
    if mid in data["monitors"]:
        data["monitors"][mid].update(updates)
        _save_monitors(data)


# ── SSE helper ────────────────────────────────────────────────────────────────

def _evt(event_type: str, **kwargs) -> str:
    return "data: " + json.dumps({"type": event_type, "ts": datetime.utcnow().isoformat(), **kwargs}) + "\n\n"


# ── Models ────────────────────────────────────────────────────────────────────

class PlanRequest(BaseModel):
    description: str
    model: str
    interval_seconds: int = 60


class StartRequest(BaseModel):
    monitor_id: str
    approved: bool = True


class MonitorJob(BaseModel):
    description: str
    model: str
    interval_seconds: int
    check_tool_name: str
    check_tool_code: str
    action_tool_name: str
    action_tool_code: str
    trigger_condition: str  # plain English description of when to fire


# ── Plan generation ───────────────────────────────────────────────────────────

PLAN_SYSTEM = """You are OpenClaw, a local AI agent on Mac (HOME={home}).
The user wants a MONITOR — a background job that checks a condition periodically and acts when triggered.

AVAILABLE BUILT-IN TOOLS (use these in your code by calling them as Python functions via the executor):
- send_email(to, subject, body) — sends email using stored SMTP credentials
- send_notification(title, message) — macOS system notification
- http_request(url, method, headers, body) — HTTP/webhook calls
- take_screenshot(save_path) — captures screen
- run_shell(command) — runs any shell command
- open_app(app_name) — opens a Mac app
- open_url(url) — opens URL in browser

For the check_tool_code and action_tool_code, write Python that:
- Uses standard library (smtplib, urllib, subprocess, os, json, etc.) directly
- Prints a JSON result: print(json.dumps({{"status":"ok","value":42}}))
- For email: use smtplib with credentials from environment or hardcoded (user will configure)
- For notifications: use subprocess osascript
- For HTTP: use urllib.request

Respond with ONLY a JSON object. ALL code must be on ONE LINE using \\n for newlines.

Format:
{{"summary":"...","check_tool_name":"snake_name","check_tool_description":"...","check_tool_code":"import json\\nprint(json.dumps({{\\\"status\\\":\\\"ok\\\"}}))","action_tool_name":"snake_name","action_tool_description":"...","action_tool_code":"import subprocess\\nsubprocess.Popen(['osascript','-e','display notification \\"msg\\" with title \\"OpenClaw\\"'])\\nprint('done')","trigger_condition":"when to fire","trigger_eval":"result.get('status')=='error'","interval_seconds":60,"tools_needed":[]}}

For email actions use this pattern:
"import smtplib,os\\nfrom email.mime.text import MIMEText\\nm=MIMEText(BODY)\\nm['Subject']=SUBJECT\\nm['From']=os.environ.get('SMTP_USER','')\\nm['To']=TO\\ns=smtplib.SMTP('smtp.gmail.com',587)\\ns.starttls()\\ns.login(os.environ.get('SMTP_USER',''),os.environ.get('SMTP_PASS',''))\\ns.send_message(m)\\ns.quit()\\nprint('sent')"

Note: SMTP_USER and SMTP_PASS come from Settings → Integrations in the app."""


def _extract_plan_fields(content: str) -> dict:
    """Field-by-field extractor for when JSON parsing fails due to embedded code."""
    import re

    def get_field(name: str) -> str:
        # Match "field_name": "value" handling escaped quotes
        pattern = r'"' + re.escape(name) + r'"\s*:\s*"((?:[^"\\]|\\.)*)"'
        m = re.search(pattern, content, re.DOTALL)
        if m:
            return m.group(1).replace('\\"', '"')
        return ""

    def get_int_field(name: str, default: int) -> int:
        pattern = r'"' + re.escape(name) + r'"\s*:\s*(\d+)'
        m = re.search(pattern, content)
        return int(m.group(1)) if m else default

    def get_list_field(name: str) -> list:
        pattern = r'"' + re.escape(name) + r'"\s*:\s*\[(.*?)\]'
        m = re.search(pattern, content, re.DOTALL)
        if not m:
            return []
        items = re.findall(r'"([^"]*)"', m.group(1))
        return items

    plan = {
        "summary": get_field("summary"),
        "check_tool_name": get_field("check_tool_name"),
        "check_tool_description": get_field("check_tool_description"),
        "check_tool_code": get_field("check_tool_code").replace("\\n", "\n"),
        "action_tool_name": get_field("action_tool_name"),
        "action_tool_description": get_field("action_tool_description"),
        "action_tool_code": get_field("action_tool_code").replace("\\n", "\n"),
        "trigger_condition": get_field("trigger_condition"),
        "trigger_eval": get_field("trigger_eval"),
        "interval_seconds": get_int_field("interval_seconds", 60),
        "tools_needed": get_list_field("tools_needed"),
    }

    # Validate we got the minimum required fields
    if plan["check_tool_name"] and plan["action_tool_name"]:
        return plan
    return {}


async def _generate_plan(description: str, model: str) -> dict:
    import re
    provider_name = get_provider_for_model(model)
    api_key = get_api_key(provider_name)
    provider = get_provider(model, api_key)
    model_name = model.removeprefix(provider_name + "/")

    system = PLAN_SYSTEM.format(home=HOME)
    messages = [
        Message(role="system", content=system),
        Message(role="user", content="Create a monitor plan for: " + sanitize_input(description)),
    ]

    # Use high max_tokens — plan JSON can be long
    request = ChatRequest(model=model_name, messages=messages, temperature=0.2, max_tokens=4096, stream=False)
    response = await provider.chat(request)

    content = ""
    if isinstance(response, dict):
        choices = response.get("choices", [])
        if choices:
            content = choices[0].get("message", {}).get("content", "") or ""
            finish = choices[0].get("finish_reason", "")
            log.info("Plan response finish_reason=%s len=%d", finish, len(content))

            # If truncated, ask to continue
            if finish == "length" and content:
                log.info("Plan truncated, requesting continuation")
                messages.append(Message(role="assistant", content=content))
                messages.append(Message(role="user", content="Continue the JSON from where you left off. Complete it."))
                cont_request = ChatRequest(model=model_name, messages=messages, temperature=0, max_tokens=2048, stream=False)
                cont_response = await provider.chat(cont_request)
                if isinstance(cont_response, dict):
                    cont_choices = cont_response.get("choices", [])
                    if cont_choices:
                        content += cont_choices[0].get("message", {}).get("content", "") or ""

    log.info("Plan raw content: %s", content[:400])

    # Strategy 1: direct JSON parse
    stripped = content.strip()
    if stripped.startswith("```"):
        stripped = re.sub(r"^```(?:json)?\s*", "", stripped)
        stripped = re.sub(r"\s*```$", "", stripped)
    try:
        obj = json.loads(stripped)
        if "check_tool_name" in obj:
            return obj
    except (json.JSONDecodeError, ValueError):
        pass

    # Strategy 2: field-by-field extraction (handles embedded newlines in code)
    plan = _extract_plan_fields(content)
    if plan:
        log.info("Plan extracted via field parser")
        return plan

    # Strategy 3: ask model to reformat as clean JSON
    log.info("Asking model to reformat plan as clean JSON")
    messages2 = [
        Message(role="system", content="You are a JSON formatter. Output ONLY valid JSON, no markdown."),
        Message(role="user", content=f"Reformat this as valid JSON with all code on single lines using \\n:\n\n{content[:2000]}"),
    ]
    request2 = ChatRequest(model=model_name, messages=messages2, temperature=0, max_tokens=2048, stream=False)
    try:
        response2 = await provider.chat(request2)
        content2 = response2.get("choices", [{}])[0].get("message", {}).get("content", "") or ""
        obj = json.loads(content2.strip())
        if "check_tool_name" in obj:
            return obj
    except Exception:
        pass

    raise ValueError("Could not parse plan. Try a different model or simplify your description.")


# ── Monitor loop ──────────────────────────────────────────────────────────────

async def _monitor_loop(mid: str, job: dict):
    """Background task that runs the check/action loop."""
    queue = _queues.get(mid)
    interval = job.get("interval_seconds", 60)
    check_tool = job.get("check_tool_name", "")
    action_tool = job.get("action_tool_name", "")
    trigger_eval = job.get("trigger_eval", "False")
    iteration = 0

    # Inject stored credentials into environment for tool execution
    from core.credentials import get_credential
    smtp_user = get_credential("smtp", "user")
    smtp_pass = get_credential("smtp", "password")
    smtp_host = get_credential("smtp", "host") or "smtp.gmail.com"
    if smtp_user:
        os.environ["SMTP_USER"] = smtp_user
    if smtp_pass:
        os.environ["SMTP_PASS"] = smtp_pass
    if smtp_host:
        os.environ["SMTP_HOST"] = smtp_host

    log.info("[MONITOR %s] Starting loop every %ds", mid, interval)

    async def emit(event_type: str, **kwargs):
        evt = _evt(event_type, monitor_id=mid, **kwargs)
        if queue:
            await queue.put(evt)
        # Persist last event
        _update_monitor(mid, {"last_event": {"type": event_type, "ts": datetime.utcnow().isoformat(), **kwargs}})

    await emit("started", message="Monitor started. Checking every " + str(interval) + "s.")

    while True:
        try:
            iteration += 1
            log.info("[MONITOR %s] Iteration %d", mid, iteration)
            await emit("checking", message="Running check #" + str(iteration) + "…")

            # Run check tool
            result = await execute_tool(check_tool, {})
            log.info("[MONITOR %s] Check result: %s", mid, str(result)[:200])
            await emit("check_result", result=result, iteration=iteration)

            # Evaluate trigger condition
            should_fire = False
            try:
                # result may be dict with stdout/stderr or direct dict
                check_output = result
                if "stdout" in result:
                    try:
                        check_output = json.loads(result["stdout"])
                    except (json.JSONDecodeError, TypeError):
                        check_output = {"raw": result["stdout"], "error": result.get("stderr")}
                should_fire = bool(eval(trigger_eval, {"result": check_output, "__builtins__": {}}))
            except Exception as e:
                log.warning("[MONITOR %s] Trigger eval error: %s", mid, e)

            if should_fire:
                log.info("[MONITOR %s] TRIGGERED — running action", mid)
                await emit("triggered", message="Condition met! Running action…", result=check_output)
                action_result = await execute_tool(action_tool, {"check_result": json.dumps(check_output)})
                await emit("action_done", result=action_result)
            else:
                await emit("ok", message="All clear.")

            # Wait for next interval (interruptible)
            await asyncio.sleep(interval)

        except asyncio.CancelledError:
            log.info("[MONITOR %s] Cancelled", mid)
            await emit("stopped", message="Monitor stopped.")
            break
        except Exception as e:
            log.exception("[MONITOR %s] Error in loop", mid)
            await emit("error", message=str(e))
            await asyncio.sleep(min(interval, 30))  # back off on error

    _update_monitor(mid, {"status": "stopped"})


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post("/plan")
async def generate_plan(req: PlanRequest):
    """Step 1: Generate a monitor plan from a description."""
    try:
        plan = await _generate_plan(req.description, req.model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    mid = str(uuid.uuid4())
    data = _load_monitors()
    data["monitors"][mid] = {
        "id": mid,
        "description": req.description,
        "model": req.model,
        "interval_seconds": plan.get("interval_seconds", req.interval_seconds),
        "status": "pending_approval",
        "plan": plan,
        "created_at": datetime.utcnow().isoformat(),
    }
    _save_monitors(data)

    return {"monitor_id": mid, "plan": plan}


@router.post("/start/{monitor_id}")
async def start_monitor(monitor_id: str):
    """Step 2: User approved — create tools and start the loop."""
    monitor = _get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")
    if monitor["status"] == "running":
        raise HTTPException(status_code=400, detail="Already running")

    plan = monitor["plan"]

    # Create and save check tool
    check_code = plan.get("check_tool_code", "print('{}') ")
    is_safe, reason = validate_agent_tool_code(check_code)
    if not is_safe:
        raise HTTPException(status_code=400, detail="Check tool blocked: " + reason)

    check_name = plan.get("check_tool_name", "monitor_check_" + monitor_id[:8])
    save_user_tool({
        "name": check_name,
        "description": plan.get("check_tool_description", "Monitor check"),
        "code": check_code,
        "parameters": {"type": "object", "properties": {}},
        "enabled": True,
    })

    # Create and save action tool
    action_code = plan.get("action_tool_code", "print('action triggered')")
    is_safe, reason = validate_agent_tool_code(action_code)
    if not is_safe:
        raise HTTPException(status_code=400, detail="Action tool blocked: " + reason)

    action_name = plan.get("action_tool_name", "monitor_action_" + monitor_id[:8])
    save_user_tool({
        "name": action_name,
        "description": plan.get("action_tool_description", "Monitor action"),
        "code": action_code,
        "parameters": {"type": "object", "properties": {"check_result": {"type": "string"}}},
        "enabled": True,
    })

    job = {
        "check_tool_name": check_name,
        "action_tool_name": action_name,
        "trigger_eval": plan.get("trigger_eval", "False"),
        "interval_seconds": monitor.get("interval_seconds", 60),
    }

    _update_monitor(monitor_id, {
        "status": "running",
        "check_tool_name": check_name,
        "action_tool_name": action_name,
        "trigger_eval": plan.get("trigger_eval", "False"),
        "started_at": datetime.utcnow().isoformat(),
    })

    # Create event queue and start background task
    _queues[monitor_id] = asyncio.Queue()
    task = asyncio.create_task(_monitor_loop(monitor_id, job))
    _running[monitor_id] = task

    return {"status": "started", "monitor_id": monitor_id, "check_tool": check_name, "action_tool": action_name}


@router.get("/stream/{monitor_id}")
async def stream_monitor(monitor_id: str):
    """SSE stream of monitor events."""
    monitor = _get_monitor(monitor_id)
    if not monitor:
        raise HTTPException(status_code=404, detail="Monitor not found")

    if monitor_id not in _queues:
        _queues[monitor_id] = asyncio.Queue()

    queue = _queues[monitor_id]

    async def generate():
        yield ": ping\n\n"
        while True:
            try:
                event = await asyncio.wait_for(queue.get(), timeout=30)
                yield event
                if '"type": "stopped"' in event:
                    break
            except asyncio.TimeoutError:
                yield ": keepalive\n\n"

    return StreamingResponse(generate(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


@router.post("/stop/{monitor_id}")
async def stop_monitor(monitor_id: str):
    """Stop a running monitor."""
    task = _running.get(monitor_id)
    if task and not task.done():
        task.cancel()
        try:
            await asyncio.wait_for(asyncio.shield(task), timeout=3)
        except (asyncio.CancelledError, asyncio.TimeoutError):
            pass
    _running.pop(monitor_id, None)
    _update_monitor(monitor_id, {"status": "stopped"})
    return {"status": "stopped"}


@router.get("/")
async def list_monitors():
    data = _load_monitors()
    monitors = list(data["monitors"].values())
    # Annotate with live status
    for m in monitors:
        mid = m["id"]
        if mid in _running and not _running[mid].done():
            m["status"] = "running"
    return {"monitors": monitors}


@router.delete("/{monitor_id}")
async def delete_monitor(monitor_id: str):
    task = _running.pop(monitor_id, None)
    if task:
        task.cancel()
    data = _load_monitors()
    data["monitors"].pop(monitor_id, None)
    _save_monitors(data)
    return {"deleted": True}
