"""LLM abstraction package for MerchantOS AI."""

from merchantos_core.llm.prompts import build_merchant_prompt
from merchantos_core.llm.provider import AbstractLLMProvider, MockLLMProvider

__all__ = [
    "AbstractLLMProvider",
    "MockLLMProvider",
    "build_merchant_prompt",
]
