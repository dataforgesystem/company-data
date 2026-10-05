from company_data.config.llm_configs import Capabilities, LLMConfig, Prompts
from company_data.llm.base import ILLMProvider
from company_data.pipeline.interfaces.extractor import BaseExtractor, ExtractedData

# Shown in place of the history on a first turn, so the prompt never contains a
# dangling empty section the model has to interpret.
NO_CONTEXT = "(none - this is the first message)"


class LLMExtractor(BaseExtractor):
    """Extracts intent with one corrective retry, verified against the query.
    """

    def __init__(self, llm: ILLMProvider) -> None:
        self.llm_client = llm
        # Kept as the raw template: the capabilities are static (rendered per
        # call is harmless) but the conversation context changes every turn, so
        # the prompt is assembled per call.
        self.prompt_template: str = Prompts.QUERY_INTENT_EXTRACTION_PROMPT
        self.capabilities: str = Capabilities.render()
        self.max_attempts: int = max(1, LLMConfig.EXTRACTION_MAX_ATTEMPTS)

    @property
    def system_prompt(self) -> str:
        """The system prompt for a turn with no conversation context."""
        return self.system_prompt_for(None)

    def system_prompt_for(self, conversation_context: str | None) -> str:
        """The system prompt with this turn's conversation history filled in."""
        context = (conversation_context or "").strip()
        return self.prompt_template.format(
            capabilities=self.capabilities,
            conversation_context=context or NO_CONTEXT,
        )

    def extract_intent(
        self, text_query: str, conversation_context: str | None = None
    ) -> ExtractedData:
        response = self._call(text_query, conversation_context)
        for _ in range(1, self.max_attempts):
            if response.company_names:
                return response
            candidate = self._call(text_query, conversation_context, previous=response)
            if not candidate.company_names:
                response = candidate
            elif self._names_are_grounded(
                candidate.company_names, text_query, conversation_context
            ):
                return candidate
            # else: the retry invented a company named neither in the query nor
            # in the conversation; keep the honest first result instead.
        return response

    @staticmethod
    def _names_are_grounded(
        names: list[str], text_query: str, conversation_context: str | None = None
    ) -> bool:
        """Whether every recovered name occurs in the query or the history.

        Both sources count: a follow-up legitimately carries its companies in
        from the conversation, so a name found only there is still real, while a
        name found in neither was invented. Case- and whitespace-insensitive so
        model-normalized spellings (``"Eightfold AI"`` for ``"EightFold AI"``)
        still verify.
        """
        haystack = " ".join(f"{text_query}\n{conversation_context or ''}".split()).lower()
        return all(" ".join(name.split()).lower() in haystack for name in names)

    def _call(
        self,
        text_query: str,
        conversation_context: str | None = None,
        previous: ExtractedData | None = None,
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
            system_instructions=self.system_prompt_for(conversation_context),
        )
