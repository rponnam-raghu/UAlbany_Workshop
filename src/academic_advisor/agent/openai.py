"""OpenAI Responses and embeddings adapter; native output stays intact in tool loops."""
import json
from typing import Any, Literal

import numpy as np
from google.genai import types
from openai import OpenAI as SDK

from academic_advisor.agent.errors import ProviderError
from academic_advisor.config import Settings


class OpenAI:
    def __init__(self, settings: Settings):
        if not settings.configured("openai"):
            raise ValueError("Set OPENAI_API_KEY in .env, then recreate the app container.")
        self.settings = settings
        self.client = SDK(api_key=settings.openai_api_key.get_secret_value(), timeout=45, max_retries=0)
        # The common runtime uses Content envelopes. Keep OpenAI native output alongside
        # each returned envelope, including reasoning items and original call IDs.
        self._native: dict[int, tuple[types.Content, list[Any]]] = {}

    @staticmethod
    def _error(error: Exception) -> ProviderError:
        code = getattr(error, "status_code", None)
        messages = {
            401: "OpenAI authentication failed. Check OPENAI_API_KEY.",
            403: "OpenAI access denied. Check project permissions.",
            404: "The configured OpenAI model is unavailable. Check the model settings.",
            429: "OpenAI quota or rate limit reached. Check billing and usage limits.",
            400: "OpenAI rejected the request. Check model and tool configuration.",
        }
        return ProviderError(messages.get(code if isinstance(code, int) else 0, "OpenAI could not complete the request. Check connectivity and retry."))

    def generate(self, system: str, history: list[types.Content], schemas: list[dict[str, Any]]) -> types.Content:
        items: list[Any] = []
        for content in history:
            native = self._native.get(id(content))
            if native is not None:
                items.extend(native[1])
                continue
            for part in content.parts or []:
                if part.function_response:
                    response = part.function_response
                    items.append({"type": "function_call_output", "call_id": response.id,
                                  "output": json.dumps(response.response)})
                elif part.text and not part.thought:
                    items.append({"role": "assistant" if content.role == "model" else "user", "content": part.text})
        tools = [{"type": "function", "name": schema["name"], "description": schema["description"],
                  "parameters": schema["parameters_json_schema"], "strict": False} for schema in schemas]
        try:
            result = self.client.responses.create(model=self.settings.openai_model, instructions=system,
                input=items, tools=tools, max_output_tokens=4096, store=False)  # type: ignore[arg-type]
            if result.status != "completed":
                raise ProviderError("OpenAI returned an incomplete response. Retry the request.")
            parts: list[types.Part] = []
            for item in result.output:
                if item.type == "function_call":
                    try:
                        args = json.loads(item.arguments)
                        if not isinstance(args, dict):
                            raise ValueError("Expected object")
                    except (ValueError, TypeError):
                        raise ProviderError("OpenAI returned invalid tool arguments. Retry the request.") from None
                    parts.append(types.Part(function_call=types.FunctionCall(name=item.name, id=item.call_id, args=args)))
                elif item.type == "message":
                    for block in item.content:
                        if block.type == "output_text":
                            parts.append(types.Part(text=block.text))
                        elif block.type == "refusal":
                            parts.append(types.Part(text=block.refusal))
            if not parts:
                raise ProviderError("OpenAI returned no usable response. Try a different question.")
            content = types.Content(role="model", parts=parts)
            self._native[id(content)] = (content, list(result.output))
            return content
        except ProviderError:
            raise
        except Exception as error:
            raise self._error(error) from None

    def embed(self, texts: list[str], task: Literal["RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]) -> list[list[float]]:
        if not texts:
            return []
        try:
            response = self.client.embeddings.create(model=self.settings.openai_embedding_model,
                input=texts, dimensions=self.settings.openai_embedding_dimension, encoding_format="float")
            data = sorted(response.data, key=lambda item: item.index)
            if [item.index for item in data] != list(range(len(texts))):
                raise ValueError("Incomplete embeddings")
            vectors = []
            for item in data:
                vector = np.asarray(item.embedding, dtype=float)
                norm = float(np.linalg.norm(vector))
                if vector.shape != (self.settings.openai_embedding_dimension,) or not np.isfinite(vector).all() or not norm:
                    raise ValueError("Invalid embedding")
                vectors.append((vector / norm).tolist())
            return vectors
        except Exception as error:
            raise self._error(error) from None
