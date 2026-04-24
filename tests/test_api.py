import pytest
import httpx

from reference_agent.app import create_app


@pytest.mark.asyncio
async def test_ask_endpoint(monkeypatch, temp_config):
    from reference_agent.adapters import hybridrag
    from reference_agent.adapters.llm import LLMClient

    def fake_create_chat(self, title=None):
        return "chat123"

    def fake_send_message(self, chat_id, question, streaming=False):
        return "Answer", "msg123"

    def fake_llm(self, model, request):
        return (
            '{'
            '"answer_blueprint": ["Test"], '
            '"required_bindings": [], '
            '"candidate_tools": [], '
            '"constraints": {}, '
            '"stop_conditions": []'
            '}'
        )

    monkeypatch.setattr(hybridrag.HybridRagClient, "create_chat", fake_create_chat)
    monkeypatch.setattr(hybridrag.HybridRagClient, "send_message", fake_send_message)
    monkeypatch.setattr(LLMClient, "generate", fake_llm)

    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.post(
            "/ask", json={"query": "What is X?", "profile_id": "default"}
        )
        assert response.status_code == 200
        payload = response.json()
        assert payload["status"] == "SUCCESS"
        assert payload["evidence"]


@pytest.mark.asyncio
async def test_capabilities(temp_config):
    app = create_app()
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
        response = await client.get("/capabilities", params={"profile_id": "default"})
        assert response.status_code == 200
        payload = response.json()
        assert payload["profile_id"] == "default"
