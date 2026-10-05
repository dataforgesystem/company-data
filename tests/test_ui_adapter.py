"""Behavioural tests for the optional Chainlit adapter (``ui/app.py``).

Chainlit is an optional extra (``pip install -e ".[ui]"``), so this module is
skipped when it is missing — the core suite must stay green with no UI
installed. When it *is* installed, the adapter's callbacks are driven through a
real Chainlit websocket session whose transport is an in-process recorder. That
pins the adapter's contract: it boots one research agent per chat, streams
pipeline progress, renders the answer plus data provenance, and releases the
agent on chat end.

The pipeline itself is faked here (``scripts/offline_agent_check.py`` exercises
the real graph). ``tests/test_decoupling.py`` guards that no UI import ever
reaches the core package.
"""

import os
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

# Chainlit creates <CHAINLIT_APP_ROOT>/.chainlit and .files as an import side
# effect; pointing it at a throwaway directory keeps the repository clean.
# `ui/run.sh` does the same thing for the real app.
os.environ["CHAINLIT_APP_ROOT"] = tempfile.mkdtemp(prefix="company-data-chainlit-")

pytest.importorskip("chainlit")

from chainlit.config import config as chainlit_config  # noqa: E402
from chainlit.context import init_ws_context  # noqa: E402
from chainlit.session import WebsocketSession  # noqa: E402
from company_data_crawler.models.company_data import CompanyData  # noqa: E402

from company_data.agent.conversation import ConversationMemory  # noqa: E402
from company_data.config.crawler_configs import MergeConfig  # noqa: E402
from company_data.database.base import SourcedProfile  # noqa: E402
from company_data.pipeline.ingestion import IngestionPipeline  # noqa: E402

pytestmark = pytest.mark.anyio

UI_DIR = Path(__file__).resolve().parents[1] / "ui"
if str(UI_DIR) not in sys.path:
    sys.path.insert(0, str(UI_DIR))

import app as ui_app  # noqa: E402  (imported once the UI dir is on the path)


class FakeAgent:
    """Stands in for ``CompanyResearchAgent`` inside the adapter."""

    fail_on_setup = False
    progress_nodes: tuple[str, ...] = ("extract_intent", "retrieve_company")

    def __init__(self) -> None:
        self.setup_calls = 0
        self.close_calls = 0
        self.queries: list[str] = []
        self.returned_state: dict[str, Any] = {
            "answer": "Stripe was founded in 2010.",
            "cache_hit": False,
            "source_profiles": [
                SourcedProfile(
                    source_name="craft",
                    profile=CompanyData(
                        company_name="Stripe", company_domain="stripe.com"
                    ),
                )
            ],
        }

    async def setup(self) -> None:
        self.setup_calls += 1
        if self.fail_on_setup:
            raise RuntimeError("qdrant unreachable")

    async def run(self, query: str, on_node=None, conversation=None):
        # `conversation` arrives from the adapter's per-session memory; the fake
        # records the context it received so tests can assert on it.
        self.conversations = getattr(self, "conversations", [])
        self.conversations.append(conversation)
        # The real agent records the finished turn into the memory it was
        # given; the fake mirrors that so memory-growth is testable here.
        if conversation is not None:
            conversation.record(
                {
                    "query": query,
                    "answer": str(self.returned_state.get("answer", "")),
                    "company_names": ["Stripe"],
                    "company_domain": "stripe.com",
                    "cache_hit": bool(self.returned_state.get("cache_hit")),
                }
            )
        self.queries.append(query)
        if on_node is not None:
            for node_name in self.progress_nodes:
                await on_node(node_name, {})
        return self.returned_state

    async def close(self) -> None:
        self.close_calls += 1


class UiHarness:
    """Records every event Chainlit would have pushed to the browser."""

    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def emit(self, event: str, data: Any = None) -> None:
        self.events.append((event, data))

    async def emit_call(self, *args, **kwargs):  # pragma: no cover - unused
        raise AssertionError("the UI never asks the client for input")

    @property
    def steps(self) -> list[dict[str, Any]]:
        """Collapsible steps: pipeline progress plus the provenance index."""
        return [
            data
            for event, data in self.events
            if event == "new_message"
            and isinstance(data, dict)
            and data.get("type") != "assistant_message"
        ]

    @property
    def messages(self) -> list[dict[str, Any]]:
        """Assistant messages (name=author, type=assistant_message)."""
        return [
            data
            for event, data in self.events
            if event == "new_message"
            and isinstance(data, dict)
            and data.get("type") == "assistant_message"
        ]

    def answers(self) -> str:
        return "\n".join(str(message.get("output", "")) for message in self.messages)

    def step_names(self) -> list[str]:
        return [str(step.get("name", "")) for step in self.steps]

    @property
    def deleted_steps(self) -> list[dict[str, Any]]:
        """Steps Chainlit was told to delete (``delete_message`` events)."""
        return [
            data
            for event, data in self.events
            if event == "delete_message" and isinstance(data, dict)
        ]

    @property
    def live_steps(self) -> list[dict[str, Any]]:
        """Steps still on screen: everything sent, minus everything deleted."""
        deleted = {str(step.get("id", "")) for step in self.deleted_steps}
        return [step for step in self.steps if str(step.get("id", "")) not in deleted]

    def live_step_names(self) -> list[str]:
        return [str(step.get("name", "")) for step in self.live_steps]

    def step_text(self) -> str:
        return "\n".join(
            f"{step.get('name', '')}\n{step.get('output', '')}" for step in self.steps
        )


async def boot_chat(monkeypatch, agent: FakeAgent) -> UiHarness:
    """Runs the adapter inside a real Chainlit session (must be awaited)."""
    harness = UiHarness()
    monkeypatch.setattr(ui_app, "CompanyResearchAgent", lambda: agent)
    # The adapter's step payloads only carry output when the chain of thought
    # is not hidden; pin the mode the assertions describe.
    monkeypatch.setattr(chainlit_config.ui, "cot", "full")

    session = WebsocketSession(
        id=f"session-{id(agent)}",
        socket_id=f"socket-{id(agent)}",
        emit=harness.emit,
        emit_call=harness.emit_call,
        user_env={},
        client_type="webapp",
        environ={"HTTP_ACCEPT_LANGUAGE": "en-US"},
    )
    init_ws_context(session)
    return harness


def message(text: str):
    """Minimal stand-in for ``cl.Message`` (only ``content`` is read)."""
    return type("Msg", (), {"content": text})()


async def test_chat_start_boots_one_agent_and_announces_the_configuration(
    monkeypatch,
):
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)

    await ui_app.start_chat()

    assert agent.setup_calls == 1
    greeting = harness.answers()
    assert "Data sources" in greeting
    assert "Models" in greeting
    assert ui_app.describe_cache() in greeting

    scope = MergeConfig.scrape_sources()
    if scope is None:
        assert "merging **on**" in greeting
    else:
        assert scope[0] in greeting


async def test_start_failure_tells_the_user_what_to_check(monkeypatch):
    agent = FakeAgent()
    agent.fail_on_setup = True
    harness = await boot_chat(monkeypatch, agent)

    await ui_app.start_chat()

    failure = harness.answers()
    assert "Could not start the research service" in failure
    assert "docker compose up -d" in failure

    # No agent was stored, so a query reports the service as unavailable
    # instead of raising.
    harness.events.clear()
    await ui_app.handle_message(message("hi"))
    assert "not started yet" in harness.answers()


async def test_message_streams_progress_answer_and_provenance(monkeypatch):
    agent = FakeAgent()
    agent.returned_state["source_profiles"] = [
        SourcedProfile(
            source_name="craft",
            profile=CompanyData(company_name="Stripe", company_domain="stripe.com"),
        ),
        SourcedProfile(
            source_name="owler",
            profile=CompanyData(
                company_name="Stripe, Inc.", company_domain="stripe.com"
            ),
        ),
        # Duplicate (same source + domain) must be collapsed in the UI.
        SourcedProfile(
            source_name="craft",
            profile=CompanyData(company_name="Stripe", company_domain="stripe.com"),
        ),
    ]
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message(" Tell me about Stripe "))

    assert agent.queries == ["Tell me about Stripe"]
    answer = harness.answers()
    assert "Stripe was founded in 2010." in answer

    # Progress streamed while the pipeline ran...
    assert harness.step_names() == [
        ui_app.NODE_LABELS["extract_intent"],
        ui_app.NODE_LABELS["retrieve_company"],
    ]
    # ...then disappeared before the answer landed. Chainlit renders every step
    # it has received as a permanent "Used <step>" header, so leaving them
    # behind is the reported bug.
    assert harness.live_step_names() == []
    assert len(harness.deleted_steps) == 2

    # Provenance rides along with the answer (deduplicated), not as a step.
    assert "**🗂️ Data provenance**" in answer
    assert "- **Stripe** — `craft` (stripe.com)" in answer
    assert "- **Stripe, Inc.** — `owler` (stripe.com)" in answer
    assert answer.count("`craft`") == 1


async def test_cached_answer_is_flagged(monkeypatch):
    agent = FakeAgent()
    agent.progress_nodes = ()  # a cache hit runs no pipeline nodes
    agent.returned_state = {
        "answer": "cached text",
        "cache_hit": True,
        "source_profiles": [],
    }
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message("Stripe?"))

    answer = harness.answers()
    assert "served from the answer cache" in answer
    assert "cached text" in answer
    # No records => no provenance block, and no progress to clean up.
    assert "Data provenance" not in answer
    assert harness.step_names() == []
    assert harness.deleted_steps == []


async def test_run_failure_is_reported_and_keeps_the_session_usable(monkeypatch):
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    async def explode(query, on_node=None):
        raise RuntimeError("crawler exploded")

    monkeypatch.setattr(agent, "run", explode)

    await ui_app.handle_message(message("Stripe?"))

    assert "The research run failed" in harness.answers()
    # A failed run must not tear down the session's agent.
    assert agent.close_calls == 0


async def test_blank_message_never_reaches_the_agent(monkeypatch):
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message("   "))

    assert agent.queries == []
    assert harness.events == []


async def test_chat_end_releases_the_agent(monkeypatch):
    agent = FakeAgent()
    await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()

    await ui_app.end_chat()

    assert agent.close_calls == 1


async def test_progress_headers_are_never_left_visible(monkeypatch):
    """Regression: no "Used <step>" header may outlive the answer.

    Every pipeline node emits a step, and Chainlit keeps every received step in
    the conversation as a ``Used <name>`` header. The adapter must delete them
    once the run finishes, on the success path and the failure path alike.
    """
    agent = FakeAgent()
    agent.progress_nodes = (
        "extract_intent",
        "retrieve_company",
        "ensure_profiles",
        "merge_profile",
        "synthesize_answer",
    )
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message("Stripe?"))

    assert len(harness.steps) == 5
    assert harness.live_step_names() == []
    assert {str(step["id"]) for step in harness.deleted_steps} == {
        str(step["id"]) for step in harness.steps
    }


async def test_progress_headers_are_removed_even_when_the_run_fails(monkeypatch):
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    async def explode(query, on_node=None, conversation=None):
        await on_node("extract_intent", {})
        raise RuntimeError("crawler exploded")

    monkeypatch.setattr(agent, "run", explode)

    await ui_app.handle_message(message("Stripe?"))

    assert "The research run failed" in harness.answers()
    assert harness.live_step_names() == []
    assert len(harness.deleted_steps) == 1


async def test_keep_progress_trace_flag_preserves_the_steps(monkeypatch):
    """``UI_KEEP_PROGRESS_TRACE=1`` opts into the raw trace for debugging."""
    monkeypatch.setattr(ui_app, "KEEP_PROGRESS_TRACE", True)
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message("Stripe?"))

    assert harness.live_step_names() == [
        ui_app.NODE_LABELS["extract_intent"],
        ui_app.NODE_LABELS["retrieve_company"],
    ]
    assert harness.deleted_steps == []


def test_scrape_scope_advertised_matches_the_pipeline_defaults():
    """What the UI advertises must match what the pipeline actually scrapes."""
    scope = MergeConfig.scrape_sources()
    if scope is None:
        # Merging on => every known source is scraped, not just the preferred.
        assert MergeConfig.PREFERRED_SOURCE in IngestionPipeline.KNOWN_SOURCES
        assert IngestionPipeline._default_sources() == IngestionPipeline.KNOWN_SOURCES
    else:
        assert list(scope) == [MergeConfig.PREFERRED_SOURCE]
        assert IngestionPipeline._default_sources() == (MergeConfig.PREFERRED_SOURCE,)


def test_adapter_is_the_module_under_ui():
    """Sanity check that this test really exercised ``ui/app.py``."""
    assert Path(ui_app.__file__).resolve().parent == UI_DIR.resolve()


# ------------------------------------------------------------ conversation


async def test_followups_share_one_conversation_memory(monkeypatch):
    """The adapter owns a per-session memory and passes it to every run."""
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    harness.events.clear()

    await ui_app.handle_message(message("Tell me about Stripe"))
    await ui_app.handle_message(message("and their employees?"))

    assert len(agent.conversations) == 2
    assert isinstance(agent.conversations[0], ConversationMemory)
    # The same memory object across turns is what makes follow-ups resolve.
    assert agent.conversations[0] is agent.conversations[1]
    # Both turns were recorded into the one shared memory.
    assert len(agent.conversations[1]) == 2


async def test_clear_command_resets_the_conversation(monkeypatch):
    agent = FakeAgent()
    harness = await boot_chat(monkeypatch, agent)
    await ui_app.start_chat()
    await ui_app.handle_message(message("Tell me about Stripe"))
    harness.events.clear()

    await ui_app.handle_message(message("/clear"))

    assert agent.queries == ["Tell me about Stripe"]  # /clear is not a query
    assert len(agent.conversations[0]) == 0
    assert "Conversation reset" in harness.answers()
