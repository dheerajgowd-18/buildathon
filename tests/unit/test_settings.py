"""Unit tests for configuration settings."""

import pytest
from pydantic import SecretStr, ValidationError

from merchantos_core.config import DEFAULT_MOCK_WEBHOOK_SECRET, Settings


def test_mock_mode_works_without_credentials() -> None:
    """In mock mode, Settings instantiate without credentials and supply fallback webhook secret."""
    settings = Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=True)
    assert settings.razorpay_use_mock is True
    assert settings.razorpay_key_id is None
    assert settings.razorpay_key_secret is None
    assert settings.llm_use_mock is True
    assert settings.llm_api_key is None
    assert settings.get_effective_webhook_secret() == DEFAULT_MOCK_WEBHOOK_SECRET


def test_mock_mode_with_custom_webhook_secret() -> None:
    """If custom webhook secret is provided in mock mode, it is honored."""
    custom_secret = SecretStr("custom_mock_wh_secret")
    settings = Settings(
        _env_file=None,
        razorpay_use_mock=True,
        llm_use_mock=True,
        razorpay_webhook_secret=custom_secret,
    )
    assert settings.get_effective_webhook_secret() == custom_secret


def test_live_mode_fails_fast_when_secrets_missing() -> None:
    """In live mode, missing key id, secret, or webhook secret must raise validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, razorpay_use_mock=False, llm_use_mock=True)
    err_str = str(exc_info.value)
    assert "RAZORPAY_KEY_ID" in err_str
    assert "RAZORPAY_KEY_SECRET" in err_str
    assert "RAZORPAY_WEBHOOK_SECRET" in err_str


def test_live_llm_mode_fails_fast_when_api_key_missing() -> None:
    """In live LLM mode, missing LLM_API_KEY must raise validation error."""
    with pytest.raises(ValidationError) as exc_info:
        Settings(_env_file=None, razorpay_use_mock=True, llm_use_mock=False)
    err_str = str(exc_info.value)
    assert "LLM_API_KEY" in err_str


def test_live_mode_passes_with_all_secrets() -> None:
    """In live mode, providing all required secrets passes validation."""
    settings = Settings(
        _env_file=None,
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("rzp_test_key"),
        razorpay_key_secret=SecretStr("rzp_test_secret"),
        razorpay_webhook_secret=SecretStr("rzp_test_whsec"),
        llm_use_mock=False,
        llm_api_key=SecretStr("gsk_test_api_key"),
    )
    assert settings.razorpay_use_mock is False
    assert settings.llm_use_mock is False
    assert settings.get_effective_webhook_secret().get_secret_value() == "rzp_test_whsec"


def test_secrets_not_exposed_in_repr() -> None:
    """SecretStr fields must never expose plaintext in __str__ or __repr__."""
    settings = Settings(
        _env_file=None,
        razorpay_use_mock=False,
        razorpay_key_id=SecretStr("sensitive_key_id"),
        razorpay_key_secret=SecretStr("sensitive_key_secret"),
        razorpay_webhook_secret=SecretStr("sensitive_webhook_secret"),
        llm_use_mock=False,
        llm_api_key=SecretStr("sensitive_llm_key"),
    )
    repr_str = repr(settings)
    str_str = str(settings)
    assert "sensitive_key_id" not in repr_str
    assert "sensitive_key_secret" not in repr_str
    assert "sensitive_webhook_secret" not in repr_str
    assert "sensitive_llm_key" not in repr_str
    assert "sensitive_key_id" not in str_str
    assert "sensitive_llm_key" not in str_str
