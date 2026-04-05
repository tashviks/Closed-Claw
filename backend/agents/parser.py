"""
Response parser — extracts tool calls and tool definitions from any model output.

Handles all formats models actually emit:
  1. <tool_call>{json}</tool_call>          — our preferred format
  2. <create_tool>{json}</create_tool>      — our preferred create format
  3. <function=name><parameter=x>v</parameter></function>  — some OpenRouter models
  4. Bare JSON object with "name"+"code"    — models that ignore format instructions
  5. ```python ... ``` code blocks          — models that output raw code
  6. subprocess.Popen / open -a patterns   — intent detection last resort
"""
import json
import re
import logging
from typing import Optional

log = logging.getLogger("openclaw.parser")

# ── Compiled patterns ─────────────────────────────────────────────────────────

_TOOL_CALL_RE = re.compile(r"<tool_call>\s*(\{.*?\})\s*</tool_call>", re.DOTALL)
_CREATE_TOOL_RE = re.compile(r"<create_tool>\s*(\{.*?\})\s*</create_tool>", re.DOTALL)
_FUNC_RE = re.compile(r"<function=(\w+)>(.*?)</function>", re.DOTALL)
_PARAM_RE = re.compile(r"<parameter=(\w+)>\s*(.*?)\s*</parameter>", re.DOTALL)
_CODE_BLOCK_RE = re.compile(r"```(?:python|bash|sh|py)?\n(.*?)```", re.DOTALL)
_POPEN_RE = re.compile(r"subprocess\.Popen\(\[([^\]]+)\]\)", re.DOTALL)
_OPEN_APP_RE = re.compile(r"open\s+-a\s+['\"]?([A-Za-z][A-Za-z0-9 .]+)['\"]?")
_APPSTORE_URL_RE = re.compile(r"(macappstore://[^\s'\"<>]+|https://apps\.apple\.com/[^\s'\"<>]+)")


def _try_json(s: str) -> Optional[dict]:
    """Try to parse JSON, with newline repair fallback."""
    s = s.strip()
    try:
        return json.loads(s)
    except (json.JSONDecodeError, ValueError):
        pass
    try:
        repaired = re.sub(r'(?<!\\)\n', r'\\n', s)
        return json.loads(repaired)
    except (json.JSONDecodeError, ValueError):
        return None


def _scan_json_objects(text: str):
    """Yield all top-level JSON objects found in text using brace matching."""
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start == -1:
            break
        depth = 0
        end = start
        for j, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        candidate = text[start:end + 1]
        obj = _try_json(candidate)
        if obj is not None:
            yield obj
        i = start + 1


# ── Public API ────────────────────────────────────────────────────────────────

def extract_tool_call(text: str) -> Optional[dict]:
    """Extract an existing tool call from model output."""
    # Format 1: <tool_call>{json}</tool_call>
    m = _TOOL_CALL_RE.search(text)
    if m:
        obj = _try_json(m.group(1))
        if obj and "name" in obj:
            log.debug("Parsed tool_call via tag")
            return obj

    # Format 3: <function=name>...</function> (not create_tool)
    m = _FUNC_RE.search(text)
    if m and m.group(1) not in ("create_tool",):
        fn_name = m.group(1)
        params = {k: v.strip() for k, v in _PARAM_RE.findall(m.group(2))}
        # Try to parse arguments param as JSON
        args_raw = params.pop("arguments", "{}")
        try:
            args = json.loads(args_raw)
        except (json.JSONDecodeError, ValueError):
            args = params
        log.debug("Parsed tool_call via <function=> tag")
        return {"name": fn_name, "arguments": args}

    return None


def extract_new_tool(text: str) -> Optional[dict]:
    """Extract a tool creation request from model output."""
    # Format 1: <create_tool>{json}</create_tool>
    m = _CREATE_TOOL_RE.search(text)
    if m:
        obj = _try_json(m.group(1))
        if obj and "name" in obj and "code" in obj:
            log.debug("Parsed create_tool via tag")
            return obj

    # Format 3: <function=create_tool>...</function>
    m = _FUNC_RE.search(text)
    if m and m.group(1) == "create_tool":
        params = {k: v.strip() for k, v in _PARAM_RE.findall(m.group(2))}
        if "name" in params and "code" in params:
            log.debug("Parsed create_tool via <function=> tag")
            return {
                "name": params.get("name", ""),
                "description": params.get("description", ""),
                "code": params.get("code", ""),
                "arguments": _try_json(params.get("arguments", "{}")) or {},
            }

    # Format 4: bare JSON object with name+code keys
    for obj in _scan_json_objects(text):
        if isinstance(obj, dict) and "name" in obj and "code" in obj:
            log.debug("Parsed create_tool via bare JSON scan")
            return obj

    # Format 5: ```python code block — wrap it into a tool
    m = _CODE_BLOCK_RE.search(text)
    if m:
        code = m.group(1).strip()
        if code and ("subprocess" in code or "import" in code or "open(" in code):
            log.debug("Parsed create_tool via code block")
            return {
                "name": "auto_tool",
                "description": "Auto-extracted from code block",
                "code": code,
                "arguments": {},
            }

    return None


def extract_intent_action(text: str) -> Optional[dict]:
    """
    Last-resort intent detection — model output plain text but we can
    infer the action from patterns like subprocess.Popen or 'open -a'.
    Returns a synthetic create_tool dict or None.
    """
    # App Store URL
    m = _APPSTORE_URL_RE.search(text)
    if m:
        url = m.group(1)
        log.debug("Intent: App Store URL %s", url)
        return {
            "name": "open_url",
            "description": "Open URL",
            "code": "import subprocess\nsubprocess.Popen(['open', '" + url + "'])\nprint('Opened: " + url + "')",
            "arguments": {},
        }

    # subprocess.Popen pattern
    m = _POPEN_RE.search(text)
    if m:
        args_str = m.group(1)
        log.debug("Intent: subprocess.Popen %s", args_str)
        code = "import subprocess\nsubprocess.Popen([" + args_str + "])\nprint('Done')"
        return {
            "name": "auto_exec",
            "description": "Auto-detected subprocess call",
            "code": code,
            "arguments": {},
        }

    # open -a AppName
    m = _OPEN_APP_RE.search(text)
    if m:
        app = m.group(1).strip()
        log.debug("Intent: open -a %s", app)
        return {
            "name": "open_" + app.lower().replace(" ", "_"),
            "description": "Open " + app,
            "code": "import subprocess\nsubprocess.Popen(['open', '-a', '" + app + "'])\nprint('Opened " + app + "')",
            "arguments": {},
        }

    return None


def clean_response(text: str) -> str:
    """Strip all tool markup and bare JSON tool defs from text for display."""
    text = _TOOL_CALL_RE.sub("", text)
    text = _CREATE_TOOL_RE.sub("", text)
    text = _FUNC_RE.sub("", text)

    # Strip bare JSON objects that look like tool defs
    parts = []
    i = 0
    while i < len(text):
        start = text.find("{", i)
        if start == -1:
            parts.append(text[i:])
            break
        parts.append(text[i:start])
        # Find matching brace
        depth = 0
        end = start
        for j, ch in enumerate(text[start:], start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    end = j
                    break
        candidate = text[start:end + 1]
        obj = _try_json(candidate)
        if isinstance(obj, dict) and "name" in obj and "code" in obj:
            i = end + 1  # skip it
        else:
            parts.append(text[start])
            i = start + 1

    text = "".join(parts)
    # Strip ```json/python blocks containing tool defs
    text = re.sub(r"```[a-z]*\s*\{[^`]*\"code\"[^`]*\}\s*```", "", text, flags=re.DOTALL)
    return text.strip()
