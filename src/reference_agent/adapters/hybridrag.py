from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Optional, Tuple

import httpx

from reference_agent.models import Evidence, EvidenceLocator


@dataclass
class HybridRagConfig:
    base_url: str
    auth_token: Optional[str]
    timeout_seconds: int = 60


class HybridRagClient:
    def __init__(self, config: HybridRagConfig) -> None:
        self._base_url = config.base_url.rstrip("/")
        self._auth_token = config.auth_token
        self._timeout = config.timeout_seconds

    def _headers(self) -> dict:
        headers = {"accept": "*/*"}
        if self._auth_token:
            headers["Authorization"] = f"Bearer {self._auth_token}"
        return headers

    def create_chat(self) -> str:
        url = f"{self._base_url}/api/v1/chat/create"
        response = httpx.post(url, headers=self._headers(), json={}, timeout=self._timeout)
        response.raise_for_status()
        payload = response.json()
        return payload.get("data", {}).get("insertedId") or payload.get("insertedId")

    def send_message(self, chat_id: str, question: str, streaming: bool = False) -> Tuple[str, str]:
        url = f"{self._base_url}/api/v1/chat/{chat_id}"
        response = httpx.post(
            url,
            headers={**self._headers(), "Content-Type": "application/json"},
            json={"q": question, "streaming": streaming},
            timeout=self._timeout,
        )
        response.raise_for_status()
        return self._parse_result(response.text)

    def _parse_result(self, body: str) -> Tuple[str, str]:
        text = body.strip()
        if text.startswith("{"):
            payload = json.loads(text)
            result = payload.get("data", {}).get("result") or payload.get("response")
            message_id = payload.get("data", {}).get("messageId")
            return result or "", message_id or ""
        for line in text.splitlines():
            line = line.strip()
            if line.startswith("data:"):
                content = line[len("data:") :].strip()
                try:
                    payload = json.loads(content)
                except json.JSONDecodeError:
                    continue
                if "result" in payload:
                    return payload.get("result", ""), payload.get("messageId", "")
        return "", ""

    def get_messages(self, chat_id: str) -> dict:
        url = f"{self._base_url}/api/v1/chat/{chat_id}/messages"
        response = httpx.get(url, headers=self._headers(), timeout=self._timeout)
        response.raise_for_status()
        return response.json()

    def get_validation(self, chat_id: str, message_id: str) -> dict:
        url = f"{self._base_url}/api/v1/chat/{chat_id}/{message_id}/validation"
        response = httpx.get(url, headers=self._headers(), timeout=self._timeout)
        response.raise_for_status()
        return response.json()


def build_hybrid_evidence(tool_id: str, chat_id: str, message_id: str, snippet: Optional[str]) -> Evidence:
    locator = EvidenceLocator(chat_id=chat_id, messageId=message_id)
    return Evidence(
        source_type="hybrid_answer",
        tool_id=tool_id,
        source_id=message_id or chat_id,
        locator=locator,
        snippet=snippet,
        retrieval_meta={},
    )
