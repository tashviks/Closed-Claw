"""
ClosedClaw Backend — FastAPI entry point
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from routers import chat, tools, settings, research, sessions, monitor, commands, integrations
from core.config import get_settings

cfg = get_settings()

limiter = Limiter(key_func=get_remote_address)

app = FastAPI(
    title="ClosedClaw API",
    version="1.0.0",
    docs_url="/docs" if cfg.debug else None,
    redoc_url=None,
)

# ── Security middleware ───────────────────────────────────────────────────────
app.add_middleware(
    TrustedHostMiddleware,
    allowed_hosts=["localhost", "127.0.0.1"],
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE"],
    allow_headers=["Content-Type", "Authorization"],
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(chat.router, prefix="/api/chat", tags=["chat"])
app.include_router(tools.router, prefix="/api/tools", tags=["tools"])
app.include_router(settings.router, prefix="/api/settings", tags=["settings"])
app.include_router(research.router, prefix="/api/research", tags=["research"])
app.include_router(sessions.router, prefix="/api/sessions", tags=["sessions"])
app.include_router(monitor.router, prefix="/api/monitor", tags=["monitor"])
app.include_router(commands.router, prefix="/api/commands", tags=["commands"])
app.include_router(integrations.router, prefix="/api/integrations", tags=["integrations"])


@app.get("/health")
async def health():
    return {"status": "ok", "version": "1.0.0"}
