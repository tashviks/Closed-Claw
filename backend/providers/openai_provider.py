"""
OpenAI provider (also used for OpenRouter — same API shape)
"""
import json
import httpx
from typing import AsyncIterator
from providers.base import BaseProvider, ChatRequest


class OpenAIProvider(BaseProvider):
    def __init__(self, api_key: str, base_url: str = "https://api.openai.com/v1"):
        self.api_key = api_key
        # Normalize: ensure no double slashes but preserve trailing slash intent
        self.base_url = base_url.rstrip("/")
        # Google's endpoint requires the path to end at /openai, completions appended after
        # so we just store as-is without trailing slash and append /chat/completions

    def _headers(self):
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "HTTP-Referer": "https://openclaw.app",
            "X-Title": "ClosedClaw",
        }

    def _build_payload(self, request: ChatRequest, stream: bool) -> dict:
        messages = [m.model_dump(exclude_none=True) for m in request.messages]
        import logging
        logging.getLogger("openclaw").info(f"Sending model='{request.model}' to {self.base_url}")
        payload = {
            "model": request.model,  # already stripped of provider prefix by chat router
            "messages": messages,
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
            "stream": stream,
        }
        if request.tools:
            payload["tools"] = request.tools
            payload["tool_choice"] = "auto"
        return payload

    async def chat_stream(self, request: ChatRequest) -> AsyncIterator[str]:
        payload = self._build_payload(request, stream=True)
        async with httpx.AsyncClient(timeout=120) as client:
            async with client.stream(
                "POST",
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            ) as resp:
                if resp.status_code == 429:
                    body = await resp.aread()
                    try:
                        err_data = json.loads(body)
                        err_msg = err_data[0]["error"]["message"] if isinstance(err_data, list) else err_data.get("error", {}).get("message", "")
                    except Exception:
                        err_msg = ""

                    retry_after = resp.headers.get("Retry-After", "")

                    if "quota" in err_msg.lower() or "billing" in err_msg.lower():
                        raise Exception(
                            "Daily quota exceeded for this API key. "
                            "The free tier limit has been reached — it resets at midnight Pacific time. "
                            "Add a paid API key or switch to a different provider in Settings."
                        )
                    elif retry_after:
                        raise Exception(
                            "Rate limit reached. Please wait " + retry_after + "s before trying again."
                        )
                    else:
                        raise Exception(
                            "Rate limit reached. Please wait a minute before trying again, "
                            "or switch to a different model in the model selector."
                        )
                resp.raise_for_status()
                async for line in resp.aiter_lines():
                    if line.startswith("data: "):
                        chunk = line[6:]
                        if chunk == "[DONE]":
                            return
                        try:
                            data = json.loads(chunk)
                            delta = data["choices"][0].get("delta", {})
                            if "content" in delta and delta["content"]:
                                yield delta["content"]
                            if "tool_calls" in delta:
                                yield json.dumps({"tool_calls": delta["tool_calls"]})
                        except (json.JSONDecodeError, KeyError, IndexError):
                            continue

    async def chat(self, request: ChatRequest) -> dict:
        payload = self._build_payload(request, stream=False)
        async with httpx.AsyncClient(timeout=120) as client:
            resp = await client.post(
                f"{self.base_url}/chat/completions",
                headers=self._headers(),
                json=payload,
            )
            if resp.status_code == 429:
                err_data = resp.json()
                err_msg = err_data.get("error", {}).get("message", "")
                raise Exception(f"Rate limit reached: {err_msg}")
            resp.raise_for_status()
            return resp.json()
