"""
Anthropic Claude provider
"""
import json
import httpx
from typing import AsyncIterator
from providers.base import BaseProvider, ChatRequest


class AnthropicProvider(BaseProvider):
    BASE_URL = "https://api.anthropic.com/v1"

    def __init__(self, api_key: str):
        self.api_key = api_key

    def _headers(self):
        return {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "Content-Type": "application/json",
        }

    def _build_payload(self, request: ChatRequest, stream: bool) -> dict:
        system = ""
        messages = []
        for m in request.messages:
            if m.role == "system":
                system = m.content
            else:
                messages.append({"role": m.role, "content": m.content})

        model = request.model.replace("anthropic/", "")
        payload = {
            "model": model,
            "messages": messages,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "stream": stream,
        }
        if system:
            payload["system"] = system
        if request.tools:
            payload["tools"] = [
                {
                    "name": t["function"]["name"],
                    "description": t["function"].get("description", ""),
                    "input_schema": t["function"].get("parameters", {}),
                }
                for t in request.tools
            ]
        return payload

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request, stream=True)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code == 429:
                    body = await resp.aread()
                    try:
                        err_data = json.loads(body)
                        err_msg = err_data.get("error", {}).get("message", "")
                    except Exception:
                        err_msg = ""

                    retry_after = resp.headers.get("retry-after", "")

                    if "quota" in err_msg.lower() or "credits" in err_msg.lower():
                        raise Exception(
                            "Daily quota exceeded for Claude API. "
                            "Add credits to your Anthropic account or switch to a different provider in Settings."
                        )
                    elif retry_after:
                        raise Exception(
                            "Rate limit reached for Claude. Please wait " + retry_after + "s before trying again."
                        )
                    else:
                        raise Exception(
                            "Rate limit reached for Claude. Please wait a moment before trying again, "
                            "or switch to a different model in the model selector."
                        )
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            if data.get("type") == "content_block_delta":
                                delta = data.get("delta", {})
                                if delta.get("type") == "text_delta":
                                    yield delta.get("text", "")
                        except (json.JSONDecodeError, KeyError):
                            continue

    async def chat(self, request: ChatRequest) -> dict:
        payload = self._build_payload(request, stream=False)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.BASE_URL}/messages",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code == 429:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", "")
                raise Exception(f"Rate limit reached for Claude: {err_msg}")
            resp.raise_for_status()
            return resp.json()
