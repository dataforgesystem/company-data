"""Regression tests for provider-agnostic model resolution.

``LLMConfig`` turns a provider-qualified spec (``"gemini:gemini-2.5-flash"``,
``"ollama:llama3.2"``) into a LangChain adapter, and still accepts bare model
names - including Ollama tags that contain colons. No network or API key is
needed: the resolution logic is exercised with stub adapters.
"""

import pytest
from langchain_core.language_models.fake_chat_models import FakeListChatModel

from company_data.config.llm_configs import LLMConfig

STUB_PROVIDER = "testvendor"


@pytest.fixture
def stub_adapters(monkeypatch):
    """Registers a stub provider without touching the real registry."""
    chat_calls: list[str] = []
    embedding_calls: list[str] = []

    monkeypatch.setitem(
        LLMConfig._CHAT_ADAPTERS,
        STUB_PROVIDER,
        lambda model: chat_calls.append(model) or FakeListChatModel(responses=["{}"]),
    )
    monkeypatch.setitem(
        LLMConfig._EMBEDDING_ADAPTERS, STUB_PROVIDER, embedding_calls.append
    )
    return chat_calls, embedding_calls


def test_explicit_provider_prefix_selects_that_adapter(stub_adapters):
    chat_calls, _ = stub_adapters

    LLMConfig.chat_model(f"{STUB_PROVIDER}:some-model")

    assert chat_calls == ["some-model"]


def test_bare_model_name_falls_back_to_the_default_provider():
    provider, model = LLMConfig._resolve("nomic-embed-text", LLMConfig._EMBEDDING_ADAPTERS)

    assert (provider, model) == (LLMConfig.DEFAULT_PROVIDER, "nomic-embed-text")


def test_ollama_tag_with_colon_is_not_read_as_a_provider():
    """``llama3.1:8b`` is a model tag, not the provider ``llama3.1``."""
    provider, model = LLMConfig._resolve("llama3.1:8b", LLMConfig._CHAT_ADAPTERS)

    assert (provider, model) == ("ollama", "llama3.1:8b")


def test_gemini_names_route_to_gemini_without_a_prefix():
    provider, model = LLMConfig._resolve("gemini-2.5-flash", LLMConfig._CHAT_ADAPTERS)

    assert (provider, model) == ("gemini", "gemini-2.5-flash")


def test_google_prefix_is_an_alias_for_gemini():
    provider, model = LLMConfig._resolve("google:gemini-2.5-pro", LLMConfig._CHAT_ADAPTERS)

    assert (provider, model) == ("google", "gemini-2.5-pro")


def test_known_provider_without_adapter_explains_how_to_register():
    """A vendor we know of but have not wired must fail loudly, not silently."""
    with pytest.raises(ValueError, match="register_provider"):
        LLMConfig.chat_model("openai:gpt-4o")


def test_empty_spec_is_rejected():
    with pytest.raises(ValueError, match="must not be empty"):
        LLMConfig.chat_model("   ")


def test_merge_model_defaults_to_gemini_flash(monkeypatch):
    """The shipped config must actually route merging to a Gemini Flash model."""
    seen: list[str] = []
    monkeypatch.setitem(LLMConfig._CHAT_ADAPTERS, "gemini", seen.append)

    LLMConfig.chat_model(LLMConfig.PROFILE_MERGE_MODEL)

    assert seen and seen[0].startswith("gemini-"), seen


def test_embedding_model_stays_on_the_vector_store_dimension():
    assert LLMConfig.EMBEDDING_MODEL == "ollama:nomic-embed-text"