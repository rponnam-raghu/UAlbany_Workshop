"""Small Gemini adapter. Raw provider exceptions never reach the UI or logs."""

from typing import Any, Literal

import numpy as np
from google import genai
from google.genai import types

from academic_advisor.agent.errors import ProviderError as ProviderError
from academic_advisor.config import Settings


def provider_error(error: Exception) -> ProviderError:
    code = getattr(error, "code", None)
    if code in (401, 403):
        message = "Gemini authentication failed. Check the API key and project permissions in .env."
    elif code == 404:
        message = "The configured Gemini model is unavailable. Check GEMINI_MODEL in .env."
    elif code == 429:
        message = "Gemini quota or rate limit reached. Wait or check the project's API quota."
    elif code == 400:
        message = "Gemini rejected the request. Check the API key, model, and tool configuration."
    else:
        message = "Gemini could not complete the request. Check connectivity and try again."
    return ProviderError(message)


class Gemini:
    def __init__(self, settings: Settings):
        self.settings = settings
        self.client = genai.Client(
            api_key=settings.require_key(),
            http_options=types.HttpOptions(timeout=45000),
        )

    def generate(
        self, system: str, history: list[types.Content], schemas: list[dict[str, Any]]
    ) -> types.Content:
        tools = (
            [types.Tool(function_declarations=[types.FunctionDeclaration(**s) for s in schemas])]
            if schemas
            else None
        )
        contents: list[types.ContentUnionDict] = list(history)
        try:
            response = self.client.models.generate_content(
                model=self.settings.gemini_model,
                contents=contents,
                config=types.GenerateContentConfig(
                    system_instruction=system,
                    tools=[item for item in tools] if tools else None,
                    automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),
                    max_output_tokens=4096,
                ),
            )
        except Exception as error:
            raise provider_error(error) from None
        if not response.candidates or response.candidates[0].content is None:
            raise ProviderError("Gemini returned no usable response. Try a different question.")
        return response.candidates[0].content

    def embed(
        self, texts: list[str], task: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
    ) -> list[list[float]]:
        if not texts:
            return []
        contents: list[types.ContentUnionDict] = list(texts)
        try:
            response = self.client.models.embed_content(
                model=self.settings.embedding_model,
                contents=contents,
                config=types.EmbedContentConfig(
                    task_type=task, output_dimensionality=self.settings.embedding_dimension
                ),
            )
            vectors = []
            for item in response.embeddings or []:
                vector = np.asarray(item.values, dtype=float)
                norm = float(np.linalg.norm(vector))
                if vector.shape != (self.settings.embedding_dimension,) or not np.isfinite(vector).all() or not norm:
                    raise ValueError("Invalid embedding.")
                vectors.append((vector / norm).tolist())
            if len(vectors) != len(texts):
                raise ValueError("Incomplete embeddings.")
            return vectors
        except Exception as error:
            raise provider_error(error) from None
