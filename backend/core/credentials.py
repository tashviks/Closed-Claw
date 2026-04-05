"""
Credentials store — SMTP, webhooks, and other integration secrets.
Encrypted at rest, same as API keys.
"""
import os
from core.storage import load_json, save_json
from core.security import encrypt_api_key, decrypt_api_key
from core.config import get_settings

cfg = get_settings()
CREDS_FILE = "credentials.json"


def save_credential(service: str, key: str, value: str) -> None:
    data = load_json(CREDS_FILE, {})
    if service not in data:
        data[service] = {}
    data[service][key] = encrypt_api_key(value, cfg.data_dir)
    save_json(CREDS_FILE, data)


def get_credential(service: str, key: str) -> str:
    data = load_json(CREDS_FILE, {})
    encrypted = data.get(service, {}).get(key)
    if not encrypted:
        return ""
    try:
        return decrypt_api_key(encrypted, cfg.data_dir)
    except Exception:
        return ""


def list_credentials() -> dict:
    """Return masked credential keys."""
    data = load_json(CREDS_FILE, {})
    result = {}
    for service, keys in data.items():
        result[service] = {k: "***configured***" for k in keys}
    return result


def delete_credential(service: str, key: str) -> None:
    data = load_json(CREDS_FILE, {})
    if service in data and key in data[service]:
        del data[service][key]
        save_json(CREDS_FILE, data)
