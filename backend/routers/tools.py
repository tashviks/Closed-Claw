"""
Tools router — CRUD for user-defined tools + test execution
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from tools.registry import get_builtin_tools, get_user_tools, save_user_tool, delete_user_tool
from tools.executor import execute_tool
from core.security import validate_tool_code

router = APIRouter()


class UserTool(BaseModel):
    name: str
    description: str
    code: str
    parameters: dict = {"type": "object", "properties": {}}
    enabled: bool = True

    @field_validator("name")
    @classmethod
    def validate_name(cls, v):
        import re
        if not re.match(r"^[a-z_][a-z0-9_]{0,63}$", v):
            raise ValueError("Tool name must be lowercase snake_case, max 64 chars")
        return v

    @field_validator("code")
    @classmethod
    def validate_code(cls, v):
        if len(v) > 10000:
            raise ValueError("Code too long (max 10000 chars)")
        return v


class TestToolRequest(BaseModel):
    name: str
    arguments: dict = {}


@router.get("/")
async def list_tools():
    return {
        "builtin": get_builtin_tools(),
        "user": get_user_tools(),
    }


@router.post("/")
async def create_tool(tool: UserTool):
    is_safe, reason = validate_tool_code(tool.code)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security check failed: {reason}")
    save_user_tool(tool.model_dump())
    return {"success": True, "name": tool.name}


@router.put("/{name}")
async def update_tool(name: str, tool: UserTool):
    if tool.name != name:
        raise HTTPException(status_code=400, detail="Name mismatch")
    is_safe, reason = validate_tool_code(tool.code)
    if not is_safe:
        raise HTTPException(status_code=400, detail=f"Security check failed: {reason}")
    save_user_tool(tool.model_dump())
    return {"success": True}


@router.delete("/{name}")
async def remove_tool(name: str):
    delete_user_tool(name)
    return {"success": True}


@router.post("/test")
async def test_tool(req: TestToolRequest):
    result = await execute_tool(req.name, req.arguments)
    return {"result": result}
