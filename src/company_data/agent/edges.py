"""Routing and static edges for the company research graph."""

from company_data.agent.state import AgentState


def route_after_intent(state: AgentState) -> str:
    """Valid intents with at least one company go to retrieval.

    A structurally valid intent that names no company (e.g. an extraction
    miss like ``company_names=[]`` on "competitors of Google") would
    otherwise flow into retrieval with zero names and die later with the
    generic "could not find" message. Routing it to the refusal makes the
    failure explicit at the step that caused it.
    """
    extracted = state.get("extracted")
    if extracted is not None and extracted.is_valid:
        names = list(state.get("company_names") or [])
        if not names:
            names = list(extracted.company_names or [])
            if not names and (extracted.company_name or "").strip():
                names = [extracted.company_name.strip()]
        if names:
            return "retrieve_company"
    return "respond_invalid_intent"

