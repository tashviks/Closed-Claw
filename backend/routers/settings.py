"""
Settings router — manage API keys and model preferences
"""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, field_validator
from core.storage import load_json, save_json
from core.security import encrypt_api_key, decrypt_api_key
from core.config import get_settings

router = APIRouter()
cfg = get_settings()

SETTINGS_FILE = "settings.json"


class ProviderKey(BaseModel):
    provider: str
    api_key: str

    @field_validator("provider")
    @classmethod
    def validate_provider(cls, v):
        allowed = {"openai", "anthropic", "openrouter", "google", "mistral", "cohere", "groq", "perplexity"}
        if v not in allowed:
            raise ValueError(f"Unknown provider: {v}")
        return v

    @field_validator("api_key")
    @classmethod
    def validate_key(cls, v):
        if len(v) < 8 or len(v) > 512:
            raise ValueError("Invalid API key length")
        return v


class AppSettings(BaseModel):
    theme: str = "dark"
    default_model: str = "openai/gpt-4o-mini"
    max_tokens: int = 4096
    temperature: float = 0.7
    stream_responses: bool = True
    sandbox_tools: bool = True
    auto_research: bool = False


@router.get("/")
async def get_settings_endpoint():
    data = load_json(SETTINGS_FILE, {})
    # Never return raw API keys
    providers = data.get("providers", {})
    masked = {k: "***" + v[-4:] if len(v) > 4 else "***" for k, v in providers.items()}
    return {
        "app": data.get("app", AppSettings().model_dump()),
        "providers": masked,
    }


@router.post("/provider-key")
async def save_provider_key(body: ProviderKey):
    data = load_json(SETTINGS_FILE, {})
    if "providers" not in data:
        data["providers"] = {}
    data["providers"][body.provider] = encrypt_api_key(body.api_key, cfg.data_dir)
    save_json(SETTINGS_FILE, data)
    return {"success": True}


@router.delete("/provider-key/{provider}")
async def delete_provider_key(provider: str):
    data = load_json(SETTINGS_FILE, {})
    data.get("providers", {}).pop(provider, None)
    save_json(SETTINGS_FILE, data)
    return {"success": True}


@router.put("/app")
async def update_app_settings(body: AppSettings):
    data = load_json(SETTINGS_FILE, {})
    data["app"] = body.model_dump()
    save_json(SETTINGS_FILE, data)
    return {"success": True}


def get_api_key(provider: str) -> str:
    """Internal helper — decrypt and return API key."""
    if provider == "ollama":
        return "ollama"  # Ollama runs locally, no key needed
    data = load_json(SETTINGS_FILE, {})
    encrypted = data.get("providers", {}).get(provider)
    if not encrypted:
        raise HTTPException(status_code=400, detail=f"No API key configured for {provider}")
    return decrypt_api_key(encrypted, cfg.data_dir)
