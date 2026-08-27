"""Configuration settings for MerchantOS AI using pydantic-settings."""

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_MOCK_WEBHOOK_SECRET = SecretStr("mock_webhook_secret_for_local_testing_only")


class Settings(BaseSettings):
    """Application settings with strict validation for mock vs live mode."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        case_sensitive=False,
    )

    razorpay_use_mock: bool = True
    razorpay_key_id: SecretStr | None = None
    razorpay_key_secret: SecretStr | None = None
    razorpay_webhook_secret: SecretStr | None = None
    razorpay_base_url: str = "https://api.razorpay.com"
    razorpay_request_timeout_seconds: float = 10.0

    @model_validator(mode="after")
    def validate_live_credentials(self) -> "Settings":
        """Fail fast if live mode is enabled but required secrets are missing."""
        if not self.razorpay_use_mock:
            missing_fields: list[str] = []
            if not self.razorpay_key_id or not self.razorpay_key_id.get_secret_value().strip():
                missing_fields.append("RAZORPAY_KEY_ID")
            if not self.razorpay_key_secret or not self.razorpay_key_secret.get_secret_value().strip():
                missing_fields.append("RAZORPAY_KEY_SECRET")
            if not self.razorpay_webhook_secret or not self.razorpay_webhook_secret.get_secret_value().strip():
                missing_fields.append("RAZORPAY_WEBHOOK_SECRET")

            if missing_fields:
                raise ValueError(
                    f"Live Razorpay mode requires the following credentials: {', '.join(missing_fields)}"
                )
        return self

    def get_effective_webhook_secret(self) -> SecretStr:
        """Return configured webhook secret, falling back to deterministic mock secret in mock mode."""
        if self.razorpay_webhook_secret is not None and self.razorpay_webhook_secret.get_secret_value().strip():
            return self.razorpay_webhook_secret
        if self.razorpay_use_mock:
            return DEFAULT_MOCK_WEBHOOK_SECRET
        raise ValueError("RAZORPAY_WEBHOOK_SECRET is required in live mode")
