# Chainlit chat UI

A thin chat adapter over the company research pipeline. The pipeline itself
lives in `src/company_data/` and knows nothing about Chainlit — this folder is
the only place a UI framework appears, and `tests/test_decoupling.py` fails if
that ever changes. Removing the UI is always safe.

## Install (optional dependency)

The core package never requires Chainlit; the UI is an optional extra:

```bash
pip install -e ".[ui]"
```

Or just `pip install chainlit` into the existing virtualenv.

## Run

PostgreSQL + Qdrant must be up (`docker compose up -d`). From the repository
root:

```bash
./ui/run.sh                     # opens http://localhost:8000
./ui/run.sh -w                  # auto-reload while editing the UI
./ui/run.sh --port 8123         # any `chainlit run` flag passes through
```

`ui/run.sh` only sets `CHAINLIT_APP_ROOT` to this folder and calls Chainlit.
Chainlit defaults its *app root* (where it looks for `chainlit.md`,
`.chainlit/`, `.files/`) to the **current working directory**, so without that
variable it would drop UI artifacts into the repository root. The equivalent
manual command is:

```bash
CHAINLIT_APP_ROOT=ui chainlit run ui/app.py -w
```

- Each chat session boots one `CompanyResearchAgent` (`agent.setup()` ensures
  the Qdrant collections exist) and releases its clients on chat end.
- Pipeline progress is streamed as collapsible Chainlit steps. Chainlit keeps
  every step it receives as a `Used <step>` header in the conversation, so the
  adapter **deletes them as soon as the run finishes** — otherwise they pile up
  under the answer. Set `UI_KEEP_PROGRESS_TRACE=1` to keep the raw trace when
  debugging the pipeline.
- The data provenance (source + domain per company) is appended to the answer
  message rather than sent as its own step, so it never leaves a header behind.
- Model calls follow the project config: intent extraction from
  `LLM_INTENT_MODEL`, answer synthesis from `LLM_ANSWER_MODEL`. The exact
  LLM response cache and (optional) semantic answer cache apply here too.

## Configure

All knobs are environment variables — see `.env.example`:

- `LLM_INTENT_MODEL` / `LLM_ANSWER_MODEL` / `LLM_EMBEDDING_MODEL`
- `MERGE_STRATEGY` (`off` | `preferred` | `union` | `llm`) and `MERGE_PREFERRED_SOURCE`
  — scraping follows the strategy: single-source strategies scrape the
  preferred source only
- `QUERY_CACHE_ENABLED` / `QUERY_CACHE_THRESHOLD` / `QUERY_CACHE_TTL_SECONDS`
- `UI_KEEP_PROGRESS_TRACE` (UI only; default `0`) — keep the per-step
  `Used <step>` headers in the conversation instead of deleting them once the
  answer lands. Useful for debugging the pipeline, noisy otherwise.

## Remove the UI

Every UI artifact — `app.py`, `chainlit.md`, `.chainlit/`, `.files/` — lives in
this folder, and nothing in the core imports Chainlit, so removal is two steps:

```bash
rm -rf ui/                      # delete the adapter and all its artifacts
pip uninstall chainlit          # drop the dependency
# remove the [project.optional-dependencies].ui entry from pyproject.toml
```

`tests/test_decoupling.py` exists to prove the core stays clean; it can be
deleted together with the UI if you also want to drop the guard.
