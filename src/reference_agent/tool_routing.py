from __future__ import annotations

from typing import Optional

from reference_agent.models import ToolEntry

_CAPABILITY_PREFIX_PRIORITY = [
    ("hybrid_cot", "HYBRIDCOT:"),
    ("hybridcot", "HYBRIDCOT:"),
    ("hybrid_rag", "HYBRID:"),
    ("hybrid", "HYBRID:"),
    ("graph_rag", "GRAPH:"),
    ("graph", "GRAPH:"),
    ("vector_rag", "VECTOR:"),
    ("vector", "VECTOR:"),
    ("sql_rag", "SQL:"),
    ("sql", "SQL:"),
]


def prefix_for_tool(tool: ToolEntry) -> Optional[str]:
    if not tool.capabilities:
        return None
    capabilities = {cap.lower() for cap in tool.capabilities}
    for capability, prefix in _CAPABILITY_PREFIX_PRIORITY:
        if capability in capabilities:
            return prefix
    return None


def capability_for_rag_type(rag_type: str) -> Optional[str]:
    mapping = {
        "VECTOR": "vector_rag",
        "GRAPH": "graph_rag",
        "HYBRID": "hybrid_rag",
        "HYBRIDCOT": "hybrid_cot",
        "SQL": "sql_rag",
    }
    return mapping.get(rag_type.upper())
