from __future__ import annotations

from dataclasses import dataclass
from typing import List, Optional, Tuple

import httpx

from reference_agent.models import Evidence


@dataclass
class ExternalMcpConfig:
    base_url: str
    tool_path_template: str = "/tools/{tool_id}"
    auth_token: Optional[str] = None


class ExternalMcpClient:
    def __init__(self, config: ExternalMcpConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._path_template = config.tool_path_template
        self._auth_token = config.auth_token

    def _headers(self) -> dict:
        headers = {"accept": "application/json"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def query(self, tool_id: str, query: str) -> Tuple[str, List[Evidence]]:
        path = self._path_template.format(tool_id=tool_id)
        url = f"{self._base_url}{path}"
        response = httpx.post(url, headers=self._headers(), json={"query": query})
        response.raise_for_status()
        payload = response.json()
        answer = payload.get("answer", "")
        evidence = [Evidence(**item) for item in payload.get("evidence", [])]
        return answer, evidence
