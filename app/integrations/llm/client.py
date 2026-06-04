"""LLM client — Gemini implementation and provider factory.

The factory function get_llm_client() is the only entry point business code
should use. It reads the provider from config and returns the right LLMClient
subclass, so swapping providers only requires changing config — not service code.
"""
import asyncio
import logging

from google import genai
from google.genai import types

from app.core.config import get_settings
from app.integrations.llm.base import LLMClient

logger = logging.getLogger(__name__)


class GeminiClient(LLMClient):
    """Gemini implementation of LLMClient using the google-genai SDK.

    Uses asyncio.wait_for() to enforce a hard timeout on every call so a
    slow or unresponsive API never hangs the request indefinitely.
    """

    def __init__(self) -> None:
        settings = get_settings()
        self._client = genai.Client(api_key=settings.gemini_api_key)
        self._model = settings.gemini_model
        self._timeout = settings.llm_timeout_seconds

    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        config = types.GenerateContentConfig(
            system_instruction=system_prompt,
        )
        try:
            response = await asyncio.wait_for(
                asyncio.to_thread(
                    self._client.models.generate_content,
                    model=self._model,
                    contents=user_prompt,
                    config=config,
                ),
                timeout=self._timeout,
            )
            return response.text
        except asyncio.TimeoutError:
            logger.error("LLM call timed out after %ds", self._timeout)
            raise
        except Exception as exc:
            logger.error("LLM call failed: %s", exc)
            raise


def get_llm_client() -> LLMClient:
    """Factory — returns the configured LLM provider.

    Adding a new provider (OpenAI, Anthropic, local model) only requires a
    new elif branch and a new subclass — no changes to business code.
    """
    settings = get_settings()

    if settings.gemini_api_key:
        return GeminiClient()

    raise RuntimeError(
        "No LLM provider configured. Set GEMINI_API_KEY in .env to enable draft generation."
    )
