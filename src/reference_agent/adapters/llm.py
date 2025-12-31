from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Dict, Optional

import httpx


@dataclass
class LLMRequest:
    prompt: str
    temperature: float
    max_tokens: int


class LLMClient:
    def __init__(self, provider: str, base_url: Optional[str], api_key: Optional[str], extra: Dict[str, str]) -> None:
        self._provider = provider
        if not base_url and provider in {"openai", "openai_compatible"}:
            base_url = "https://api.openai.com"
        self._base_url = (base_url or "").rstrip("/")
        self._api_key = api_key
        self._extra = extra

    def generate(self, model: str, request: LLMRequest) -> str:
        if self._provider in {"openai", "openai_compatible", "azure_openai", "ollama"}:
            return self._generate_openai_compatible(model, request)
        if self._provider == "anthropic":
            return self._generate_anthropic(model, request)
        if self._provider == "gemini":
            return self._generate_gemini(model, request)
        raise ValueError(f"Unsupported LLM provider: {self._provider}")

    def _headers(self, extra: Optional[Dict[str, str]] = None) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if self._api_key:
            headers["Authorization"] = f"Bearer {self._api_key}"
        if extra:
            headers.update(extra)
        return headers

    def _generate_openai_compatible(self, model: str, request: LLMRequest) -> str:
        if self._provider == "ollama" and not self._base_url:
            self._base_url = "http://localhost:11434"
        endpoint = self._extra.get("endpoint", "/v1/chat/completions")
        url = f"{self._base_url}{endpoint}"
        payload = {
            "model": model,
            "messages": [
                {"role": "system", "content": "You are a precise classifier and summarizer."},
                {"role": "user", "content": request.prompt},
            ],
            "temperature": request.temperature,
            "max_tokens": request.max_tokens,
        }
        if self._provider == "ollama":
            payload = {
                "model": model,
                "messages": [
                    {"role": "system", "content": "You are a precise classifier and summarizer."},
                    {"role": "user", "content": request.prompt},
                ],
                "stream": False,
            }
        if self._provider == "azure_openai":
            api_version = self._extra.get("api_version")
            if not api_version:
                raise ValueError("azure_openai requires extra.api_version")
            url = f"{self._base_url}/openai/deployments/{model}/chat/completions?api-version={api_version}"
            headers = self._headers({"api-key": self._api_key or ""})
        else:
            headers = self._headers()
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        if self._provider == "ollama":
            return data.get("message", {}).get("content", "")
        return data.get("choices", [{}])[0].get("message", {}).get("content", "")

    def _generate_anthropic(self, model: str, request: LLMRequest) -> str:
        if not self._base_url:
            self._base_url = "https://api.anthropic.com"
        url = f"{self._base_url}/v1/messages"
        headers = self._headers({
            "x-api-key": self._api_key or "",
            "anthropic-version": self._extra.get("anthropic_version", "2023-06-01"),
        })
        payload = {
            "model": model,
            "max_tokens": request.max_tokens,
            "temperature": request.temperature,
            "messages": [{"role": "user", "content": request.prompt}],
        }
        response = httpx.post(url, headers=headers, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        content = data.get("content", [])
        if content and isinstance(content, list):
            return content[0].get("text", "")
        return ""

    def _generate_gemini(self, model: str, request: LLMRequest) -> str:
        if not self._base_url:
            self._base_url = "https://generativelanguage.googleapis.com"
        url = f"{self._base_url}/v1beta/models/{model}:generateContent"
        params = {}
        if self._api_key:
            params["key"] = self._api_key
        payload = {
            "contents": [{"parts": [{"text": request.prompt}]}],
            "generationConfig": {
                "temperature": request.temperature,
                "maxOutputTokens": request.max_tokens,
            },
        }
        response = httpx.post(url, params=params, json=payload, timeout=30)
        response.raise_for_status()
        data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            return ""
        parts = candidates[0].get("content", {}).get("parts", [])
        return "".join(part.get("text", "") for part in parts)


def build_intent_prompt(query: str) -> str:
    instruction = (
        "Classify the user query into intents: citation, relation, external, or hybridcot. "
        "Return JSON with keys: intent (one of citation/relation/external/hybridcot/unknown)."
    )
    return f"{instruction}\nQuery: {query}"


def parse_intent_response(text: str) -> str:
    try:
        data = json.loads(text)
        return data.get("intent", "unknown")
    except json.JSONDecodeError:
        return "unknown"
