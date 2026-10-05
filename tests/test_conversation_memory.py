"""Tests for conversation memory and context-aware caching.

Pins the three behaviours that make follow-up questions work:

- ``ConversationMemory`` keeps a bounded history and derives the prompt text
  and the cache scope from it;
- the agent passes that context to the extractor and uses the derived scope for
  the answer cache, so a follow-up can never be answered from another
  company's conversation;
- a turn served from the cache still seeds the memory (with the company names
  the cached answer was about), so a follow-up after a cache hit resolves.

No LLM, database, or Qdrant is needed.
"""

from typing import Any

import pytest

from company_data.agent.conversation import ConversationMemory, ConversationTurn
from company_data.config.conversation_configs import ConversationConfig

pytestmark = pytest.mark.anyio


# --------------------------------------------------------------- memory unit


def turn(query: str, answer: str = "ans", **fields: Any) -> ConversationTurn:
    return ConversationTurn(query=query, answer=answer, **fields)


def test_record_keeps_only_the_configured_number_of_turns():
    memory = ConversationMemory(history_turns=2, enabled=True)
    for index in range(5):
        memory.record({"query": f"q{index}", "answer": "a"})

    assert [t.query for t in memory.turns] == ["q3", "q4"]


def test_record_drops_turns_without_an_answer():
    memory = ConversationMemory(history_turns=4, enabled=True)
    assert memory.record({"query": "refused", "answer": ""}) is None
    assert memory.record({"query": "", "answer": "orphan answer"}) is None
    assert len(memory) == 0


def test_disabled_memory_records_nothing_and_renders_nothing():
    memory = ConversationMemory(enabled=False)
    memory.record({"query": "q", "answer": "a"})

    assert len(memory) == 0
    assert memory.render_for_prompt() == ""
    assert memory.cache_scope() == ""
    assert not memory.active


def test_history_turns_zero_disables_the_history_but_keeps_the_wiring():
    memory = ConversationMemory(history_turns=0, enabled=True)
    memory.record({"query": "q", "answer": "a"})

    assert len(memory) == 0
    assert not memory.active


def test_render_for_prompt_lists_query_companies_and_excerpted_answers():
    memory = ConversationMemory(history_turns=4, answer_excerpt_chars=20, enabled=True)
    memory.record(
        {
            "query": "Tell me about Stripe's funding",
            "answer": "word " * 30,  # longer than the excerpt window
            "company_names": ["Stripe"],
            "company_domains": ["stripe.com"],
        }
    )
    memory.record(
        {
            "query": "and their employees?",
            "answer": "short answer",
            "company_names": ["Stripe"],
        }
    )

    rendered = memory.render_for_prompt()
    assert "1. User asked: Tell me about Stripe's funding" in rendered
    assert "2. User asked: and their employees?" in rendered
    assert "Companies: Stripe" in rendered
    # The long answer is excerpted, the short one is whole.
    assert "…" in rendered
    assert "short answer" in rendered


def test_cache_scope_uses_the_most_recent_turn_with_companies():
    memory = ConversationMemory(history_turns=4, enabled=True)
    # A refusal turn carries no companies; the scope must see past it.
    memory.record({"query": "tell me a joke", "answer": "I only do company data."})
    memory.record(
        {
            "query": "Stripe funding",
            "answer": "Series H.",
            "company_names": ["Stripe"],
        }
    )

    assert memory.cache_scope() == "stripe"
    assert memory.last_companies() == ("Stripe",)


def test_cache_scope_is_empty_without_context():
    memory = ConversationMemory(history_turns=4, enabled=True)
    memory.record({"query": "hello", "answer": "Ask me about a company."})

    assert memory.cache_scope() == ""


def test_cache_scope_is_order_and_case_insensitive():
    memory = ConversationMemory(history_turns=4, enabled=True)
    memory.record(
        {
            "query": "q",
            "answer": "a",
            "company_names": ["EightFold  AI", "Stripe"],
        }
    )

    assert memory.cache_scope() == "eightfold ai|stripe"


def test_record_prefers_extracted_names_when_state_has_none():
    """A cache-hit result carries no ``extracted``; the fallback must hold."""
    memory = ConversationMemory(history_turns=4, enabled=True)

    class StubExtracted:
        company_names = ["FromExtracted"]

    memory.record(
        {
            "query": "q",
            "answer": "a",
            "extracted": StubExtracted(),
            "company_domains": [],
            "company_domain": "fromextracted.com",
        }
    )

    assert memory.last_companies() == ("FromExtracted",)
    assert memory.last_domains() == ("fromextracted.com",)


def test_clear_forgets_everything():
    memory = ConversationMemory(history_turns=4, enabled=True)
    memory.record({"query": "q", "answer": "a", "company_names": ["Stripe"]})
    memory.clear()

    assert len(memory) == 0
    assert memory.cache_scope() == ""


def test_config_defaults_are_sane():
    assert ConversationConfig.HISTORY_TURNS >= 1
    assert ConversationConfig.ANSWER_EXCERPT_CHARS > 0
