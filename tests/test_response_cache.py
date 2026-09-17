"""Tests for the exact-match LLM response cache.

The important guarantee is that a repeated model call is served from disk
without touching the provider, and that a hit can never come from a different
prompt or a differently configured model.
"""

import time
from typing import ClassVar

import pytest
from langchain_core.globals import get_llm_cache, set_llm_cache
from langchain_core.language_models.fake_chat_models import FakeListChatModel
from langchain_core.messages import AIMessage
from langchain_core.outputs import ChatGeneration

from company_data.llm.response_cache import DiscoResponseCache, configure_llm_cache


class CountingChatModel(FakeListChatModel):
    """Fake chat model that records how often it actually runs."""

    calls: ClassVar[int] = 0

    def _generate(self, messages, stop=None, run_manager=None, **kwargs):
        type(self).calls += 1
        return super()._generate(
            messages, stop=stop, run_manager=run_manager, **kwargs
        )


@pytest.fixture
def cache(tmp_path):
    """A cache instance isolated to a temporary directory."""
    return DiscoResponseCache(str(tmp_path), expiry_seconds=60)


def generations(text: str) -> list[ChatGeneration]:
    return [ChatGeneration(message=AIMessage(content=text))]


def test_stores_and_returns_chat_generations(cache):
    cache.update("prompt", "llm-config", generations("answer"))

    hit = cache.lookup("prompt", "llm-config")

    assert hit is not None
    assert hit[0].message.content == "answer"


def test_unknown_prompt_is_a_miss(cache):
    assert cache.lookup("never-seen", "llm-config") is None


def test_a_different_model_configuration_is_a_miss(cache):
    """The same prompt against a different model must not reuse a response."""
    cache.update("prompt", "gemini:gemini-3.6-flash", generations("answer"))

    assert cache.lookup("prompt", "ollama:llama3.2") is None


def test_entries_expire(tmp_path):
    """A response must not be served after its TTL has passed."""
    expiring = DiscoResponseCache(str(tmp_path), expiry_seconds=1)
    expiring.update("prompt", "llm-config", generations("answer"))

    time.sleep(1.2)

    assert expiring.lookup("prompt", "llm-config") is None


def test_clear_drops_everything(cache):
    cache.update("prompt", "llm-config", generations("answer"))

    cache.clear()

    assert cache.lookup("prompt", "llm-config") is None


def test_global_cache_prevents_a_second_model_call(tmp_path):
    """Registering the cache makes a repeated call free - the core guarantee."""
    configure_llm_cache(directory=str(tmp_path), expiry_seconds=60)
    try:
        CountingChatModel.calls = 0
        model = CountingChatModel(responses=["hello"])

        first = model.invoke("hi")
        second = model.invoke("hi")

        assert first.content == second.content == "hello"
        assert CountingChatModel.calls == 1, "second call should be served from cache"
    finally:
        set_llm_cache(None)


def test_disabled_cache_is_not_registered(tmp_path):
    configure_llm_cache(directory=str(tmp_path))
    try:
        set_llm_cache(None)

        assert configure_llm_cache(enabled=False, directory=str(tmp_path)) is None
        assert get_llm_cache() is None
    finally:
        set_llm_cache(None)


def test_enabled_cache_is_registered_globally(tmp_path):
    set_llm_cache(None)
    try:
        installed = configure_llm_cache(directory=str(tmp_path), expiry_seconds=60)

        assert isinstance(installed, DiscoResponseCache)
        assert get_llm_cache() is installed
    finally:
        set_llm_cache(None)