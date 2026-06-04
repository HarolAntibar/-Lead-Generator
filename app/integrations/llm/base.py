"""LLM adapter interface — provider-agnostic contract.

Any concrete LLM provider (Gemini, OpenAI, Claude, etc.) must subclass
LLMClient and implement generate(). Business code only imports this base
class, so switching providers requires changing only client.py.
"""
from abc import ABC, abstractmethod


class LLMClient(ABC):
    @abstractmethod
    async def generate(self, system_prompt: str, user_prompt: str) -> str:
        """Send a prompt to the LLM and return the text response.

        *system_prompt* sets the model's role and output rules.
        *user_prompt* contains the task-specific content (business data, channel, etc.).
        Both are assembled by prompts.py — never built ad-hoc in service code.
        """
