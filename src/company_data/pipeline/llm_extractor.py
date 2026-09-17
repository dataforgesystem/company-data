from company_data.config.llm_configs import Capabilities, Prompts
from company_data.llm.base import ILLMProvider
from company_data.pipeline.interfaces.extractor import BaseExtractor, ExtractedData


class LLMExtractor(BaseExtractor):
    def __init__(self, llm: ILLMProvider) -> None:
        self.llm_client = llm
        self.system_prompt: str = Prompts.QUERY_INTENT_EXTRACTION_PROMPT.format(
            capabilities=Capabilities.render()
        )

    def extract_intent(self, text_query: str) -> ExtractedData:
        response = self.llm_client.generate_structured_output(
            prompt=text_query,
            response_schema=ExtractedData,
            system_instructions=self.system_prompt,
        )
        return response
