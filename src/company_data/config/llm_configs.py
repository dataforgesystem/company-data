from company_data_crawler.models.company_data import CompanyData


class LLMConfig:
    QUERY_INTENT_EXTRACTION_MODEL = "llama3.2"
    OLLAMA_HOST = "http://127.0.0.1:11434"


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
