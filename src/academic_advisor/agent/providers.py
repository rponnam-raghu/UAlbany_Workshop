"""Provider selection checks both capabilities and never mixes embedding spaces."""
from collections.abc import Callable
from hashlib import sha256
from typing import Literal, Protocol

from google.genai import types

from academic_advisor.agent.errors import ProviderError
from academic_advisor.agent.gemini import Gemini
from academic_advisor.agent.openai import OpenAI
from academic_advisor.agent.runtime import ModelClient
from academic_advisor.config import Settings

PROVIDERS = ("gemini", "openai")


class NoProviderAvailable(ProviderError):
    """Both candidates have already been considered."""


class ProviderClient(ModelClient, Protocol):
    def embed(self, texts: list[str], task: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]) -> list[list[float]]: ...


def create_client(settings: Settings, provider: str) -> ProviderClient:
    if provider not in PROVIDERS:
        raise ValueError("Unknown AI provider.")
    return OpenAI(settings) if provider == "openai" else Gemini(settings)


def config_token(settings: Settings) -> str:
    # Only a fingerprint is retained in session state, never plaintext credentials.
    values = [settings.gemini_api_key.get_secret_value(), settings.openai_api_key.get_secret_value(),
              settings.gemini_model, settings.openai_model, settings.signature("gemini"), settings.signature("openai")]
    return sha256("\0".join(values).encode()).hexdigest()


def validate(client: ProviderClient) -> None:
    result = client.generate("Reply with OK.", [types.Content(role="user", parts=[types.Part(text="Connection check")])], [])
    if not any(part.text for part in result.parts or []):
        raise ProviderError("The chat capability check returned no text.")
    client.embed(["Connection check"], "RETRIEVAL_DOCUMENT")
    client.embed(["Connection check"], "RETRIEVAL_QUERY")


def select_provider(settings: Settings, preferred: str, *, exclude: set[str] | None = None,
                    factory: Callable[[Settings, str], ProviderClient] = create_client) -> tuple[str, str, set[str]]:
    failures: list[str] = []
    failed = set(exclude or set())
    for provider in [preferred, *(p for p in PROVIDERS if p != preferred)]:
        if provider in (exclude or set()):
            continue
        if not settings.configured(provider):
            failed.add(provider)
            failures.append(f"{provider}: API key is not configured.")
            continue
        try:
            validate(factory(settings, provider))
            return provider, " ".join(failures), failed
        except (ValueError, ProviderError) as error:
            failed.add(provider)
            failures.append(f"{provider}: {error}")
    raise NoProviderAvailable("No working provider is available. " + " ".join(failures))
