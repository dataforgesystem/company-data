"""Conversation memory for the research agent.

The graph is stateless: it answers one question from the query alone. A chat is
a sequence of questions, though, and the later ones often only make sense
against the earlier ones — "Tell me about Stripe's funding" followed by "and
their employees?". This module holds the bounded history that makes such
follow-ups resolvable.

It is pure bookkeeping: no model calls, no I/O, nothing UI-specific, so any
caller (CLI, tests, a chat UI) can own one. Two derived values are what the
graph consumes:

``render_for_prompt``
    The history as prompt text, so the intent extractor can carry a company
    over from an earlier turn instead of reporting that no company was named.

``cache_scope``
    A digest of the companies a follow-up could refer to. The answer cache is
    keyed on question text, and "and their employees?" is the *same text* in a
    conversation about Stripe and one about Adyen while expecting different
    answers, so cached entries are only valid inside their company scope.
"""

from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from company_data.config.conversation_configs import ConversationConfig


@dataclass(frozen=True)
class ConversationTurn:
    """One completed question/answer exchange, after resolution."""

    query: str
    answer: str
    company_names: tuple[str, ...] = ()
    company_domains: tuple[str, ...] = ()
    intent: str = ""
    cache_hit: bool = False


class ConversationMemory:
    """Bounded short-term memory of a single conversation.

    ``record`` is fed the state a run returns, so the memory reflects what was
    actually resolved (including turns served from the answer cache, which is
    what keeps a follow-up working after a cache hit).
    """

    def __init__(
        self,
        history_turns: int | None = None,
        answer_excerpt_chars: int | None = None,
        enabled: bool | None = None,
    ) -> None:
        self.enabled = (
            ConversationConfig.CONVERSATION_ENABLED if enabled is None else enabled
        )
        configured = (
            ConversationConfig.HISTORY_TURNS if history_turns is None else history_turns
        )
        self.history_turns = max(0, configured)
        self.answer_excerpt_chars = (
            ConversationConfig.ANSWER_EXCERPT_CHARS
            if answer_excerpt_chars is None
            else max(0, answer_excerpt_chars)
        )
        self._turns: list[ConversationTurn] = []

    @property
    def turns(self) -> tuple[ConversationTurn, ...]:
        """The retained turns, oldest first."""
        return tuple(self._turns)

    def __len__(self) -> int:
        return len(self._turns)

    @property
    def active(self) -> bool:
        """Whether this memory will keep and report anything."""
        return self.enabled and self.history_turns > 0

    def record(self, state: Mapping[str, Any]) -> ConversationTurn | None:
        """Stores one finished run, or returns ``None`` if there is nothing to store.

        A run with no answer (or no query) carries no context forward, so it is
        dropped rather than recorded as an empty turn.
        """
        if not self.active:
            return None

        query = str(state.get("query") or "").strip()
        answer = str(state.get("answer") or "").strip()
        if not query or not answer:
            return None

        extracted = state.get("extracted")
        names = state.get("company_names") or []
        if not names and extracted is not None:
            names = getattr(extracted, "company_names", None) or []
        domains = state.get("company_domains") or []
        if not domains:
            # A cache hit only carries the first company's domain.
            single = state.get("company_domain")
            domains = [single] if single else []

        turn = ConversationTurn(
            query=query,
            answer=answer,
            company_names=tuple(
                name.strip() for name in names if str(name or "").strip()
            ),
            company_domains=tuple(
                domain for domain in domains if str(domain or "").strip()
            ),
            intent=str(getattr(extracted, "intent", "") or ""),
            cache_hit=bool(state.get("cache_hit")),
        )
        self._turns.append(turn)
        del self._turns[: -self.history_turns]
        return turn

    def last_companies(self) -> tuple[str, ...]:
        """Companies a follow-up could most plausibly refer to.

        Scans back for the most recent turn that named companies: a follow-up
        can directly follow a refusal or a cached answer, and the company that
        was under discussion then is still the one being discussed.
        """
        if not self.active:
            return ()
        for turn in reversed(self._turns):
            if turn.company_names:
                return turn.company_names
        return ()

    def last_domains(self) -> tuple[str, ...]:
        """Domains of the most recent turn that resolved any."""
        if not self.active:
            return ()
        for turn in reversed(self._turns):
            if turn.company_domains:
                return turn.company_domains
        return ()

    def cache_scope(self) -> str:
        """Digest of the companies a follow-up could refer to.

        Empty means "no context", which is every first turn — so a one-shot
        caller (a script, the CLI) keeps exactly the caching behaviour it had
        before conversation memory existed.
        """
        names = self.last_companies()
        if not names:
            return ""
        return "|".join(" ".join(name.split()).casefold() for name in names)

    def render_for_prompt(self) -> str:
        """The recent history as prompt text; ``""`` when there is none."""
        if not self.active or not self._turns:
            return ""
        lines: list[str] = []
        for index, turn in enumerate(self._turns, start=1):
            lines.append(f"{index}. User asked: {turn.query}")
            if turn.company_names:
                lines.append(f"   Companies: {', '.join(turn.company_names)}")
            lines.append(f"   Answer: {self._excerpt(turn.answer)}")
        return "\n".join(lines)

    def clear(self) -> None:
        """Forgets every turn (a fresh chat, or an explicit reset)."""
        self._turns.clear()

    def _excerpt(self, answer: str) -> str:
        if self.answer_excerpt_chars <= 0:
            return "(omitted)"
        collapsed = " ".join(answer.split())
        if len(collapsed) <= self.answer_excerpt_chars:
            return collapsed
        return collapsed[: self.answer_excerpt_chars].rstrip() + "…"
