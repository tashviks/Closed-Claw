"""
Local JSON-based persistence for settings, sessions, tools.
"""
import json
import os
from typing import Any
from core.config import get_settings

cfg = get_settings()


def _path(filename: str) -> str:
    os.makedirs(cfg.data_dir, exist_ok=True)
    return os.path.join(cfg.data_dir, filename)


def load_json(filename: str, default: Any = None) -> Any:
    p = _path(filename)
    if not os.path.exists(p):
        return default if default is not None else {}
    with open(p, "r") as f:
        return json.load(f)


def save_json(filename: str, data: Any) -> None:
    p = _path(filename)
    with open(p, "w") as f:
        json.dump(data, f, indent=2)
    try:
        os.chmod(p, 0o600)
    except Exception:
        pass
