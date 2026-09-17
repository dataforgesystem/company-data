"""Routing and static edges for the company research graph."""

from company_data.agent.state import AgentState


def route_after_intent(state: AgentState) -> str:
    """Valid intents go to retrieval; invalid ones to the polite refusal."""
    extracted = state.get("extracted")
    if extracted is not None and extracted.is_valid:
        return "retrieve_company"
    return "respond_invalid_intent"

