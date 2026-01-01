from __future__ import annotations

from typing import List, Optional

from reference_agent.adapters.llm import LLMClient, LLMRequest
from reference_agent.models import Evidence


class AnswerComposer:
    def __init__(self, llm: Optional[LLMClient], model: Optional[str]) -> None:
        self._llm = llm
        self._model = model

    def compose_external(self, query: str, local_answer: str, external_answer: str, evidence: List[Evidence]) -> str:
        if not self._llm or not self._model:
            return self._fallback_compose(local_answer, external_answer)
        prompt = self._build_prompt(query, local_answer, external_answer, evidence)
        return self._llm.generate(self._model, LLMRequest(prompt, 0.2, 512)).strip() or self._fallback_compose(
            local_answer, external_answer
        )

    def compose_partial(self, query: str, answer: str, evidence: List[Evidence], template: str) -> str:
        if not self._llm or not self._model:
            return f"{template}\n\n{answer}"
        prompt = self._build_partial_prompt(query, answer, evidence, template)
        return self._llm.generate(self._model, LLMRequest(prompt, 0.2, 512)).strip() or f"{template}\n\n{answer}"

    def _fallback_compose(self, local_answer: str, external_answer: str) -> str:
        return (
            "Local evidence summary:\n"
            f"{local_answer}\n\n"
            "External evidence summary:\n"
            f"{external_answer}"
        )

    def _build_partial_prompt(self, query: str, answer: str, evidence: List[Evidence], template: str) -> str:
        citations = "\n".join(f"- {item.tool_id}: {item.locator.model_dump()}" for item in evidence)
        return (
            "Task:\n"
            "You are an answer generator within a RAG system that helps to compose an proper answer in response to "
            f"the question or instruction \"{query}\" from the user. Produce helpful, accurate, and "
            "well-structured answers based on retrieved context.\n\n"
            "<INFORMATION>\n"
            "Retrieved data (partial)\n"
            f"{answer}\n\n"
            "Evidence locators\n"
            f"{citations}\n"
            "<INFORMATION>\n\n"
            "The retrieval is incomplete. Use the following partial-response notice and then answer using the "
            "retrieved data. Keep the notice concise and do not repeat the question.\n\n"
            f"Partial notice: {template}\n\n"
            "Note:\n"
            "1. Use markdown to format the answer. Use markdown to highlight keywords instead of using double quotes.\n"
            "2. Don't repeat the question in the answer. Skip the main title of the article. Start straight with the "
            "introduction.\n"
            "3. When using tables, use markdown table syntax.\n"
            "4. When using charts, create a code block and output a chart using this format: \"chartType: Title of "
            "the chart\".\n"
            "5. Do not include any explaination or other texts except the code block.\n"
            "6. If the retrieved data is missing or not enough to answer the question, simply explain to the user you "
            "did not find the data, do not reveal the details of the failed attempts.\n"
            "7. You can also ask questions to the user to clarify the question the user asked.\n"
            "8. Answer in the language of the question. If not sure about the language, the default is English.\n"
            "9. Pay attention to whether it is uppercase of lowercase the relationship is. Use casing according to "
            "the schema.\n\n"
            "You:\n"
        )

    def _build_prompt(
        self, query: str, local_answer: str, external_answer: str, evidence: List[Evidence]
    ) -> str:
        citations = "\n".join(f"- {item.tool_id}: {item.locator.model_dump()}" for item in evidence)
        return (
            "Task:\n"
            "You are an answer generator within a RAG system that helps to compose an proper answer in response to "
            f"the question or instruction \"{query}\" from the user. Produce helpful, accurate, and "
            "well-structured answers based on retrieved context, model knowledge, and conversation history based on "
            "the information provided below:\n\n"
            "<INFORMATION>\n"
            "The data retrieved from the graph database\n"
            f"{external_answer}\n\n"
            "The data retrieved from the documents\n"
            f"{local_answer}\n\n"
            "Information from the previous conversation\n"
            "\n\n"
            "Project Description\n"
            "\n\n"
            "Evidence locators\n"
            f"{citations}\n"
            "<INFORMATION>\n\n"
            "If all the information is missing, reply to the user about the failure of fetching the data briefly "
            "(in under 50 words), and give up composing the answer.\n\n"
            "Consider the nature of the question and the context, you can compose the answer from the most specific "
            "way to the most comprehensive way. The bigger the question is, the more detailed and comprehensive the "
            "answer should be.\n\n"
            "For the detailed answers, consider explain the answer accompanied with markdown tables and charts "
            "(such as flowchart, pie chart, bar chart, radar chart, treemap, mindmap, quadrant chart, user journey, "
            "state diagram, and sequence diagram). When using charts, consider the nature of the data. "
            "If the data in question is proportional, consider using pie chart. If the data is comparative, consider "
            "using the bar chart. If the question is suitable for a simple or precise answers, you can also answer "
            "without the charts. If the bars is less than 4, or the values of the bars are all the same, don't use a "
            "bar chart. If the divisions of a pie chart are less than 3, don't use a pie chart.\n\n"
            "Note:\n"
            "1. Use markdown to format the answer. Use markdown to highlight keywords instead of using double quotes.\n"
            "2. Don't repeat the question in the answer. Skip the main title of the article. Start straight with the "
            "introduction.\n"
            "3. When using tables, use markdown table syntax.\n"
            "4. When using charts, create a code block and output a chart using this format: \"chartType: Title of "
            "the chart\".\n"
            "5. Do not include any explaination or other texts except the code block.\n"
            "6. If the retrieved data is missing or not enough to answer the question, simply explain to the user you "
            "did not find the data, do not reveal the details of the failed attempts.\n"
            "7. You can also ask questions to the user to clarify the question the user asked.\n"
            "8. Answer in the language of the question. If not sure about the language, the default is English.\n"
            "9. Pay attention to whether it is uppercase of lowercase the relationship is. Use casing according to "
            "the schema.\n\n"
            "Before generating the final answer, follow this reasoning chain:\n\n"
            "[Step 1: Assess retrieval state]\n"
            "Based on the query and retrieved information, determine:\n"
            "- Was context retrieved?\n"
            "- Is it relevant but insufficient?\n"
            "- Is it adequate?\n"
            "- Is it entirely missing?\n\n"
            "[Step 2: Select response strategy]\n"
            "- If context is adequate → answer directly + append inferred follow-up suggestion.\n"
            "- If context is insufficient → give partial answer + ask concrete clarification.\n"
            "- If no context → infer user intent + propose alternative phrasing or guidance.\n\n"
            "[Step 3: Generate the final message]\n"
            "- Write a natural response.\n"
            "- Append the selected strategy element at the end (suggestion / hypothesis / request for info).\n\n"
            "[Output requirement]\n"
            "Do NOT expose your reasoning chain.\n"
            "Only output the final answer, but it must reflect the decision you made above.\n\n"
            "You:\n"
        )
