from types import SimpleNamespace
from unittest.mock import Mock

import pytest
from google.genai import types

from academic_advisor.agent.errors import ProviderError
from academic_advisor.agent.openai import OpenAI
from academic_advisor.agent.providers import NoProviderAvailable, config_token, select_provider
from academic_advisor.agent.runtime import run_turn
from academic_advisor.config import Settings
from academic_advisor.tools.handlers import build_registry


def settings(**kwargs):
    return Settings(_env_file=None, gemini_api_key="fake-gemini", openai_api_key="fake-openai", **kwargs)


class Probe:
    def __init__(self, failure=None):
        self.failure = failure
        self.calls = []

    def generate(self, *args):
        self.calls.append("chat")
        if self.failure == "chat":
            raise ProviderError("Chat unavailable")
        return types.Content(role="model", parts=[types.Part(text="OK")])

    def embed(self, texts, task):
        self.calls.append(task)
        if self.failure == task:
            raise ProviderError("Embedding unavailable")
        return [[1.0]]


@pytest.mark.parametrize("failure", ["chat", "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"])
def test_fallback_requires_both_capabilities(failure):
    models = {"gemini": Probe(failure), "openai": Probe()}
    chosen, notice, failed = select_provider(settings(), "gemini", factory=lambda s, p: models[p])
    assert chosen == "openai" and "gemini" in notice and failed == {"gemini"}
    assert models["openai"].calls == ["chat", "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]


def test_working_preference_does_not_probe_other_provider():
    factory = Mock(return_value=Probe())
    assert select_provider(settings(), "openai", factory=factory)[0] == "openai"
    assert factory.call_count == 1


def test_missing_key_and_both_failures_are_bounded():
    cfg = settings().model_copy(update={"gemini_api_key": settings().gemini_api_key.__class__("")})
    factory = Mock(return_value=Probe())
    assert select_provider(cfg, "gemini", factory=factory)[0] == "openai"
    assert factory.call_count == 1
    factory = Mock(return_value=Probe("chat"))
    with pytest.raises(NoProviderAvailable):
        select_provider(settings(), "gemini", factory=factory)
    assert factory.call_count == 2
    factory.reset_mock()
    with pytest.raises(NoProviderAvailable):
        select_provider(settings(), "gemini", exclude={"gemini"}, factory=factory)
    assert factory.call_count == 1


def test_configuration_is_secret_aware_and_invalidates_checks():
    cfg = settings()
    assert "fake-openai" not in repr(cfg)
    assert config_token(cfg) != config_token(settings(openai_model="different-model"))
    assert cfg.signature("gemini") != cfg.signature("openai")
    assert cfg.for_provider("openai").embedding_model == "text-embedding-3-small"


def adapter(monkeypatch):
    sdk = Mock()
    monkeypatch.setattr("academic_advisor.agent.openai.SDK", Mock(return_value=sdk))
    return OpenAI(settings()), sdk


def message(text):
    return SimpleNamespace(type="message", content=[SimpleNamespace(type="output_text", text=text)])


def test_openai_tools_keep_native_reasoning_and_call_ids(monkeypatch):
    model, sdk = adapter(monkeypatch)
    reasoning = SimpleNamespace(type="reasoning", id="opaque-reasoning", encrypted_content="opaque")
    call = SimpleNamespace(type="function_call", name="days_until", call_id="call-1", arguments='{"date_str":"2026-11-15"}')
    sdk.responses.create.side_effect = [SimpleNamespace(status="completed", output=[reasoning, call]), SimpleNamespace(status="completed", output=[message("Done")])]
    result = run_turn(model, "Help", [], "Calculate the remaining days", build_registry())
    assert result.text == "Done"
    payload = sdk.responses.create.call_args.kwargs
    assert payload["store"] is False
    assert payload["input"][1] is reasoning
    assert payload["input"][2] is call
    assert payload["input"][3]["call_id"] == "call-1"
    assert result.trace[0]["tool"] == "days_until"
    assert result.trace[0]["result"]["status"] == "ok"


def test_openai_bad_tool_json_does_not_execute(monkeypatch):
    model, sdk = adapter(monkeypatch)
    call = SimpleNamespace(type="function_call", name="days_until", call_id="x", arguments="[]")
    sdk.responses.create.return_value = SimpleNamespace(status="completed", output=[call])
    with pytest.raises(ProviderError, match="invalid tool arguments"):
        run_turn(model, "Help", [], "Hi", build_registry())


def test_openai_embeddings_validate_order_dimensions_and_values(monkeypatch):
    model, sdk = adapter(monkeypatch)
    vector = [2.0] + [0.0] * 767
    sdk.embeddings.create.return_value = SimpleNamespace(data=[SimpleNamespace(index=1, embedding=vector), SimpleNamespace(index=0, embedding=vector)])
    assert model.embed(["a", "b"], "RETRIEVAL_DOCUMENT") == [[1.0] + [0.0] * 767] * 2
    for data in ([SimpleNamespace(index=0, embedding=[1.0])], [SimpleNamespace(index=0, embedding=[float("nan")] * 768)], []):
        sdk.embeddings.create.return_value = SimpleNamespace(data=data)
        with pytest.raises(ProviderError):
            model.embed(["a"], "RETRIEVAL_QUERY")


def test_provider_errors_do_not_leak_secrets(monkeypatch):
    model, sdk = adapter(monkeypatch)
    sdk.responses.create.side_effect = RuntimeError("raw response with fake-openai and credentials")
    with pytest.raises(ProviderError) as caught:
        model.generate("Hi", [], [])
    assert "fake-openai" not in str(caught.value)
    assert "raw response" not in str(caught.value)


def test_embedding_failure_retries_operation_with_one_consistent_provider(monkeypatch):
    from academic_advisor.agent import providers
    from academic_advisor.ui import app

    class State(dict):
        __getattr__ = dict.__getitem__
        __setattr__ = dict.__setitem__

    class Flaky(Probe):
        def embed(self, texts, task):
            if texts != ["Connection check"]:
                raise ProviderError("Embedding quota reached")
            return super().embed(texts, task)

    models = {"gemini": Flaky(), "openai": Probe()}
    state = State(active_provider="gemini", preferred_provider="gemini")
    monkeypatch.setattr(app.st, "session_state", state)
    monkeypatch.setattr(app, "create_client", lambda s, p: models[p])
    monkeypatch.setattr(app, "select_provider", lambda s, p, **kw: providers.select_provider(s, p, factory=lambda s, p: models[p], **kw))
    attempted = []

    def operation(service):
        attempted.append(service.store.signature)
        service.embedder.embed(["Document content"], "RETRIEVAL_DOCUMENT")
        return "Indexed"

    assert app._run_document_action(settings(), SimpleNamespace(database=object()), operation) == "Indexed"
    assert state.active_provider == "openai"
    assert attempted == [settings().signature("gemini"), settings().signature("openai")]
    assert app._client(settings()) is models["openai"]
    assert models["openai"].calls[:3] == ["chat", "RETRIEVAL_DOCUMENT", "RETRIEVAL_QUERY"]
