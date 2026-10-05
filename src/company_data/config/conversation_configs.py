import os


def _flag(name: str, default: bool) -> bool:
    """Reads a boolean environment flag ("1"/"true"/"yes"/"on")."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


class ConversationConfig:
    """Conversation-memory settings, overridable via environment variables.

    The graph answers one question at a time, so on its own it cannot resolve a
    follow-up: "and their employees?" names no company and would be refused as
    out of scope. Conversation memory keeps the earlier turns so the extractor
    can carry the companies over.

    ``HISTORY_TURNS`` is deliberately small. The history is part of *every*
    extraction prompt, and small local models degrade as the prompt grows —
    four turns is enough for pronouns like "them"/"the second one" while
    keeping the prompt roughly constant in size across a long chat.
    """

    CONVERSATION_ENABLED = _flag("CONVERSATION_ENABLED", True)
    # Turns kept and shown to the model. 0 disables the history while leaving
    # the feature wired (useful to reproduce pre-memory behaviour).
    HISTORY_TURNS = int(os.getenv("CONVERSATION_HISTORY_TURNS", "4"))
    # Answers are replayed into the prompt for continuity only, so long ones
    # are excerpted rather than carried whole (profiles can be a few KB).
    ANSWER_EXCERPT_CHARS = int(os.getenv("CONVERSATION_ANSWER_EXCERPT_CHARS", "500"))
