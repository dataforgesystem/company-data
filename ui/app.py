"""Chainlit chat UI for the company research pipeline.

Thin presentation adapter over :class:`company_data.agent.graph.CompanyResearchAgent`:
the pipeline in ``src/company_data`` knows nothing about Chainlit, so this
folder can be deleted at any time without touching the core (guarded by
``tests/test_decoupling.py``).

Run from the repository root::

    ./ui/run.sh -w

``run.sh`` pins Chainlit's app root to this folder (via ``CHAINLIT_APP_ROOT``)
so ``chainlit.md``, ``.chainlit/`` and ``.files/`` never appear in the
repository root. The equivalent manual command is::

    CHAINLIT_APP_ROOT=ui chainlit run ui/app.py -w
"""

import logging
import os
from typing import Any

import chainlit as cl

from company_data.agent.graph import CompanyResearchAgent
from company_data.config.cache_configs import CacheConfig
from company_data.config.crawler_configs import MergeConfig
from company_data.config.llm_configs import LLMConfig
from company_data.pipeline.ingestion import IngestionPipeline


def _flag(name: str, default: bool) -> bool:
    """Reads a boolean environment flag ("1"/"true"/"yes"/"on")."""
    raw = os.getenv(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


ASSISTANT_NAME = "Company Research"
PROGRESS_STEPS_KEY = "progress_steps"

# Chainlit renders every step it has ever received as a permanent "Used
# <step>" header in the conversation (``chat.messages.status.used``), and the
# pipeline emits one step per graph node. Left alone those headers pile up
# underneath the answer, so by default the adapter deletes the progress steps
# as soon as the answer is delivered. Set ``UI_KEEP_PROGRESS_TRACE=1`` to keep
# them for debugging.
KEEP_PROGRESS_TRACE = _flag("UI_KEEP_PROGRESS_TRACE", False)

logger = logging.getLogger(__name__)

NODE_LABELS = {
    "extract_intent": "🧠 Understanding your request",
    "retrieve_company": "🔎 Looking up known companies",
    "ensure_profiles": "🌐 Fetching company data (may scrape the web)",
    "merge_profile": "🧩 Reconciling company records",
    "synthesize_answer": "✍️ Writing the answer",
    "respond_invalid_intent": "🚫 Preparing an out-of-scope reply",
}


def describe_data_sources() -> str:
    """Human summary of the scrape scope implied by the merge strategy."""
    scope = MergeConfig.scrape_sources()
    if scope is None:
        known = ", ".join(IngestionPipeline.KNOWN_SOURCES)
        return (
            f"merging **on** (`{MergeConfig.validated_strategy()}`) — "
            f"scraping {known}"
        )
    return (
        f"merging **off** — answering from {', '.join(scope)} only "
        f"(set `MERGE_STRATEGY=union|llm` to merge sources)"
    )


def describe_models() -> str:
    return (
        f"intent `{LLMConfig.QUERY_INTENT_EXTRACTION_MODEL}` · "
        f"answer `{LLMConfig.ANSWER_MODEL}` · "
        f"embeddings `{LLMConfig.EMBEDDING_MODEL}`"
    )


def describe_cache() -> str:
    enabled = CacheConfig.QUERY_CACHE_ENABLED
    ttl_minutes = CacheConfig.QUERY_CACHE_TTL_SECONDS // 60
    state = f"on (TTL {ttl_minutes} min)" if enabled else "off"
    return f"answer cache {state}"


def render_provenance(source_profiles: list[Any] | None) -> str:
    """Renders the per-source records an answer was built from.

    Appended to the answer message instead of being sent as its own step: a
    step would leave a permanent "Used 🗂️ Data provenance" header behind, and
    provenance belongs with the answer it justifies.
    """
    lines: list[str] = []
    seen: set[tuple[str, str | None]] = set()
    for sourced in source_profiles or []:
        key = (sourced.source_name, sourced.profile.company_domain)
        if key in seen:
            continue
        seen.add(key)
        lines.append(
            f"- **{sourced.profile.company_name}** — `{sourced.source_name}` "
            f"({sourced.profile.company_domain})"
        )
    if not lines:
        return ""
    return "\n\n---\n**🗂️ Data provenance**\n" + "\n".join(lines)


def _progress_steps() -> list[Any]:
    return cl.user_session.get(PROGRESS_STEPS_KEY) or []


async def clear_progress_steps() -> None:
    """Deletes this run's progress steps so their headers do not linger."""
    if KEEP_PROGRESS_TRACE:
        cl.user_session.set(PROGRESS_STEPS_KEY, [])
        return

    steps = _progress_steps()
    cl.user_session.set(PROGRESS_STEPS_KEY, [])
    for step in steps:
        try:
            await step.remove()
        except Exception as failure:  # pragma: no cover - best-effort cleanup
            logger.debug("Could not remove progress step %r: %r", step.name, failure)


@cl.on_chat_start
async def start_chat() -> None:
    """Boots one research agent per chat session."""
    try:
        agent = CompanyResearchAgent()
        await agent.setup()
    except Exception as failure:
        await cl.Message(
            content=(
                f"⚠️ Could not start the research service: {failure!r}\n\n"
                "Check that PostgreSQL and Qdrant are running "
                "(`docker compose up -d`) and try again."
            ),
            author=ASSISTANT_NAME,
        ).send()
        cl.user_session.set(PROGRESS_STEPS_KEY, [])
        return

    cl.user_session.set("agent", agent)
    cl.user_session.set(PROGRESS_STEPS_KEY, [])
    await cl.Message(
        content=(
            "👋 Ask me about any company — funding, key executives, "
            "employees, locations, similar companies.\n\n"
            f"**Data sources:** {describe_data_sources()}\n"
            f"**Models:** {describe_models()}\n"
            f"**{describe_cache()}**\n\n"
            "Try: *Tell me about the funding history of Stripe.*"
        ),
        author=ASSISTANT_NAME,
    ).send()


async def on_node_progress(node_name: str, node_update: dict[str, Any]) -> None:
    """Reports one finished pipeline step as a collapsed Chainlit step.

    The step is tracked in the session so :func:`clear_progress_steps` can
    delete it once the answer lands — Chainlit renders every step it receives
    as a permanent ``Used <step>`` header.
    """
    step = cl.Step(name=NODE_LABELS.get(node_name, node_name), type="run")
    step.output = "✓"
    await step.send()
    cl.user_session.set(PROGRESS_STEPS_KEY, [*_progress_steps(), step])


@cl.on_message
async def handle_message(message: cl.Message) -> None:
    agent: CompanyResearchAgent | None = cl.user_session.get("agent")
    if agent is None:
        await cl.Message(
            content="⚠️ The research service is not started yet.", author=ASSISTANT_NAME
        ).send()
        return

    query = (message.content or "").strip()
    if not query:
        return

    cl.user_session.set(PROGRESS_STEPS_KEY, [])
    state: dict[str, Any] = {}
    failure: Exception | None = None
    try:
        state = await agent.run(query, on_node=on_node_progress)
    except Exception as error:  # reported below, after the trace is cleaned up
        failure = error
    finally:
        await clear_progress_steps()

    if failure is not None:
        await cl.Message(
            content=f"⚠️ The research run failed: {failure!r}", author=ASSISTANT_NAME
        ).send()
        return

    answer = state.get("answer") or "I could not produce an answer for that."
    if state.get("cache_hit"):
        answer = "⚡ *served from the answer cache*\n\n" + answer
    answer += render_provenance(state.get("source_profiles"))
    await cl.Message(content=answer, author=ASSISTANT_NAME).send()


@cl.on_chat_end
async def end_chat() -> None:
    """Releases the per-session agent's database clients."""
    agent: CompanyResearchAgent | None = cl.user_session.get("agent")
    if agent is not None:
        await agent.close()
    cl.user_session.set("agent", None)