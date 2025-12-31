import re
from typing import Dict

TEMPLATES: Dict[str, Dict[str, str]] = {
    "en": {
        "TPL_NO_EVIDENCE_V1": "I could not find verifiable evidence to answer this question. Please provide more specific details or data sources.",
        "TPL_EMPTY_V1": "No relevant evidence was found for this query. Please clarify the scope or add more context.",
        "TPL_PARTIAL_V1": "Partial results are available. Some sources failed or returned no evidence. Please review the provided evidence and consider refining the query.",
    },
    "zh": {
        "TPL_NO_EVIDENCE_V1": "我找不到可驗證的證據來回答這個問題，請提供更具體的資訊或來源。",
        "TPL_EMPTY_V1": "沒有找到相關證據，請縮小範圍或補充更多上下文。",
        "TPL_PARTIAL_V1": "只有部分結果可用，部分來源失敗或無證據，請參考已提供的證據並調整問題。",
    },
}


def detect_language(text: str) -> str:
    if re.search(r"[\u4e00-\u9fff]", text):
        return "zh"
    return "en"


def get_template(template_id: str, query: str) -> str:
    language = detect_language(query)
    return TEMPLATES.get(language, TEMPLATES["en"]).get(
        template_id, TEMPLATES["en"]["TPL_NO_EVIDENCE_V1"]
    )
