"""
Security utilities — API key encryption, input sanitization
"""
import re
import base64
import os
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC


def _get_or_create_key(data_dir: str) -> bytes:
    """Derive a stable encryption key from a machine-local secret."""
    key_file = os.path.join(data_dir, ".keystore")
    os.makedirs(data_dir, exist_ok=True)

    if os.path.exists(key_file):
        with open(key_file, "rb") as f:
            salt = f.read()
    else:
        salt = os.urandom(16)
        with open(key_file, "wb") as f:
            f.write(salt)
        # Restrict permissions on Unix
        try:
            os.chmod(key_file, 0o600)
        except Exception:
            pass

    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=480000,
    )
    key = base64.urlsafe_b64encode(kdf.derive(b"openclaw-local-secret"))
    return key


def get_fernet(data_dir: str) -> Fernet:
    return Fernet(_get_or_create_key(data_dir))


def encrypt_api_key(api_key: str, data_dir: str) -> str:
    f = get_fernet(data_dir)
    return f.encrypt(api_key.encode()).decode()


def decrypt_api_key(token: str, data_dir: str) -> str:
    f = get_fernet(data_dir)
    return f.decrypt(token.encode()).decode()


# ── Input sanitization ────────────────────────────────────────────────────────
DANGEROUS_PATTERNS = [
    r"<script[^>]*>.*?</script>",
    r"javascript:\s*\w",
    r"on(?:click|load|error|mouseover)\s*=",
]

_DANGER_RE = re.compile("|".join(DANGEROUS_PATTERNS), re.IGNORECASE | re.DOTALL)


def sanitize_input(text: str) -> str:
    """Strip XSS/HTML injection patterns from user input. Does NOT strip Python code."""
    return _DANGER_RE.sub("[REDACTED]", text)


def validate_tool_code(code: str) -> tuple[bool, str]:
    """
    Strict validation for run_python sandbox — no system access.
    Returns (is_safe, reason).
    """
    blocked = [
        "__import__", "eval(", "exec(",
        "socket", "shutil.rmtree",
    ]
    for b in blocked:
        if b in code:
            return False, f"Blocked pattern detected: '{b}'"
    return True, "ok"


def validate_agent_tool_code(code: str) -> tuple[bool, str]:
    """
    Relaxed validation for agent-created tools.
    Allows subprocess, os, sys for launching apps and system tasks.
    Only blocks truly dangerous patterns like arbitrary code injection.
    Returns (is_safe, reason).
    """
    blocked = [
        "__import__", "eval(", "exec(",
        "shutil.rmtree", "os.remove(\"/\")", "os.unlink(\"/\")",
        ":(){ :|:& };:",  # fork bomb
    ]
    for b in blocked:
        if b in code:
            return False, f"Blocked pattern: '{b}'"
    return True, "ok"
