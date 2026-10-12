# Company Research

An AI research agent that answers natural-language questions about companies —
funding, executives, employee counts, locations, similar companies and more —
from **real crawled data**, not model memory.

Ask it things like *"What is the funding history of Stripe?"* or
*"Compare the key executives of Findem and EightFold AI."* and it extracts the
intent, retrieves the right company records, and synthesizes a grounded answer
it can point back to (per source, with provenance).

![Architecture](architecture.png)

## Highlights

- **Multi-source, provenance-preserving storage** — craft and owler records are
  stored *separately* (one row per source per company in Postgres, one point
  per source in Qdrant). Nothing is silently conflated; you always know which
  source an answer came from.
- **Merging is optional and on demand** — answer from a single preferred source
  by default, switch to an algorithmic union or an LLM reconciliation with one
  environment variable. Scraping follows the strategy: single-source
  configurations scrape only the preferred source.
- **Multi-company queries** — *"Compare Stripe and Adyen"* resolves both
  companies and answers against both profiles in one turn.
- **Conversation memory** — follow-ups work: ask about a company, then say
  *"and their employees?"* The agent carries the companies over from the
  previous turn and rewrites the question into a standalone one.
- **Two cache layers** — an exact-match cache of LLM responses (identical
  prompt ⇒ no API call) and a semantic cache of whole answers (repeat
  questions skip crawling, merging and synthesis entirely), scoped per
  conversation so one company's answer is never served for another.
- **Model-agnostic** — every model is selected by a `provider:model` spec
  through LangChain: local Ollama for cheap steps, Gemini for heavier ones, or
  any vendor you register.
- **Optional chat UI** — a Chainlit interface that lives entirely in `ui/`,
  with zero UI imports in the core, so it can be deleted without touching the
  pipeline.

## How it works

Each question runs through a LangGraph pipeline:

```
question
   │
   ▼
extract_intent ──► intent + companies + resolved_query        (LLM, small model)
   │                 │  conversation history rides along so
   │                 │  "and their employees?" still names a company
   ▼
retrieve_company ──► semantic vector search in Qdrant         (local embeddings)
   │
   ▼
ensure_profiles ──► read the per-source rows; crawl and store only on a miss
   │                (scope follows MERGE_STRATEGY)
   ▼
merge_profile ────► resolve the requested view: preferred record as-is,
   │                deterministic union, or LLM reconciliation (opt-in)
   ▼
synthesize_answer ─► grounded answer from the profile JSON      (LLM)
   │
   ▼
answer + data provenance   (cached, scoped to the conversation)
```

Invalid or out-of-scope requests stop at the first step with an explicit
refusal instead of reaching the stores.

## Quickstart

### Prerequisites

- Python **3.12+**
- **Docker** (PostgreSQL + Qdrant)
- An LLM: **[Ollama](https://ollama.com)** locally and/or a **Gemini API key**

### 1. Install

```bash
git clone https://github.com/dataforgesystem/company-data.git
cd company-data
python -m venv .venv && source .venv/bin/activate
pip install -e .            # core pipeline
pip install -e ".[ui]"      # optional: + Chainlit chat UI
```

### 2. Configure

```bash
cp .env.example .env
```

Set at minimum:

```bash
GEMINI_API_KEY=your-key          # if using Gemini models
PG_CONNECTION_STRING=postgresql://postgres:test123@localhost:5432/company_data
```

`.env` is loaded automatically for every entry point (CLI, scripts, tests).
`.env.example` documents every knob.

### 3. Start the services

```bash
docker compose up -d            # PostgreSQL (:5432) + Qdrant (:6333)
```

With Ollama, pull the default models:

```bash
ollama pull llama3.2            # intent extraction
ollama pull nomic-embed-text    # embeddings (768-dim)
```

### 4. Run it

**Chat UI:**

```bash
./ui/run.sh                     # http://localhost:8000
```

**One-shot from Python:**

```python
import asyncio
from company_data.agent.graph import CompanyResearchAgent

async def main():
    agent = CompanyResearchAgent()
    await agent.setup()                     # ensures the Qdrant collection
    try:
        state = await agent.run("What is the funding history of Stripe?")
        print(state["answer"])
        for record in state["source_profiles"]:     # provenance per source
            print(record.source_name, record.profile.company_domain)
    finally:
        await agent.close()

asyncio.run(main())
```

**Multi-turn (conversation memory):**

```python
agent = CompanyResearchAgent()
await agent.setup()
await agent.run("Tell me about the funding history of Stripe")
state = await agent.run("and their employees?")     # inherits "Stripe"
print(state["company_names"])                       # ['Stripe']
```

> The agent instance *is* a conversation: successive `run()` calls share
> memory. Chat UIs pass one `ConversationMemory` per chat session instead.

**Smoke scripts** (from the repo root, with `.venv` active):

| Script | Purpose |
|---|---|
| `scripts/ingest_smoke.py --company stripe` | Applies the schema, creates the collection, ingests a company, shows what landed per source |
| `scripts/agent_smoke.py --query "…"` | Full live pipeline: intent → retrieval → ingestion → answer |
| `scripts/offline_agent_check.py` | 7 routes through the real graph with fakes — no LLM, no database |
| `scripts/merge_diagnostic.py` | Inspects the LLM merge path in isolation |


## Configuration

All configuration is environment variables (copy `.env.example` to `.env`).
Real environment variables always win over `.env` entries.

### Models

Every model is a `<provider>:<model>` spec. A bare name is accepted too and
the provider is inferred (names starting with `gemini` → Gemini, anything else
→ `LLM_DEFAULT_PROVIDER`), so values like `llama3.1:8b` keep working.

| Variable | Default | Used for |
|---|---|---|
| `LLM_INTENT_MODEL` | `ollama:llama3.2` | Intent extraction (cheap, local) |
| `LLM_EXTRACTION_ATTEMPTS` | `2` | Extraction passes; `2` = one corrective retry when a small model drops the company |
| `LLM_MERGE_MODEL` | `gemini:gemini-3.5-flash` | LLM merge strategy (`MERGE_STRATEGY=llm`) |
| `LLM_ANSWER_MODEL` | = `LLM_MERGE_MODEL` | Answer synthesis |
| `LLM_EMBEDDING_MODEL` | `ollama:nomic-embed-text` | 768-dim vectors (must match `VECTOR_SIZE`) |
| `GEMINI_API_KEY` | – | Gemini auth (or `GOOGLE_API_KEY`) |
| `OLLAMA_HOST` | `http://127.0.0.1:11434` | Ollama endpoint |
| `LLM_CONTEXT_WINDOW` / `LLM_MAX_OUTPUT_TOKENS` | `8192` / `4096` | Ollama generation limits |

Adding a vendor is one line:

```python
from company_data.config.llm_configs import LLMConfig
LLMConfig.register_provider("openai", chat=ChatOpenAI)
```

> `gemini-2.5-flash` is no longer served to new API keys (the API answers
> `404 NOT_FOUND`); the default is pinned to a current generation. Set
> `LLM_MERGE_MODEL` to any model your key can reach.

### Storage

| Variable | Default | Used for |
|---|---|---|
| `PG_CONNECTION_STRING` | `postgresql://postgres:test123@localhost:5432/company_data` | Per-source company profiles (system of record) |
| `QDRANT_URL` | `http://localhost:6333` | Semantic company index + answer cache |
| `QDRANT_COLLECTION` | `companies` | One point per `(domain, source)` |
| `VECTOR_SIZE` | `768` | Must match the embedding model |

The schema lives in `src/company_data/database/schema.sql`;
`scripts/ingest_smoke.py` applies it automatically on first run.

### Merging & scraping

Stores always keep **one record per source**. Merging is an on-demand
resolution step, controlled by `MERGE_STRATEGY`:

| Strategy | What answers the query | LLM call | Scrapes |
|---|---|---|---|
| `off` | Preferred source's record only | never | preferred source only |
| `preferred` *(default)* | Preferred source when present, else a deterministic union fallback | never | preferred source only |
| `union` | Algorithmic union across sources (newest non-empty scalar wins) | never | every source |
| `llm` | LLM reconciliation with collection completion | **opt-in** | every source |

```bash
MERGE_STRATEGY=preferred            # off | preferred | union | llm
MERGE_PREFERRED_SOURCE=craft        # code default: craft
```

`MERGE_ENABLED=false` is a legacy kill-switch forcing `off`.


### Caching

| Variable | Default | Used for |
|---|---|---|
| `LLM_CACHE_ENABLED` | `true` | Exact-match cache of LLM responses, keyed by full prompt + model config (`LLM_CACHE_DIR`, 7-day expiry) |
| `QUERY_CACHE_ENABLED` | `true` | Semantic cache of whole answers — a hit skips the entire graph |
| `QUERY_CACHE_THRESHOLD` | `0.97` | Cosine similarity required; deliberately conservative, because a false hit returns a wrong answer with no way to notice |
| `QUERY_CACHE_TTL_SECONDS` | `86400` | Cached answers expire after 24 h |

Answer-cache entries are additionally **scoped to the companies under
discussion**: *"and their employees?"* is identical text in a Stripe
conversation and an Adyen one, so the scope filter (an exact match applied in
Qdrant alongside the vector search) guarantees they can never collide.
One-shot callers use an empty scope, exactly as before.

### Conversation memory

| Variable | Default | Used for |
|---|---|---|
| `CONVERSATION_ENABLED` | `true` | Follow-up resolution via earlier turns |
| `CONVERSATION_HISTORY_TURNS` | `4` | Turns kept and shown to the model (they are part of every extraction prompt — keep it small for small models) |
| `CONVERSATION_ANSWER_EXCERPT_CHARS` | `500` | History answers are excerpted, not replayed whole |

### Chat UI

| Variable | Default | Used for |
|---|---|---|
| `UI_KEEP_PROGRESS_TRACE` | `0` | Keep the per-step `Used …` headers instead of deleting them after each answer |

## Chat UI

```bash
./ui/run.sh                    # http://localhost:8000
./ui/run.sh -w                 # auto-reload while editing ui/
```

- Per-chat conversation memory with a `/clear` command (`/reset`, `/new` too).
- Live progress: every pipeline node renders as a collapsible step, deleted
  when the answer lands.
- Data provenance under each answer: company → source → domain.
- Cache hits are flagged (⚡).

The UI is a **pure adapter** — it imports the core, never the reverse
(`tests/test_decoupling.py` enforces this). To remove it:

```bash

## Testing

```bash
pytest tests/ -q                     # 105 tests, no LLM or database required
python scripts/offline_agent_check.py  # 7 routes through the real graph with fakes
```

The suites cover extraction retry and grounding (the 3B model dropping
heading-style queries), optional merging and read scoping, conversation memory
and cache scoping, lossless merge completion, the LLM client and response
cache, provider-agnostic model resolution, the progress hook, and the Chainlit
adapter (skipped when `chainlit` isn't installed).

For live verification against real services, `scripts/agent_smoke.py` and
`scripts/ingest_smoke.py` exercise the pipeline end to end.

## Project layout

```
src/company_data/
├── agent/              LangGraph pipeline: state, nodes, routing, graph and
│                       ConversationMemory (the runnable CompanyResearchAgent)
├── cache/              Semantic answer cache contract + implementation
├── config/             env-driven config: models, DB, merge, cache, conversation
├── database/           Postgres profiles · Qdrant index · answer-cache store
│   ├── relational/     per-source rows (schema.sql)
│   └── vector/         per-source points + query cache
├── llm/                vendor-agnostic ILLMProvider/IEmbedder + LangChain impl,
│                       exact-match response cache
├── pipeline/           ingestion, intent extractor, mergers (deterministic + LLM)
│   └── interfaces/     contracts (Extractor, Merger, Scraper)
├── tools/              LangChain tool wrappers around the crawler
└── utils/              logger

ui/                     optional Chainlit chat adapter (removable)
scripts/                smoke tests + offline route checks
tests/                  pytest suites (hermetic: fakes, no services)
```

## Troubleshooting

| Symptom | Fix |
|---|---|
| *"Could not start the research service"* / connection errors | `docker compose up -d` |
| Extraction returns no companies | Heading-style queries trip small models; the extractor retries once. Raise `LLM_EXTRACTION_ATTEMPTS` or use a larger `LLM_INTENT_MODEL` |
| Answer looks stale after config changes | Run once with `QUERY_CACHE_ENABLED=false`; entries are scoped and expire after `QUERY_CACHE_TTL_SECONDS` |
| Embedding errors / dimension mismatch | `VECTOR_SIZE` must match `LLM_EMBEDDING_MODEL` |
| Gemini `404 NOT_FOUND: no longer available` | The pinned model isn't served to your key — set `LLM_MERGE_MODEL` to one it supports (e.g. `gemini:gemini-flash-latest`) |
| Follow-ups refuse with *"could not tell which company"* | Ensure `CONVERSATION_ENABLED=true`; name the company explicitly on the first question |

> `setup.md` describes an older multi-member Poetry workspace layout and does
> not apply to the current single-package structure (`pip install -e .`).

## Authors

[Sajid Shaikh](mailto:shaikhsajid11112000@gmail.com) ·
[Shiva Silmawala](mailto:shivasilmawala841@gmail.com)

rm -rf ui/ && pip uninstall chainlit     # then drop the [ui] extra from pyproject.toml
```

`ui/run.sh` sets `CHAINLIT_APP_ROOT` so Chainlit's artifacts (`chainlit.md`,
`.chainlit/`, `.files/`) stay inside `ui/` and the repo root stays clean.

