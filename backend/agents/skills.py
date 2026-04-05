"""
Skills & persona injection — reads AGENTS.md, SOUL.md, TOOLS.md from workspace.
These files let users customize the agent's persona, capabilities, and behavior.
"""
import os
import logging

log = logging.getLogger("openclaw.skills")

HOME = os.path.expanduser("~")
WORKSPACE = os.path.join(HOME, ".openclaw", "workspace")

SKILL_FILES = {
    "agents": "AGENTS.md",
    "soul": "SOUL.md",
    "tools": "TOOLS.md",
}


def _read(filename: str) -> str:
    path = os.path.join(WORKSPACE, filename)
    if os.path.exists(path):
        try:
            with open(path, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception as e:
            log.warning("Could not read %s: %s", path, e)
    return ""


def get_persona_injection() -> str:
    """Return any custom persona/skill content to prepend to system prompt."""
    parts = []
    soul = _read("SOUL.md")
    if soul:
        parts.append("## Persona\n" + soul)
    agents = _read("AGENTS.md")
    if agents:
        parts.append("## Agent Instructions\n" + agents)
    tools_md = _read("TOOLS.md")
    if tools_md:
        parts.append("## Custom Tool Notes\n" + tools_md)
    return "\n\n".join(parts)


def list_skills() -> list[dict]:
    """List installed skills from ~/.openclaw/workspace/skills/"""
    skills_dir = os.path.join(WORKSPACE, "skills")
    if not os.path.exists(skills_dir):
        return []
    skills = []
    for name in os.listdir(skills_dir):
        skill_path = os.path.join(skills_dir, name)
        if os.path.isdir(skill_path):
            skill_md = os.path.join(skill_path, "SKILL.md")
            description = ""
            if os.path.exists(skill_md):
                with open(skill_md, "r") as f:
                    description = f.readline().strip().lstrip("#").strip()
            skills.append({"name": name, "description": description, "path": skill_path})
    return skills


def ensure_workspace():
    """Create default workspace files if they don't exist."""
    os.makedirs(WORKSPACE, exist_ok=True)
    os.makedirs(os.path.join(WORKSPACE, "skills"), exist_ok=True)

    soul_path = os.path.join(WORKSPACE, "SOUL.md")
    if not os.path.exists(soul_path):
        with open(soul_path, "w") as f:
            f.write("# OpenClaw Soul\n\nYou are a helpful, precise, and proactive AI agent.\n")

    agents_path = os.path.join(WORKSPACE, "AGENTS.md")
    if not os.path.exists(agents_path):
        with open(agents_path, "w") as f:
            f.write("# Agent Instructions\n\nAlways be concise. Prefer action over explanation.\n")
