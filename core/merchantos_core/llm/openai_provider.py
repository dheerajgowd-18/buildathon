"""OpenAI-compatible LLM Provider implementation for real API integration."""

from __future__ import annotations

import json
import logging
from pydantic import SecretStr, ValidationError

from merchantos_core.contracts import LLMOutput
from merchantos_core.llm.provider import AbstractLLMProvider

logger = logging.getLogger(__name__)


class LLMProviderError(Exception):
    """Base exception for LLM provider errors."""


class LLMParsingError(LLMProviderError):
    """Raised when LLM response cannot be parsed into valid LLMOutput."""


class OpenAICompatibleLLMProvider(AbstractLLMProvider):
    """Real LLM provider calling OpenAI-compatible endpoints (Grok/Groq/OpenAI)."""

    def __init__(
        self,
        api_key: SecretStr,
        base_url: str = "https://api.groq.com/openai/v1",
        model: str = "openai/gpt-oss-120b",
        timeout_seconds: float = 30.0,
    ) -> None:
        from openai import OpenAI

        self.api_key = api_key
        self.base_url = base_url
        self.model = model
        self.timeout_seconds = timeout_seconds
        self.client = OpenAI(
            api_key=api_key.get_secret_value(),
            base_url=base_url,
            timeout=timeout_seconds,
        )

    def generate_offer_proposal(self, system_prompt: str, user_prompt: str) -> LLMOutput:
        """Call OpenAI-compatible chat completion endpoint and parse response into LLMOutput.

        Args:
            system_prompt: System prompt with instructions and JSON schema definition.
            user_prompt: User prompt containing buyer utterance, catalog, and policies.

        Returns:
            Validated LLMOutput model.

        Raises:
            LLMParsingError: If response is not valid JSON or violates LLMOutput schema.
            LLMProviderError: If API call fails (network, auth, rate limit, etc.).
        """
        try:
            # Try requesting structured JSON object response format
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                response_format={"type": "json_object"},
                temperature=0.2,
            )
        except Exception as err:
            err_msg = str(err)
            # If response_format json_object is not supported by endpoint, retry without response_format
            if "response_format" in err_msg or "unsupported" in err_msg.lower():
                try:
                    response = self.client.chat.completions.create(
                        model=self.model,
                        messages=[
                            {"role": "system", "content": system_prompt},
                            {"role": "user", "content": user_prompt},
                        ],
                        temperature=0.2,
                    )
                except Exception as fallback_err:
                    raise LLMProviderError(f"OpenAI-compatible API request failed: {fallback_err}") from fallback_err
            else:
                raise LLMProviderError(f"OpenAI-compatible API request failed: {err}") from err

        if not response.choices or not response.choices[0].message:
            raise LLMParsingError("LLM response did not contain any choices or message content")

        raw_content = response.choices[0].message.content
        if not raw_content or not raw_content.strip():
            raise LLMParsingError("LLM returned empty message content")

        # Parse JSON content
        try:
            cleaned_content = raw_content.strip()
            if cleaned_content.startswith("```json"):
                cleaned_content = cleaned_content[7:]
            elif cleaned_content.startswith("```"):
                cleaned_content = cleaned_content[3:]
            if cleaned_content.endswith("```"):
                cleaned_content = cleaned_content[:-3]
            cleaned_content = cleaned_content.strip()

            parsed_dict = json.loads(cleaned_content)
        except Exception as err:
            raise LLMParsingError(
                f"Failed to parse LLM response as JSON: {err}. Raw content: {raw_content[:200]}"
            ) from err

        if not isinstance(parsed_dict, dict):
            raise LLMParsingError(f"Expected JSON object in LLM response, got {type(parsed_dict).__name__}")

        try:
            return LLMOutput.model_validate(parsed_dict)
        except ValidationError as err:
            raise LLMParsingError(f"LLM JSON output does not match LLMOutput schema: {err}") from err

    def ping(self) -> str:
        """Lightweight connectivity ping sending a minimal prompt to verify API credentials and reachability.

        Returns:
            The raw text reply from the LLM provider.
        """
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "user", "content": "Reply with the single word: READY"},
                ],
                max_tokens=8,
                temperature=0.0,
            )
            if not response.choices or not response.choices[0].message:
                raise LLMProviderError("No response message returned from ping completion.")
            return str(response.choices[0].message.content or "").strip()
        except Exception as err:
            raise LLMProviderError(f"LLM ping failed: {err}") from err

