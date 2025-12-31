from __future__ import annotations

from typing import List

from reference_agent.models import Evidence

SOURCE_PRIORITY = {
    "hybrid_answer": 1,
    "vector_chunk": 2,
    "graph_node": 3,
    "graph_edge": 4,
    "external_chunk": 5,
    "sql_row": 6,
    "sql_metric": 7,
}


def dedupe_evidence(evidence: List[Evidence]) -> List[Evidence]:
    seen = {}
    for item in evidence:
        if item.source_id not in seen:
            seen[item.source_id] = item
    return list(seen.values())


def sort_evidence(evidence: List[Evidence]) -> List[Evidence]:
    return sorted(evidence, key=lambda item: SOURCE_PRIORITY.get(item.source_type, 99))
