"""Configuration shared by CLI and UI; credentials are never rendered."""

from pathlib import Path

from pydantic import Field, SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

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
