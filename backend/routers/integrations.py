"""
Integrations router — manage SMTP, webhooks, and other credentials.
"""
from fastapi import APIRouter
from pydantic import BaseModel
from core.credentials import save_credential, get_credential, list_credentials, delete_credential

router = APIRouter()


class CredentialRequest(BaseModel):
    service: str   # e.g. "smtp", "slack", "discord"
    key: str       # e.g. "host", "user", "password", "webhook_url"
    value: str


@router.get("/")
async def get_integrations():
    return {"integrations": list_credentials()}


@router.post("/")
async def save_integration(req: CredentialRequest):
    save_credential(req.service, req.key, req.value)
    return {"success": True}


@router.delete("/{service}/{key}")
async def delete_integration(service: str, key: str):
    delete_credential(service, key)
    return {"success": True}


@router.get("/smtp/test")
async def test_smtp():
    """Test if SMTP is configured."""
    host = get_credential("smtp", "host")
    user = get_credential("smtp", "user")
    if not host or not user:
        return {"configured": False, "message": "SMTP not configured"}
    return {"configured": True, "host": host, "user": user[:3] + "***"}
