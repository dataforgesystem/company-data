"""Tests for the vendor-agnostic LLM provider wrapper.

Providers disagree on response shape and on how prompt text may be
interpreted, so these pin both down.
"""

from langchain_core.language_models.fake_chat_models import (
    FakeListChatModel,
    FakeMessagesListChatModel,
)
from langchain_core.messages import AIMessage

from company_data.llm.llm_client import LLMProvider, extract_message_text


def test_text_is_extracted_from_block_content():
    """Gemini-style block content must not leak as a stringified list."""
    model = FakeMessagesListChatModel(
        responses=[
            AIMessage(
                content=[
                    {"type": "text", "text": "Based on the profile, "},
                    {"type": "text", "text": "Stripe raised Series I."},
                ]
            )
        ]
    )

    answer = LLMProvider(model).generate_text("question")

    assert answer == "Based on the profile, Stripe raised Series I."


def test_plain_string_content_is_returned_unchanged():
    model = FakeListChatModel(responses=["just text"])

    assert LLMProvider(model).generate_text("question") == "just text"


def test_extract_handles_missing_attributes():
    assert extract_message_text("raw string") == "raw string"


def test_prompt_braces_are_not_treated_as_a_template():
    """JSON in a prompt must reach the model literally."""
    model = FakeListChatModel(responses=["ok"])

    answer = LLMProvider(model).generate_text('{"company_name": "Acme", "x": 1}')

    assert answer == "ok"