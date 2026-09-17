from typing import Any, cast

from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.messages import HumanMessage, SystemMessage
from langchain_core.tools import BaseTool

from company_data.llm.base import ILLMProvider, T


def extract_message_text(message: object) -> str:
    """Flattens a model response into plain text.

    Providers disagree on the shape of ``content``: most return a string, while
    others (Gemini among them) return a list of typed blocks. ``BaseMessage.text``
    normalizes both, which keeps an answer from being handed back as a
    stringified Python list.
    """
    text = getattr(message, "text", None)
    if isinstance(text, str):
        return text
    content = getattr(message, "content", None)
    if isinstance(content, str):
        return content
    if content is None:
        return str(message)
    return str(content)


class LLMProvider(ILLMProvider):
    def __init__(self, chat_model: BaseChatModel):
        super().__init__(chat_model)

    def generate_text(self, prompt: str, system_instructions: str | None = None) -> str:
        messages = []
        if system_instructions:
            messages.append(SystemMessage(content=system_instructions))
        messages.append(HumanMessage(content=prompt))

        return extract_message_text(self.chat_model.invoke(messages))

    def generate_structured_output(
        self, prompt: str, response_schema: type[T], system_instructions: str
    ) -> T:
        # Literal messages, not ChatPromptTemplate: prompt text (e.g. JSON
        # records) must never be parsed as a template.
        model = self.chat_model.with_structured_output(response_schema)
        messages = [
            SystemMessage(content=system_instructions),
            HumanMessage(content=prompt),
        ]
        return cast(T, model.invoke(messages))

    def call_with_tools(
        self,
        prompt: str,
        tools: list[BaseTool],
        system_instruction: str,
    ) -> Any:
        model = self.chat_model.bind_tools(tools)
        messages = []
        if system_instruction:
            messages.append(SystemMessage(content=system_instruction))
        messages.append(HumanMessage(content=prompt))
        return model.invoke(messages)
