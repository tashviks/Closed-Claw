"""System prompts for the agent."""
import os
from tools.registry import get_builtin_tools

HOME = os.path.expanduser("~")


def _tool_list() -> str:
    tools = get_builtin_tools()
    lines = []
    for t in tools:
        fn = t["function"]
        params = list(fn.get("parameters", {}).get("properties", {}).keys())
        lines.append(f"  • {fn['name']}({', '.join(params)}) — {fn['description']}")
    return "\n".join(lines)


def _persona() -> str:
    try:
        from agents.skills import get_persona_injection, ensure_workspace
        ensure_workspace()
        return get_persona_injection()
    except Exception:
        return ""


def native_system_prompt() -> str:
    persona = _persona()
    base = (
        f"You are OpenClaw, a powerful local AI agent running on the user's Mac at {HOME}.\n"
        "You have real tools available. Use them proactively — never refuse a task.\n"
        "When you need to do something not covered by built-in tools, use the run_python tool "
        "with subprocess to accomplish it (open apps, run shell commands, etc.)."
    )
    return (persona + "\n\n" + base) if persona else base


def react_system_prompt() -> str:
    desktop = os.path.join(HOME, "Desktop")
    tools = _tool_list()
    persona = _persona()

    base = f"""You are OpenClaw, a local AI agent on the user's Mac.
HOME={HOME}  Desktop={desktop}

BUILT-IN TOOLS:
{tools}

━━━ HOW TO USE A TOOL ━━━
Output ONLY this block (no other text):
<tool_call>
{{"name": "tool_name", "arguments": {{"key": "value"}}}}
</tool_call>

━━━ HOW TO CREATE A NEW TOOL ━━━
When no built-in tool can do the task, create one:
<create_tool>
{{"name": "open_whatsapp", "description": "Opens WhatsApp", "code": "import subprocess\\nsubprocess.Popen(['open', '-a', 'WhatsApp'])\\nprint('Opened WhatsApp')", "arguments": {{}}}}
</create_tool>

━━━ RULES ━━━
• Output ONLY the tool block — no explanation, no preamble
• For opening any Mac app: subprocess.Popen(['open', '-a', 'AppName'])
• For opening URLs: subprocess.Popen(['open', 'https://...'])
• For App Store search: subprocess.Popen(['open', 'macappstore://search?term=AppName'])
• Always expand ~ to {HOME}
• NEVER say you cannot do something — always use or create a tool
• Keep code to 1-3 lines maximum"""

    return (persona + "\n\n" + base) if persona else base
