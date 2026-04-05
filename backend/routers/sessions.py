"""
Sessions router — manage conversation history
"""
import uuid
from datetime import datetime
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from core.storage import load_json, save_json

router = APIRouter()
SESSIONS_FILE = "sessions.json"


def _load() -> dict:
    return load_json(SESSIONS_FILE, {"sessions": {}})


def _save(data: dict):
    save_json(SESSIONS_FILE, data)


class CreateSession(BaseModel):
    title: str = "New Chat"
    model: str = "openai/gpt-4o-mini"


@router.get("/")
async def list_sessions():
    data = _load()
    sessions = list(data["sessions"].values())
    sessions.sort(key=lambda s: s.get("updated_at", ""), reverse=True)
    return {"sessions": sessions}


@router.post("/")
async def create_session(body: CreateSession):
    data = _load()
    sid = str(uuid.uuid4())
    now = datetime.utcnow().isoformat()
    session = {
        "id": sid,
        "title": body.title,
        "model": body.model,
        "messages": [],
        "created_at": now,
        "updated_at": now,
    }
    data["sessions"][sid] = session
    _save(data)
    return session


@router.get("/{session_id}")
async def get_session(session_id: str):
    data = _load()
    session = data["sessions"].get(session_id)
    if not session:
        raise HTTPException(status_code=404, detail="Session not found")
    return session


@router.put("/{session_id}/title")
async def update_title(session_id: str, body: dict):
    data = _load()
    if session_id not in data["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    data["sessions"][session_id]["title"] = body.get("title", "Chat")
    data["sessions"][session_id]["updated_at"] = datetime.utcnow().isoformat()
    _save(data)
    return {"success": True}


@router.delete("/{session_id}")
async def delete_session(session_id: str):
    data = _load()
    data["sessions"].pop(session_id, None)
    _save(data)
    return {"success": True}


@router.post("/{session_id}/messages")
async def append_message(session_id: str, message: dict):
    data = _load()
    if session_id not in data["sessions"]:
        raise HTTPException(status_code=404, detail="Session not found")
    data["sessions"][session_id]["messages"].append(message)
    data["sessions"][session_id]["updated_at"] = datetime.utcnow().isoformat()
    _save(data)
    return {"success": True}
