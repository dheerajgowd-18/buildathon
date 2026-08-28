"""Integration tests for live validation and OpenAI-compatible LLM provider."""

from __future__ import annotations

from unittest.mock import MagicMock, patch
import pytest
from pydantic import SecretStr

from merchantos_core.contracts import LLMOutput
from merchantos_core.llm.openai_provider import (
    LLMParsingError,
    LLMProviderError,
    OpenAICompatibleLLMProvider,
)


def test_openai_provider_json_parsing() -> None:
    """Mock the OpenAI client response with a valid JSON string and verify parsing into LLMOutput."""
    provider = OpenAICompatibleLLMProvider(
        api_key=SecretStr("mock-key"),
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
    )

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '{\n'
        '  "selected_sku_id": "SKU-LAPTOP-PRO",\n'
        '  "proposed_price_minor": 5500000,\n'
        '  "discount_minor": 500000,\n'
        '  "shipping_tier": "express",\n'
        '  "rationale": "High value customer requesting developer workstation within budget."\n'
        '}'
    )
    mock_response.choices = [mock_choice]

    with patch.object(provider.client.chat.completions, "create", return_value=mock_response):
        result = provider.generate_offer_proposal(
            system_prompt="You are a merchant agent.",
            user_prompt="I want a laptop under 60k with fast delivery",
        )

    assert isinstance(result, LLMOutput)
    assert result.selected_sku_id == "SKU-LAPTOP-PRO"
    assert result.proposed_price_minor == 5500000
    assert result.discount_minor == 500000
    assert result.shipping_tier == "express"
    assert "High value customer" in result.rationale


def test_openai_provider_json_with_markdown_fences() -> None:
    """Verify provider strips markdown ```json code blocks correctly."""
    provider = OpenAICompatibleLLMProvider(
        api_key=SecretStr("mock-key"),
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
    )

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = (
        '```json\n'
        '{\n'
        '  "selected_sku_id": "SKU-LAPTOP-AIR",\n'
        '  "proposed_price_minor": 4800000,\n'
        '  "discount_minor": 200000,\n'
        '  "shipping_tier": "standard",\n'
        '  "rationale": "Standard budget offer."\n'
        '}\n'
        '```'
    )
    mock_response.choices = [mock_choice]

    with patch.object(provider.client.chat.completions, "create", return_value=mock_response):
        result = provider.generate_offer_proposal(
            system_prompt="You are a merchant agent.",
            user_prompt="Looking for air laptop",
        )

    assert result.selected_sku_id == "SKU-LAPTOP-AIR"
    assert result.proposed_price_minor == 4800000
    assert result.discount_minor == 200000
    assert result.shipping_tier == "standard"


def test_openai_provider_fallback_on_malformed_json() -> None:
    """Mock the OpenAI client response with garbage text and assert LLMParsingError is raised."""
    provider = OpenAICompatibleLLMProvider(
        api_key=SecretStr("mock-key"),
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
    )

    mock_response = MagicMock()
    mock_choice = MagicMock()
    mock_choice.message.content = "Sorry, as an AI language model I cannot output JSON right now."
    mock_response.choices = [mock_choice]

    with patch.object(provider.client.chat.completions, "create", return_value=mock_response):
        with pytest.raises(LLMParsingError) as exc_info:
            provider.generate_offer_proposal(
                system_prompt="You are a merchant agent.",
                user_prompt="I want a discount",
            )

    assert "Failed to parse LLM response as JSON" in str(exc_info.value)


def test_openai_provider_handles_api_exception() -> None:
    """Verify that network or API errors raise LLMProviderError."""
    provider = OpenAICompatibleLLMProvider(
        api_key=SecretStr("mock-key"),
        base_url="https://api.groq.com/openai/v1",
        model="openai/gpt-oss-120b",
    )

    with patch.object(provider.client.chat.completions, "create", side_effect=Exception("Connection refused")):
        with pytest.raises(LLMProviderError) as exc_info:
            provider.generate_offer_proposal(
                system_prompt="System",
                user_prompt="User",
            )

    assert "OpenAI-compatible API request failed" in str(exc_info.value)
