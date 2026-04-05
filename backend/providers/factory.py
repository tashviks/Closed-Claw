"""
Provider factory — returns the right provider instance for a model ID.
"""
from providers.base import BaseProvider, get_provider_for_model
from providers.openai_provider import OpenAIProvider
from providers.anthropic_provider import AnthropicProvider


def get_provider(model_id: str, api_key: str) -> BaseProvider:
    provider_name = get_provider_for_model(model_id)

    if provider_name == "anthropic":
        return AnthropicProvider(api_key=api_key)

    if provider_name == "openrouter":
        return OpenAIProvider(api_key=api_key, base_url="https://openrouter.ai/api/v1")

    if provider_name == "google":
        return OpenAIProvider(
            api_key=api_key,
            base_url="https://generativelanguage.googleapis.com/v1beta/openai",
        )

    if provider_name == "mistral":
        return OpenAIProvider(api_key=api_key, base_url="https://api.mistral.ai/v1")

    if provider_name == "groq":
        return OpenAIProvider(api_key=api_key, base_url="https://api.groq.com/openai/v1")

    if provider_name == "perplexity":
        return OpenAIProvider(api_key=api_key, base_url="https://api.perplexity.ai")

    if provider_name == "ollama":
        # Ollama runs locally — no API key needed
        return OpenAIProvider(api_key="ollama", base_url="http://localhost:11434/v1")

    # Default: OpenAI
    return OpenAIProvider(api_key=api_key)
