from company_data.config.llm_configs import Capabilities, LLMConfig, Prompts
from company_data.llm.base import ILLMProvider
from company_data.pipeline.interfaces.extractor import BaseExtractor, ExtractedData


class LLMExtractor(BaseExtractor):
    """Extracts intent with one corrective retry, verified against the query.

    Small local models (llama3.2 in particular) reliably drop the company on
    heading-style queries such as ``All Key Executives of Google`` while
    solving rephrased ones, and a larger model solves both. When a pass
    returns no company names, the same query is re-asked with the failed
    output shown back for correction.

    A retry's names are accepted only when they appear in the query text:
    the corrective prompt reliably recovers dropped names, but it can also
    make a small model *invent* one for a query that names no company at all
    (observed live: ``Hello there`` -> ``["Google"]``). Unverifiable retries
    are discarded and the honest first result is returned, which the graph
    then refuses with an actionable message.
    """

    def __init__(self, llm: ILLMProvider) -> None:
        self.llm_client = llm
        self.system_prompt: str = Prompts.QUERY_INTENT_EXTRACTION_PROMPT.format(
            capabilities=Capabilities.render()
        )
        self.max_attempts: int = max(1, LLMConfig.EXTRACTION_MAX_ATTEMPTS)

    def extract_intent(self, text_query: str) -> ExtractedData:
        response = self._call(text_query)
        for _ in range(1, self.max_attempts):
            if response.company_names:
                return response
            candidate = self._call(text_query, previous=response)
            if not candidate.company_names:
                response = candidate
            elif self._names_in_query(candidate.company_names, text_query):
                return candidate
            # else: the retry invented a company the query does not mention;
            # keep the honest first result instead.
        return response

    @staticmethod
    def _names_in_query(names: list[str], text_query: str) -> bool:
        """Whether every recovered name occurs in the query text.

        Case- and whitespace-insensitive so model-normalized spellings
        (``"Eightfold AI"`` for ``"EightFold AI"``) still verify.
        """
        normalized_query = " ".join(text_query.split()).lower()
        return all(
            " ".join(name.split()).lower() in normalized_query for name in names
        )

    def _call(
        self, text_query: str, previous: ExtractedData | None = None
    ) -> ExtractedData:
        prompt = text_query
        if previous is not None:
            prompt = (
                f"{text_query}\n\n"
                + Prompts.QUERY_INTENT_RETRY_PROMPT.format(
                    previous_output=previous.model_dump_json()
                )
            )
        return self.llm_client.generate_structured_output(
            prompt=prompt,
            response_schema=ExtractedData,
            system_instructions=self.system_prompt,
        )
