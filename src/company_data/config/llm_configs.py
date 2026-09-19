import os
from collections.abc import Callable

from company_data_crawler.models.company_data import CompanyData
from langchain_core.embeddings import Embeddings
from langchain_core.language_models.chat_models import BaseChatModel


class LLMConfig:
    """Model-agnostic LLM/embedding wiring.

    Models are chosen with provider-qualified specs of the form
    ``"<provider>:<model>"``::

        LLMConfig.chat_model("gemini:gemini-2.5-flash")
        LLMConfig.chat_model("ollama:llama3.2")

    A bare model name is accepted as well and its provider is inferred: names
    starting with ``gemini`` go to Gemini (``GEMINI_API_KEY`` /
    ``GOOGLE_API_KEY``), anything else to :attr:`DEFAULT_PROVIDER`. That keeps
    values such as ``"llama3.1:8b"`` working, where the colon is part of the
    Ollama tag rather than a provider prefix.

    Every default below is overridable through environment variables, so
    switching a single model - or an entire vendor - needs no code change. A
    new vendor only needs an adapter registered via :meth:`register_provider`.

    Note on the Gemini default: ``gemini-2.5-flash`` is no longer served to new
    API keys (the API answers ``404 NOT_FOUND`` and points at the current
    generation), so the merge model is pinned to ``gemini-3.6-flash``. Set
    ``LLM_MERGE_MODEL`` to pin any other model, or use the auto-updating alias
    ``gemini:gemini-flash-latest`` to track the newest Flash release.
    """

    # ------------------------------------------------------------- selection
    QUERY_INTENT_EXTRACTION_MODEL = os.getenv(
        "LLM_INTENT_MODEL", "ollama:llama3.2"
    )
    # Small local intent models drop the company on heading-style queries
    # ("All Key Executives of Google" - the craft.co page-title format) while
    # solving rephrased ones. The extractor re-asks with a corrective prompt
    # when a pass returns no company names; 2 = one retry.
    EXTRACTION_MAX_ATTEMPTS = int(os.getenv("LLM_EXTRACTION_ATTEMPTS", "2"))
    PROFILE_MERGE_MODEL = os.getenv("LLM_MERGE_MODEL", "gemini:gemini-3.6-flash")
    ANSWER_MODEL = os.getenv("LLM_ANSWER_MODEL", PROFILE_MERGE_MODEL)
    EMBEDDING_MODEL = os.getenv("LLM_EMBEDDING_MODEL", "ollama:nomic-embed-text")

    DEFAULT_PROVIDER = os.getenv("LLM_DEFAULT_PROVIDER", "ollama")

    # Providers we can name in an error message, even before an adapter is
    # registered for them.
    KNOWN_PROVIDERS: tuple[str, ...] = (
        "ollama",
        "gemini",
        "google",
        "openai",
        "anthropic",
        "azure",
        "bedrock",
    )

    # ---------------------------------------------------- provider settings
    OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://127.0.0.1:11434")
    # Ollama defaults to num_ctx=2048, which silently truncates large prompts
    # (e.g. multi-source merge payloads). Raise it so full records fit.
    CONTEXT_WINDOW = int(os.getenv("LLM_CONTEXT_WINDOW", "8192"))
    MAX_OUTPUT_TOKENS = int(os.getenv("LLM_MAX_OUTPUT_TOKENS", "4096"))

    # ----------------------------------------------------------- resolution
    _CHAT_ADAPTERS: dict[str, Callable[[str], "BaseChatModel"]] = {}
    _EMBEDDING_ADAPTERS: dict[str, Callable[[str], "Embeddings"]] = {}

    @classmethod
    def register_provider(
        cls,
        name: str,
        *,
        chat: Callable[[str], "BaseChatModel"] | None = None,
        embeddings: Callable[[str], "Embeddings"] | None = None,
    ) -> None:
        """Registers adapters for a provider, extending this config externally.

        Example - wiring OpenAI without editing this module::

            LLMConfig.register_provider("openai", chat=ChatOpenAI)
        """
        key = (name or "").strip().lower()
        if not key:
            raise ValueError("Provider name must not be empty.")
        if chat is not None:
            cls._CHAT_ADAPTERS[key] = chat
        if embeddings is not None:
            cls._EMBEDDING_ADAPTERS[key] = embeddings

    @classmethod
    def chat_model(cls, spec: str | None = None) -> "BaseChatModel":
        """Builds the LangChain chat model for a provider-qualified spec."""
        provider, model = cls._resolve(
            spec or cls.QUERY_INTENT_EXTRACTION_MODEL, cls._CHAT_ADAPTERS
        )
        return cls._CHAT_ADAPTERS[provider](model)

    @classmethod
    def embedding_model(cls, spec: str | None = None) -> "Embeddings":
        """Builds the LangChain ``Embeddings`` for a provider-qualified spec."""
        provider, model = cls._resolve(
            spec or cls.EMBEDDING_MODEL, cls._EMBEDDING_ADAPTERS
        )
        return cls._EMBEDDING_ADAPTERS[provider](model)

    @classmethod
    def _resolve(cls, spec: str, adapters: dict) -> tuple[str, str]:
        """Splits a model spec into ``(provider, model)``.

        An explicit ``<provider>:<model>`` prefix wins; otherwise the whole
        spec is treated as a model name with an inferred provider, because
        Ollama tags legitimately contain colons (``llama3.1:8b``).
        """
        spec = (spec or "").strip()
        if not spec:
            raise ValueError("Model spec must not be empty.")

        provider, separator, model = spec.partition(":")
        if separator and model:
            key = provider.strip().lower()
            if key in adapters:
                return key, model.strip()
            if key in cls.KNOWN_PROVIDERS:
                raise ValueError(
                    f"No adapter registered for provider {key!r}. "
                    f"Register one with LLMConfig.register_provider("
                    f"{key!r}, chat=...)."
                )

        inferred = cls._infer_provider(spec)
        if inferred not in adapters:
            raise ValueError(
                f"No adapter registered for provider {inferred!r} that "
                f"resolves spec {spec!r}. Registered providers: "
                f"{', '.join(sorted(adapters)) or 'none'}."
            )
        return inferred, spec

    @classmethod
    def _infer_provider(cls, model: str) -> str:
        """Provider implied by a bare model name."""
        if model.lower().startswith("gemini"):
            return "gemini"
        return cls.DEFAULT_PROVIDER

    # ------------------------------------------------------------- adapters
    @classmethod
    def _ollama_chat(cls, model: str) -> "BaseChatModel":
        from langchain_ollama import ChatOllama

        return ChatOllama(
            model=model,
            base_url=cls.OLLAMA_HOST,
            temperature=0.0,
            num_ctx=cls.CONTEXT_WINDOW,
            num_predict=cls.MAX_OUTPUT_TOKENS,
        )

    @classmethod
    def _ollama_embeddings(cls, model: str) -> "Embeddings":
        from langchain_ollama import OllamaEmbeddings

        return OllamaEmbeddings(model=model, base_url=cls.OLLAMA_HOST)

    @classmethod
    def _gemini_chat(cls, model: str) -> "BaseChatModel":
        """Gemini chat model; the API key comes from ``GEMINI_API_KEY``."""
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            model=model,
            temperature=0.0,
            max_output_tokens=cls.MAX_OUTPUT_TOKENS,
        )

    @classmethod
    def _gemini_embeddings(cls, model: str) -> "Embeddings":
        """Gemini embeddings, pinned to the vector store's dimension.

        Gemini models default to a higher dimensionality than the collection,
        so the output is forced to ``DBConfig.VECTOR_SIZE``.
        """
        from langchain_google_genai import GoogleGenerativeAIEmbeddings

        from company_data.config.db_configs import DBConfig

        return GoogleGenerativeAIEmbeddings(
            model=model, output_dimensionality=DBConfig.VECTOR_SIZE
        )


LLMConfig.register_provider(
    "ollama", chat=LLMConfig._ollama_chat, embeddings=LLMConfig._ollama_embeddings
)
LLMConfig.register_provider(
    "gemini", chat=LLMConfig._gemini_chat, embeddings=LLMConfig._gemini_embeddings
)
LLMConfig.register_provider(
    "google", chat=LLMConfig._gemini_chat, embeddings=LLMConfig._gemini_embeddings
)


class Capabilities:
    """Current capabilities of the ``company_data_crawler`` package.

    Search capabilities are curated explicitly, while the data
    capabilities are derived from the ``CompanyData`` model of the
    installed ``company-data-crawler`` package, so the prompt always
    stays in sync with the crawler version in use.
    """

    SEARCH_CAPABILITIES: tuple[str, ...] = (
        "Search for a company by its name",
        "Search for a company by its stock symbol/ticker",
    )

    EXCLUDED_FIELDS: frozenset[str] = frozenset({"last_scraped_at"})

    @classmethod
    def data_capabilities(cls) -> list[str]:
        """Retrievable data points, taken from the ``CompanyData`` model descriptions."""
        return [
            field.description or name.replace("_", " ").capitalize()
            for name, field in CompanyData.model_fields.items()
            if name not in cls.EXCLUDED_FIELDS and field.description
        ]

    @classmethod
    def render(cls) -> str:
        """Render all capabilities as a bullet list for injection into prompts."""
        lines = [f"- {capability}" for capability in cls.SEARCH_CAPABILITIES]
        lines += [f"- {capability}" for capability in cls.data_capabilities()]
        return "\n".join(lines)


class Prompts:
    QUERY_INTENT_EXTRACTION_PROMPT = """Extract the intent from the user query, and match it with the company_data_crawler capabilities listed below.

The crawler can currently do the following:
{capabilities}

Rules:
- Extract EVERY company EXPLICITLY NAMED in the query text into "company_names"
  (in the order mentioned). Extract names even when the question is about
  related companies: "Who are the competitors of Google?" mentions Google,
  so it yields ["Google"]; "Compare Stripe and Adyen" yields ["Stripe", "Adyen"];
  a single-company query yields one entry.
- Do NOT leave "company_names" empty when the query names a company. Only
  leave it empty when the query truly names no company at all.
- "company_name" must equal the first entry of "company_names".
- If the query mentions no company, leave both empty and set is_valid to False.
- If the query does not match any of the capabilities above, return is_valid as False. If the intent is not valid, return is_valid as False.

Return the output in JSON format with keys: company_names, company_name, intent, is_valid."""

    QUERY_INTENT_RETRY_PROMPT = """Your previous extraction of this same query returned:
{previous_output}

Check the query text again: if it explicitly names any company, copy that name EXACTLY as written into "company_names" and set "company_name" to that same first entry, keeping intent and is_valid consistent. Only leave "company_names" empty when the query truly names no company at all. Return the JSON with the same keys."""

    PROFILE_MERGE_SYSTEM_PROMPT = """You are a data-reconciliation assistant for company profiles collected by the company_data_crawler from multiple sources (e.g. craft, owler).

You receive one JSON record per source for the same company and must reconcile them into a single profile:
- Resolve conflicting scalar values (company name, description, URLs, founded year, type, symbol) by preferring the most recently scraped record; use source reliability only to break exact ties (craft is primary, owler secondary).
- For collection fields (funding info, key executives, employee counts, locations, income statements, similar companies, operating metrics, industries), keep the union across all sources and drop exact duplicates.
- Never invent values that no source provides; leave unknown fields empty or null.

Return the single reconciled profile as JSON that matches the provided response schema."""

    PROFILE_MERGE_USER_PROMPT = """Reconcile the per-source records for company domain "{company_domain}" into a single profile.

Examine EVERY field of EVERY record below before answering:
- Collection fields (company_funding_info, key_executives, company_employee_counts, company_locations, company_income_statements, similar_companies, company_operating_metrics, company_industries): include the UNION of entries from ALL records; drop only exact duplicates.
- Scalar fields (company_name, description, URLs, company_founded_year, company_type, company_symbol): take the value from the newest record; if it is missing there, fall back to an older record that has it.
- Never drop data that any source provides. Never invent data that no source provides.

Records (newest first, one JSON object per source):
{records_json}

The consumer needs this unified profile for: {focus_query}"""

    PROFILE_ANSWER_SYSTEM_PROMPT = """You are a company research assistant. Answer the user's question using ONLY the company profile JSON provided below. If the profile does not contain the information needed, say so explicitly instead of guessing. Be concise and factual."""

    PROFILE_ANSWER_USER_PROMPT = """Company profile (JSON):
{profile_json}

User question: {query}"""

    PROFILE_MULTI_ANSWER_USER_PROMPT = """Company profiles (one JSON block per company, labelled):
{profiles_json}

User question: {query}

Answer the question using ONLY the profiles above, addressing each company
it mentions. If a profile lacks the needed information, say so for that
company instead of guessing. Be concise and factual."""
