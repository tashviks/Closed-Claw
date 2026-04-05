"""
Tool executor — runs built-in and user-defined tools safely
"""
import json
import os
import asyncio
import traceback
from typing import Any
from core.config import get_settings
from core.security import validate_tool_code
from tools.registry import get_user_tools

cfg = get_settings()


async def execute_tool(tool_name: str, arguments: dict) -> Any:
    """Dispatch tool call to the appropriate handler."""
    handlers = {
        # File system
        "web_search": _web_search,
        "fetch_url": _fetch_url,
        "run_python": _run_python,
        "read_file": _read_file,
        "write_file": _write_file,
        "list_directory": _list_directory,
        # Actions
        "send_email": _action("send_email"),
        "send_notification": _action("send_notification"),
        "http_request": _action("http_request"),
        "take_screenshot": _action("take_screenshot"),
        "get_clipboard": _action("get_clipboard"),
        "set_clipboard": _action("set_clipboard"),
        "run_applescript": _action("run_applescript"),
        "run_shell": _action("run_shell"),
        "open_app": _action("open_app"),
        "open_url": _action("open_url"),
    }

    if tool_name in handlers:
        try:
            return await asyncio.wait_for(
                handlers[tool_name](**arguments),
                timeout=cfg.max_tool_execution_time,
            )
        except asyncio.TimeoutError:
            return {"error": f"Tool '{tool_name}' timed out after {cfg.max_tool_execution_time}s"}
        except Exception as e:
            return {"error": str(e)}

    # User-defined tool
    user_tools = {t["name"]: t for t in get_user_tools()}
    if tool_name in user_tools:
        return await _run_user_tool(user_tools[tool_name], arguments)

    return {"error": f"Unknown tool: {tool_name}"}


def _action(name: str):
    """Return a bound action function from builtin_actions."""
    import tools.builtin_actions as ba
    return getattr(ba, name)


# ── Built-in tool implementations ─────────────────────────────────────────────

async def _web_search(query: str, max_results: int = 5) -> dict:
    try:
        from duckduckgo_search import DDGS
        results = []
        with DDGS() as ddgs:
            for r in ddgs.text(query, max_results=max_results):
                results.append({
                    "title": r.get("title", ""),
                    "url": r.get("href", ""),
                    "snippet": r.get("body", ""),
                })
        return {"results": results, "query": query}
    except Exception as e:
        return {"error": str(e), "results": []}


async def _fetch_url(url: str) -> dict:
    # Validate URL
    if not url.startswith(("http://", "https://")):
        return {"error": "Only http/https URLs are allowed"}
    try:
        import httpx
        from bs4 import BeautifulSoup
        async with httpx.AsyncClient(timeout=30, follow_redirects=True) as client:
            resp = await client.get(url, headers={"User-Agent": "ClosedClaw/1.0"})
            resp.raise_for_status()
            soup = BeautifulSoup(resp.text, "lxml")
            # Remove scripts and styles
            for tag in soup(["script", "style", "nav", "footer", "header"]):
                tag.decompose()
            text = soup.get_text(separator="\n", strip=True)
            # Truncate to 8000 chars
            return {"url": url, "content": text[:8000], "status": resp.status_code}
    except Exception as e:
        return {"error": str(e)}


async def _run_python(code: str) -> dict:
    """Execute Python in a restricted subprocess with no network/fs access."""
    is_safe, reason = validate_tool_code(code)
    if not is_safe:
        return {"error": f"Code blocked by security policy: {reason}"}

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", _wrap_sandboxed(code),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={
                "PATH": os.environ.get("PATH", ""),
                "HOME": os.path.expanduser("~"),  # needed so ~ resolves correctly
                "PYTHONPATH": "",
            },
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=15)
        return {
            "stdout": stdout.decode()[:4000],
            "stderr": stderr.decode()[:1000],
            "exit_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        proc.kill()
        return {"error": "Execution timed out (15s limit)"}
    except Exception as e:
        return {"error": str(e)}


def _wrap_sandboxed(code: str) -> str:
    """Wrap user code with resource limits."""
    return f"""
import resource, sys
# Limit memory to 128MB
try:
    resource.setrlimit(resource.RLIMIT_AS, (128 * 1024 * 1024, 128 * 1024 * 1024))
except Exception:
    pass
{code}
"""


async def _read_file(path: str) -> dict:
    # Security: only allow reading within home dir or current dir
    abs_path = os.path.abspath(os.path.expanduser(path))
    home = os.path.expanduser("~")
    if not abs_path.startswith(home) and not abs_path.startswith(os.getcwd()):
        return {"error": "Access denied: path outside allowed directories"}
    try:
        with open(abs_path, "r", encoding="utf-8", errors="replace") as f:
            content = f.read(50000)  # Max 50KB
        return {"path": abs_path, "content": content}
    except Exception as e:
        return {"error": str(e)}


async def _write_file(path: str, content: str) -> dict:
    abs_path = os.path.abspath(os.path.expanduser(path))
    home = os.path.expanduser("~")
    if not abs_path.startswith(home) and not abs_path.startswith(os.getcwd()):
        return {"error": "Access denied: path outside allowed directories"}
    try:
        os.makedirs(os.path.dirname(abs_path), exist_ok=True)
        with open(abs_path, "w", encoding="utf-8") as f:
            f.write(content)
        return {"success": True, "path": abs_path}
    except Exception as e:
        return {"error": str(e)}


async def _list_directory(path: str) -> dict:
    abs_path = os.path.abspath(os.path.expanduser(path))
    home = os.path.expanduser("~")
    if not abs_path.startswith(home) and not abs_path.startswith(os.getcwd()):
        return {"error": "Access denied"}
    try:
        entries = []
        for entry in os.scandir(abs_path):
            entries.append({
                "name": entry.name,
                "type": "dir" if entry.is_dir() else "file",
                "size": entry.stat().st_size if entry.is_file() else None,
            })
        return {"path": abs_path, "entries": entries}
    except Exception as e:
        return {"error": str(e)}


async def _run_user_tool(tool: dict, arguments: dict) -> dict:
    """Execute a user-defined or agent-created Python tool."""
    code = tool.get("code", "")
    from core.security import validate_agent_tool_code
    is_safe, reason = validate_agent_tool_code(code)
    if not is_safe:
        return {"error": f"Tool blocked: {reason}"}

    # Inject arguments as variables
    arg_setup = "\n".join(f"{k} = {json.dumps(v)}" for k, v in arguments.items())

    # Inject a shim so agent code can call built-in tools as plain functions
    shim = _builtin_shim()

    full_code = f"{shim}\n{arg_setup}\n\n{code}"

    try:
        proc = await asyncio.create_subprocess_exec(
            "python3", "-c", full_code,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            env={**os.environ, "PYTHONPATH": ""},
        )
        stdout, stderr = await asyncio.wait_for(proc.communicate(), timeout=30)
        return {
            "stdout": stdout.decode()[:4000],
            "stderr": stderr.decode()[:1000],
            "exit_code": proc.returncode,
        }
    except asyncio.TimeoutError:
        return {"error": "Tool execution timed out (30s)"}
    except Exception as e:
        return {"error": str(e)}


def _builtin_shim() -> str:
    """
    Python shim injected into every user tool execution.
    Maps built-in tool names to real implementations so agent-generated
    code like `open_url('https://...')` or `send_notification('title','msg')` works.
    """
    home = os.path.expanduser("~")
    smtp_user = os.environ.get("SMTP_USER", "")
    smtp_pass = os.environ.get("SMTP_PASS", "")
    smtp_host = os.environ.get("SMTP_HOST", "smtp.gmail.com")

    return f'''
import subprocess, os, json, sys

HOME = {json.dumps(home)}

def open_app(app_name):
    r = subprocess.run(["open", "-a", app_name], capture_output=True)
    return {{"success": r.returncode == 0, "app": app_name}}

def open_url(url):
    r = subprocess.run(["open", url], capture_output=True)
    return {{"success": r.returncode == 0, "url": url}}

def send_notification(title, message, sound=True):
    sound_str = "default" if sound else "none"
    script = f'display notification "{{message}}" with title "{{title}}" sound name "{{sound_str}}"'
    r = subprocess.run(["osascript", "-e", script], capture_output=True)
    return {{"success": r.returncode == 0}}

def run_shell(command, timeout=30):
    r = subprocess.run(command, shell=True, capture_output=True, timeout=timeout)
    return {{"stdout": r.stdout.decode()[:2000], "stderr": r.stderr.decode()[:500], "exit_code": r.returncode}}

def run_applescript(script):
    r = subprocess.run(["osascript", "-e", script], capture_output=True)
    return {{"stdout": r.stdout.decode().strip(), "stderr": r.stderr.decode().strip(), "exit_code": r.returncode}}

def take_screenshot(save_path=""):
    path = save_path or os.path.join(HOME, "Desktop", "screenshot.png")
    r = subprocess.run(["screencapture", "-x", path], capture_output=True)
    return {{"success": r.returncode == 0, "path": path}}

def get_clipboard():
    r = subprocess.run(["pbpaste"], capture_output=True)
    return {{"content": r.stdout.decode("utf-8", errors="replace")[:4000]}}

def set_clipboard(text):
    subprocess.run(["pbcopy"], input=text.encode(), capture_output=True)
    return {{"success": True}}

def http_request(url, method="GET", headers=None, body="", timeout=30):
    import urllib.request, urllib.error
    req = urllib.request.Request(url, method=method.upper())
    if headers:
        for k, v in headers.items():
            req.add_header(k, v)
    if body:
        req.data = body.encode() if isinstance(body, str) else body
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return {{"status": resp.status, "ok": True, "body": resp.read().decode()[:4000]}}
    except urllib.error.HTTPError as e:
        return {{"status": e.code, "ok": False, "body": e.read().decode()[:1000]}}
    except Exception as e:
        return {{"error": str(e)}}

def send_email(to, subject, body, smtp_host={json.dumps(smtp_host)}, smtp_port=587, smtp_user={json.dumps(smtp_user)}, smtp_password={json.dumps(smtp_pass)}, from_addr=""):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText
    user = smtp_user or os.environ.get("SMTP_USER", "")
    password = smtp_password or os.environ.get("SMTP_PASS", "")
    sender = from_addr or user
    if not user or not password:
        print(json.dumps({{"error": "SMTP not configured. Add credentials in Settings → Integrations."}}))
        return {{"error": "SMTP not configured"}}
    msg = MIMEMultipart()
    msg["From"] = sender
    msg["To"] = to
    msg["Subject"] = subject
    msg.attach(MIMEText(body, "plain"))
    with smtplib.SMTP(smtp_host, smtp_port, timeout=30) as s:
        s.ehlo(); s.starttls(); s.login(user, password)
        s.sendmail(sender, to, msg.as_string())
    return {{"success": True, "to": to}}

def read_file(path):
    p = os.path.expanduser(path)
    with open(p, "r", encoding="utf-8", errors="replace") as f:
        return {{"content": f.read(50000)}}

def write_file(path, content):
    p = os.path.expanduser(path)
    os.makedirs(os.path.dirname(p) or ".", exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        f.write(content)
    return {{"success": True, "path": p}}

def list_directory(path):
    p = os.path.expanduser(path)
    entries = [{{"name": e.name, "type": "dir" if e.is_dir() else "file"}} for e in os.scandir(p)]
    return {{"entries": entries, "path": p}}
'''
