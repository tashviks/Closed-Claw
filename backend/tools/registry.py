"""
Tool registry — built-in tools + user-defined tools
"""
import json
import os
from core.storage import load_json, save_json

TOOLS_FILE = "tools.json"


def get_builtin_tools() -> list[dict]:
    """Return OpenAI-compatible tool definitions for built-in tools."""
    return [
        {
            "type": "function",
            "function": {
                "name": "web_search",
                "description": "Search the web for current information on any topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "query": {"type": "string", "description": "Search query"},
                        "max_results": {"type": "integer", "default": 5},
                    },
                    "required": ["query"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "fetch_url",
                "description": "Fetch and extract text content from a URL.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_python",
                "description": "Execute a Python code snippet in a sandboxed environment. No network or file system access.",
                "parameters": {
                    "type": "object",
                    "properties": {"code": {"type": "string"}},
                    "required": ["code"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "read_file",
                "description": "Read a local file by path.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "write_file",
                "description": "Write content to a local file.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "path": {"type": "string"},
                        "content": {"type": "string"},
                    },
                    "required": ["path", "content"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "list_directory",
                "description": "List files and folders in a directory.",
                "parameters": {
                    "type": "object",
                    "properties": {"path": {"type": "string"}},
                    "required": ["path"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_email",
                "description": "Send an email. Uses stored SMTP credentials from Settings → Integrations.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "to": {"type": "string", "description": "Recipient email address"},
                        "subject": {"type": "string"},
                        "body": {"type": "string"},
                    },
                    "required": ["to", "subject", "body"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "send_notification",
                "description": "Send a macOS system notification with a title and message.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "title": {"type": "string"},
                        "message": {"type": "string"},
                        "sound": {"type": "boolean", "default": True},
                    },
                    "required": ["title", "message"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "http_request",
                "description": "Make an HTTP request to any URL. Use for webhooks, REST APIs, Slack/Discord webhooks.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "url": {"type": "string"},
                        "method": {"type": "string", "default": "GET", "enum": ["GET", "POST", "PUT", "DELETE", "PATCH"]},
                        "headers": {"type": "object"},
                        "body": {"type": "string"},
                    },
                    "required": ["url"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "take_screenshot",
                "description": "Take a screenshot of the screen and save it.",
                "parameters": {
                    "type": "object",
                    "properties": {"save_path": {"type": "string", "description": "Where to save the screenshot"}},
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "get_clipboard",
                "description": "Get the current clipboard contents.",
                "parameters": {"type": "object", "properties": {}},
            },
        },
        {
            "type": "function",
            "function": {
                "name": "set_clipboard",
                "description": "Set the clipboard contents.",
                "parameters": {
                    "type": "object",
                    "properties": {"text": {"type": "string"}},
                    "required": ["text"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_applescript",
                "description": "Run an AppleScript for Mac automation (control apps, UI, system).",
                "parameters": {
                    "type": "object",
                    "properties": {"script": {"type": "string"}},
                    "required": ["script"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "run_shell",
                "description": "Run any shell command with full system access.",
                "parameters": {
                    "type": "object",
                    "properties": {
                        "command": {"type": "string"},
                        "timeout": {"type": "integer", "default": 30},
                    },
                    "required": ["command"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_app",
                "description": "Open a macOS application by name.",
                "parameters": {
                    "type": "object",
                    "properties": {"app_name": {"type": "string"}},
                    "required": ["app_name"],
                },
            },
        },
        {
            "type": "function",
            "function": {
                "name": "open_url",
                "description": "Open a URL in the default browser or associated app.",
                "parameters": {
                    "type": "object",
                    "properties": {"url": {"type": "string"}},
                    "required": ["url"],
                },
            },
        },
    ]


def get_user_tools() -> list[dict]:
    data = load_json(TOOLS_FILE, {"tools": []})
    return data.get("tools", [])


def get_all_tools() -> list[dict]:
    return get_builtin_tools() + [
        {
            "type": "function",
            "function": {
                "name": t["name"],
                "description": t.get("description", ""),
                "parameters": t.get("parameters", {"type": "object", "properties": {}}),
            },
        }
        for t in get_user_tools()
        if t.get("enabled", True)
    ]


def save_user_tool(tool: dict) -> None:
    data = load_json(TOOLS_FILE, {"tools": []})
    tools = data.get("tools", [])
    # Update if exists
    for i, t in enumerate(tools):
        if t["name"] == tool["name"]:
            tools[i] = tool
            save_json(TOOLS_FILE, {"tools": tools})
            return
    tools.append(tool)
    save_json(TOOLS_FILE, {"tools": tools})


def delete_user_tool(name: str) -> bool:
    data = load_json(TOOLS_FILE, {"tools": []})
    tools = [t for t in data.get("tools", []) if t["name"] != name]
    save_json(TOOLS_FILE, {"tools": tools})
    return True
