"""Regression tests for the extractor's corrective retry.

Small local intent models (llama3.2) reliably drop the company on
heading-style queries such as ``All Key Executives of Google`` while solving
rephrased ones; a larger model solves both. ``LLMExtractor`` re-asks with the
failed output shown back for correction instead of letting the miss flow into
the graph. These tests pin the retry contract. No LLM or database is needed.
"""

from company_data.config.llm_configs import LLMConfig, Prompts
from company_data.pipeline.interfaces.extractor import ExtractedData
from company_data.pipeline.llm_extractor import LLMExtractor


class ScriptedLLM:
    """Returns queued outputs in order, recording every prompt it is given."""

    def __init__(self, *outputs: ExtractedData) -> None:
        self.outputs = list(outputs)
        self.prompts: list[str] = []

    def generate_structured_output(
        self, prompt: str, response_schema, system_instructions
    ) -> ExtractedData:
        self.prompts.append(prompt)
        assert response_schema is ExtractedData
        return self.outputs.pop(0)


def _extraction(
    *names: str, valid: bool = True, intent: str = "get key executives"
) -> ExtractedData:
    return ExtractedData(
        company_names=list(names), intent=intent, is_valid=valid
    )


def test_retry_recovers_when_first_pass_drops_the_company():
    llm = ScriptedLLM(
        _extraction(valid=False, intent="Get all key executives of a specific company"),
        _extraction("Google"),
    )
    out = LLMExtractor(llm).extract_intent("All Key Executives of Google")

    assert out.company_names == ["Google"]
    assert out.is_valid
    assert len(llm.prompts) == 2
    # The retry re-asks the same query and shows the failed output back...
    assert "All Key Executives of Google" in llm.prompts[1]
    assert "previous extraction" in llm.prompts[1]
    # ...including the previous result as JSON (pydantic emits it compactly).
    assert '"company_names":[]' in llm.prompts[1]
    # The first pass must carry the plain query, not retry scaffolding.
    assert llm.prompts[0] == "All Key Executives of Google"


def test_no_retry_when_first_pass_names_a_company():
    llm = ScriptedLLM(_extraction("Stripe", "Adyen"))
    out = LLMExtractor(llm).extract_intent("Compare Stripe and Adyen")

    assert out.company_names == ["Stripe", "Adyen"]
    assert llm.prompts == ["Compare Stripe and Adyen"]


def test_genuinely_companyless_query_stays_empty_after_retry():
    llm = ScriptedLLM(
        _extraction(valid=False, intent="casual greeting"),
        _extraction(valid=False, intent="casual greeting"),
    )
    out = LLMExtractor(llm).extract_intent("Hello there")

    assert out.company_names == []
    assert not out.is_valid
    assert len(llm.prompts) == 2


def test_attempts_knob_can_disable_the_retry(monkeypatch):
    monkeypatch.setattr(LLMConfig, "EXTRACTION_MAX_ATTEMPTS", 1)
    llm = ScriptedLLM(_extraction(valid=False, intent="Get all key executives"))

    out = LLMExtractor(llm).extract_intent("All Key Executives of Google")

    assert out.company_names == []
    assert len(llm.prompts) == 1


def test_more_attempts_allow_more_retries(monkeypatch):
    monkeypatch.setattr(LLMConfig, "EXTRACTION_MAX_ATTEMPTS", 3)
    llm = ScriptedLLM(
        _extraction(valid=False), _extraction(valid=False), _extraction("Google")
    )

    out = LLMExtractor(llm).extract_intent("All Key Executives of Google")

    assert out.company_names == ["Google"]
    assert len(llm.prompts) == 3


def test_retry_may_not_invent_companies_absent_from_the_query():
    """The corrective prompt can make a small model hallucinate a company
    (observed live: ``Hello there`` -> ``[\"Google\"]``). An unverifiable
    retry must be discarded in favour of the honest first result."""
    llm = ScriptedLLM(
        _extraction(valid=False, intent="casual greeting"),
        _extraction("Google"),  # hallucinated on the retry pass
    )
    out = LLMExtractor(llm).extract_intent("Hello there")

    assert out.company_names == []
    assert not out.is_valid
    assert len(llm.prompts) == 2


def test_retry_verifies_names_case_and_whitespace_insensitively():
    llm = ScriptedLLM(
        _extraction(valid=False, intent="get funding of the company"),
        _extraction("Eightfold  AI"),  # model-normalized spelling of the query's name
    )
    out = LLMExtractor(llm).extract_intent("Funding of EightFold AI")

    assert out.company_names == ["Eightfold  AI"]
    assert out.is_valid


# ------------------------------------------------------- conversation context


def test_first_turn_prompt_states_there_is_no_history():
    llm = ScriptedLLM(_extraction("Google"))
    extractor = LLMExtractor(llm)

    extractor.extract_intent("All Key Executives of Google")

    system_prompt = extractor.system_prompt_for(None)
    assert "(none - this is the first message)" in system_prompt
    # The history section must never be left dangling/empty.
    assert "Earlier turns of this conversation" in system_prompt


def test_followup_prompt_carries_the_rendered_history():
    history = "1. User asked: Tell me about Stripe\n   Companies: Stripe"
    llm = ScriptedLLM(_extraction("Stripe"))
    extractor = LLMExtractor(llm)

    extractor.extract_intent("and their employees?", conversation_context=history)

    system_prompt = extractor.system_prompt_for(history)
    assert history in system_prompt
    assert "(none - this is the first message)" not in system_prompt
    # The retry prompt must also look at the conversation, not just the query.
    assert "earlier turns" in Prompts.QUERY_INTENT_RETRY_PROMPT


def test_retry_may_carry_a_company_in_from_the_conversation():
    """A follow-up retry recovers the company from the history, not hallucinated.

    The query itself names no company, so the query-only guard would have
    rejected the recovered name; the history is a legitimate source.
    """
    llm = ScriptedLLM(
        _extraction(valid=False, intent="employees of the company"),
        _extraction("Stripe", intent="employees of the company"),
    )
    history = "1. User asked: Tell me about Stripe\n   Companies: Stripe"
    out = LLMExtractor(llm).extract_intent(
        "and their employees?", conversation_context=history
    )

    assert out.company_names == ["Stripe"]
    assert out.is_valid


def test_retry_still_rejects_names_absent_from_both_query_and_history():
    llm = ScriptedLLM(
        _extraction(valid=False, intent="employees of the company"),
        _extraction("Google"),  # invented: not in the query nor the history
    )
    history = "1. User asked: Tell me about Stripe\n   Companies: Stripe"
    out = LLMExtractor(llm).extract_intent(
        "and their employees?", conversation_context=history
    )

    assert out.company_names == []
    assert not out.is_valid
