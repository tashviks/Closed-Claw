"""
Base provider interface + model registry
"""
from __future__ import annotations
from abc import ABC, abstractmethod
from typing import AsyncIterator, List, Optional
from pydantic import BaseModel


class Message(BaseModel):
    role: str  # system | user | assistant | tool
    content: str
    tool_calls: Optional[list] = None
    tool_call_id: Optional[str] = None
    name: Optional[str] = None


class ChatRequest(BaseModel):
    model: str
    messages: List[Message]
    temperature: float = 0.7
    max_tokens: int = 4096
    tools: Optional[list] = None
    stream: bool = True


class BaseProvider(ABC):
    @abstractmethod
    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        ...

    @abstractmethod
    async def chat(self, request: ChatRequest) -> dict:
        ...


# ── Model registry ────────────────────────────────────────────────────────────
MODELS = {
    # OpenAI
    "openai/gpt-4o": {"provider": "openai", "context": 128000, "free": False, "supports_thinking": False},
    "openai/gpt-4o-mini": {"provider": "openai", "context": 128000, "free": False, "supports_thinking": False},
    "openai/o3-mini": {"provider": "openai", "context": 200000, "free": False, "supports_thinking": True},
    "openai/o4-mini": {"provider": "openai", "context": 200000, "free": False, "supports_thinking": True},
    # Anthropic
    "anthropic/claude-opus-4-5": {"provider": "anthropic", "context": 200000, "free": False, "supports_thinking": True},
    "anthropic/claude-sonnet-4-5": {"provider": "anthropic", "context": 200000, "free": False, "supports_thinking": True},
    "anthropic/claude-3-5-sonnet": {"provider": "anthropic", "context": 200000, "free": False, "supports_thinking": False},
    "anthropic/claude-3-haiku": {"provider": "anthropic", "context": 200000, "free": False, "supports_thinking": False},
    # Groq (fast inference)
    "groq/llama-3.3-70b-versatile": {"provider": "groq", "context": 128000, "free": False, "supports_thinking": False},
    "groq/llama-3.1-8b-instant": {"provider": "groq", "context": 128000, "free": False, "supports_thinking": False},
    "groq/mixtral-8x7b-32768": {"provider": "groq", "context": 32768, "free": False, "supports_thinking": False},
    "groq/gemma2-9b-it": {"provider": "groq", "context": 8192, "free": False, "supports_thinking": False},
    # Perplexity (web search built-in)
    "perplexity/sonar": {"provider": "perplexity", "context": 127072, "free": False, "supports_thinking": False},
    "perplexity/sonar-pro": {"provider": "perplexity", "context": 127072, "free": False, "supports_thinking": False},
    "perplexity/sonar-reasoning": {"provider": "perplexity", "context": 127072, "free": False, "supports_thinking": True},
    # Ollama (local models — no API key needed)
    "ollama/llama3.2": {"provider": "ollama", "context": 128000, "free": True, "supports_thinking": False},
    "ollama/llama3.1": {"provider": "ollama", "context": 128000, "free": True, "supports_thinking": False},
    "ollama/mistral": {"provider": "ollama", "context": 32768, "free": True, "supports_thinking": False},
    "ollama/qwen2.5-coder": {"provider": "ollama", "context": 32768, "free": True, "supports_thinking": False},
    "ollama/deepseek-r1": {"provider": "ollama", "context": 64000, "free": True, "supports_thinking": True},
    # OpenRouter (free tier) — verified working March 2026
    "openrouter/meta-llama/llama-3.3-70b-instruct:free": {"provider": "openrouter", "context": 65536, "free": True, "supports_thinking": False},
    "openrouter/mistralai/mistral-small-3.1-24b-instruct:free": {"provider": "openrouter", "context": 128000, "free": True, "supports_thinking": False},
    "openrouter/nvidia/nemotron-3-super-120b-a12b:free": {"provider": "openrouter", "context": 262144, "free": True, "supports_thinking": False},
    "openrouter/qwen/qwen3-coder:free": {"provider": "openrouter", "context": 262000, "free": True, "supports_thinking": False},
    "openrouter/nousresearch/hermes-3-llama-3.1-405b:free": {"provider": "openrouter", "context": 131072, "free": True, "supports_thinking": False},
    "openrouter/google/gemma-3-27b-it:free": {"provider": "openrouter", "context": 131072, "free": True, "supports_thinking": False},
    "openrouter/stepfun/step-3.5-flash:free": {"provider": "openrouter", "context": 256000, "free": True, "supports_thinking": False},
    # OpenRouter paid
    "openrouter/openai/gpt-4o": {"provider": "openrouter", "context": 128000, "free": False, "supports_thinking": False},
    "openrouter/anthropic/claude-3.5-sonnet": {"provider": "openrouter", "context": 200000, "free": False, "supports_thinking": False},
    "openrouter/deepseek/deepseek-r1": {"provider": "openrouter", "context": 163840, "free": False, "supports_thinking": True},
    # Google
    "google/gemini-2.5-flash": {"provider": "google", "context": 1048576, "free": False, "supports_thinking": True},
    "google/gemini-2.5-pro": {"provider": "google", "context": 1048576, "free": False, "supports_thinking": True},
    "google/gemini-2.0-flash": {"provider": "google", "context": 1048576, "free": False, "supports_thinking": False},
    "google/gemini-2.0-flash-lite": {"provider": "google", "context": 1048576, "free": False, "supports_thinking": False},
    # Mistral
    "mistral/mistral-large-latest": {"provider": "mistral", "context": 131072, "free": False, "supports_thinking": False},
    "mistral/mistral-small-latest": {"provider": "mistral", "context": 131072, "free": False, "supports_thinking": False},
    "mistral/codestral-latest": {"provider": "mistral", "context": 256000, "free": False, "supports_thinking": False},
}


def get_provider_for_model(model_id: str) -> str:
    if model_id in MODELS:
        return MODELS[model_id]["provider"]
    # Fallback: infer from prefix
    if "/" in model_id:
        return model_id.split("/")[0]
    return "openai"
