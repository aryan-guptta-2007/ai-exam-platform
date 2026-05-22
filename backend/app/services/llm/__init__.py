from typing import Optional
from app.core.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.gemini import GeminiProvider, GeminiProProvider
from app.services.llm.openai import OpenAIProvider, GPT4Provider
from app.services.llm.mock import MockLLMProvider
from loguru import logger

_providers = {
    "openai": OpenAIProvider,
    "gpt4": GPT4Provider,
    "gemini": GeminiProvider,
    "gemini-pro": GeminiProProvider,
    "mock": MockLLMProvider,
}

def get_llm_provider(provider_name: Optional[str] = None) -> BaseLLMProvider:
    """
    Factory to retrieve an LLM provider based on settings or name.
    """
    # If API keys are set to placeholder values, default to mock provider for local testing
    if not provider_name and (
        not settings.OPENAI_API_KEY 
        or "your" in settings.OPENAI_API_KEY.lower() 
        or "placeholder" in settings.OPENAI_API_KEY.lower()
    ):
        if settings.PRIMARY_LLM_PROVIDER == "openai" or settings.PRIMARY_LLM_PROVIDER == "gemini":
            logger.info("Placeholder or missing API keys detected. Defaulting to 'mock' LLM provider for testing.")
            return MockLLMProvider()

    name = provider_name or settings.PRIMARY_LLM_PROVIDER
    name = name.lower()

    if name in _providers:
        provider_class = _providers[name]
        logger.debug(f"Instantiating LLM Provider: {name}")
        return provider_class()
    else:
        logger.warning(f"Unknown provider '{name}'. Falling back to primary configuration.")
        primary = settings.PRIMARY_LLM_PROVIDER.lower()
        if primary in _providers:
            return _providers[primary]()
        return MockLLMProvider() # Default safety fallback
