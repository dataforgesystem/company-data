from company_data_crawler.models.company_data import CompanyData


class LLMConfig:
    QUERY_INTENT_EXTRACTION_MODEL = "llama3.2"
    PROFILE_MERGE_MODEL = "llama3.2"
    EMBEDDING_MODEL = "nomic-embed-text"
    OLLAMA_HOST = "http://127.0.0.1:11434"

    @classmethod
    def environment_config(
        cls, model_name: str, host: str | None = None
    ) -> "ILLMEnvironmentConfig":
        """Build the provider-agnostic config object the LLM providers take."""
        from company_data.llm.base import ILLMEnvironmentConfig

        return ILLMEnvironmentConfig(
            API_KEY=None, model_name=model_name, host=host or cls.OLLAMA_HOST
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

If the query does not match any of the capabilities above, return is_valid as False. If the intent is not valid, return is_valid as False.

Return the output in JSON format with keys: company_name, intent, is_valid."""

    PROFILE_MERGE_SYSTEM_PROMPT = """You are a data-reconciliation assistant for company profiles collected by the company_data_crawler from multiple sources (e.g. craft, owler).

You receive one JSON record per source for the same company and must reconcile them into a single profile:
- Resolve conflicting scalar values (company name, description, URLs, founded year, type, symbol) by preferring the most recently scraped record; use source reliability only to break exact ties (craft is primary, owler secondary).
- For collection fields (funding info, key executives, employee counts, locations, income statements, similar companies, operating metrics, industries), keep the union across all sources and drop exact duplicates.
- Never invent values that no source provides; leave unknown fields empty or null.
- Take company_status from the record with the newest last_updated.

Return the single reconciled profile as JSON that matches the CompanyData schema."""

    PROFILE_MERGE_USER_PROMPT = """Reconcile the per-source records for company domain "{company_domain}" into a single profile.

Examine EVERY field of EVERY record below before answering:
- Collection fields (company_funding_info, key_executives, company_employee_counts, company_locations, company_income_statements, similar_companies, company_operating_metrics, company_industries): include the UNION of entries from ALL records; drop only exact duplicates.
- Scalar fields (company_name, description, URLs, company_founded_year, company_type, company_symbol): take the value from the newest record; if it is missing there, fall back to an older record that has it.
- Never drop data that any source provides. Never invent data that no source provides.

Records (newest first, one JSON object per source):
{records_json}

The consumer needs this unified profile for: {focus_query}"""
