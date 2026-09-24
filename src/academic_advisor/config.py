"""Configuration shared by CLI and UI; credentials are never rendered."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: SecretStr = SecretStr("")
    openai_model: str = "gpt-4.1-mini"
    openai_embedding_model: str = "text-embedding-3-small"
    openai_embedding_dimension: int = Field(default=768, ge=128, le=1536)

    gemini_api_key: SecretStr = SecretStr("")
    gemini_model: str = "gemini-3.8-flash"
    embedding_model: str = "gemini-embedding-001"
    embedding_dimension: int = Field(default=768, ge=128, le=2000)
    database_url: SecretStr = SecretStr("postgresql://advisor:workshop@localhost:55432/advisor")
    fixture_dir: Path = Path("data/fixtures")
    runtime_dir: Path = Path("runtime")
    migration_dir: Path = Path("migrations")
    sample_dir: Path = Path("data/samples")
    max_tool_calls: int = Field(default=24, ge=1, le=40)

    def require_key(self) -> str:
        key = self.gemini_api_key.get_secret_value()
        if not key or key.startswith("replace_"):
            raise ValueError("Set GEMINI_API_KEY in .env, then restart the application.")
        return key

    def configured(self, provider: str) -> bool:
        secret = self.openai_api_key if provider == "openai" else self.gemini_api_key
        value = secret.get_secret_value()
        return bool(value and not value.startswith("replace_"))

    def default_provider(self) -> str:
        return "gemini" if self.configured("gemini") or not self.configured("openai") else "openai"

    def for_provider(self, provider: str) -> "Settings":
        if provider == "openai":
            return self.model_copy(update={"embedding_model": self.openai_embedding_model,
                                           "embedding_dimension": self.openai_embedding_dimension})
        return self

    def signature(self, provider: str) -> str:
        settings = self.for_provider(provider)
        return f"{provider}:{settings.embedding_model}:{settings.embedding_dimension}"
