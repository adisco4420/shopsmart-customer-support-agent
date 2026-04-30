"""
Integration tests for the FastAPI application endpoints.
The agent is mocked so these tests run without API keys or a live MCP server.
"""

import json

import pytest

from tests.conftest import collect_sse_events


# ===========================================================================
# /health
# ===========================================================================


class TestHealthEndpoint:
    def test_returns_200(self, sync_client):
        resp = sync_client.get("/health")
        assert resp.status_code == 200

    def test_body_contains_required_fields(self, sync_client):
        data = sync_client.get("/health").json()
        assert data["status"] == "ok"
        assert data["service"] == "shopsmart-support"
        assert "active_sessions" in data
        assert "timestamp" in data

    def test_timestamp_is_iso_format(self, sync_client):
        data = sync_client.get("/health").json()
        from datetime import datetime
        # Should not raise
        datetime.fromisoformat(data["timestamp"])


# ===========================================================================
# /metrics
# ===========================================================================


class TestMetricsEndpoint:
    def test_returns_200(self, sync_client):
        resp = sync_client.get("/metrics")
        assert resp.status_code == 200

    def test_body_has_expected_keys(self, sync_client):
        data = sync_client.get("/metrics").json()
        assert "requests_total" in data
        assert "errors_total" in data
        assert "llm" in data
        assert "tools" in data


# ===========================================================================
# GET /
# ===========================================================================


class TestRootEndpoint:
    def test_serves_html(self, sync_client):
        resp = sync_client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_contains_shopsmart_branding(self, sync_client):
        resp = sync_client.get("/")
        assert b"ShopSmart" in resp.content


# ===========================================================================
# POST /chat — SSE streaming tests
# ===========================================================================


class TestChatEndpoint:
    async def test_streams_session_id_first(self, async_client, mock_agent_plain):
        async with async_client.stream(
            "POST", "/chat", json={"message": "hello"}
        ) as resp:
            assert resp.status_code == 200
            events = await collect_sse_events(resp)

        assert events[0]["type"] == "session_id"
        assert "session_id" in events[0]

    async def test_streams_text_chunks(self, async_client, mock_agent_plain):
        async with async_client.stream(
            "POST", "/chat", json={"message": "hello"}
        ) as resp:
            events = await collect_sse_events(resp)

        text_events = [e for e in events if e["type"] == "text"]
        assert len(text_events) > 0
        full_text = "".join(e["content"] for e in text_events)
        assert "answer" in full_text.lower()

    async def test_streams_done_event_at_end(self, async_client, mock_agent_plain):
        async with async_client.stream(
            "POST", "/chat", json={"message": "hello"}
        ) as resp:
            events = await collect_sse_events(resp)

        assert events[-1]["type"] == "done"

    async def test_streams_tool_event(self, async_client, mock_agent_with_tool):
        async with async_client.stream(
            "POST", "/chat", json={"message": "where is my order ORD-12345?"}
        ) as resp:
            events = await collect_sse_events(resp)

        tool_events = [e for e in events if e["type"] == "tool"]
        assert len(tool_events) == 1
        assert tool_events[0]["name"] == "get_order_status"

    async def test_persists_session_across_requests(self, async_client, mock_agent_plain):
        # First request creates a session
        async with async_client.stream(
            "POST", "/chat", json={"message": "hello"}
        ) as resp:
            events = await collect_sse_events(resp)
        session_id = events[0]["session_id"]

        # Second request with same session_id should succeed
        async with async_client.stream(
            "POST", "/chat", json={"message": "follow-up", "session_id": session_id}
        ) as resp:
            events2 = await collect_sse_events(resp)

        assert events2[0]["session_id"] == session_id

    async def test_returns_error_event_on_agent_failure(
        self, async_client, mock_agent_error
    ):
        async with async_client.stream(
            "POST", "/chat", json={"message": "trigger error"}
        ) as resp:
            events = await collect_sse_events(resp)

        error_events = [e for e in events if e["type"] == "error"]
        assert len(error_events) == 1
        assert "message" in error_events[0]

    def test_rejects_empty_message(self, sync_client, mock_agent_plain):
        resp = sync_client.post("/chat", json={"message": ""})
        assert resp.status_code == 422

    def test_rejects_message_over_2000_chars(self, sync_client, mock_agent_plain):
        resp = sync_client.post("/chat", json={"message": "x" * 2001})
        assert resp.status_code == 422

    def test_response_has_content_type_sse(self, sync_client, mock_agent_plain):
        resp = sync_client.post("/chat", json={"message": "hi"})
        assert "text/event-stream" in resp.headers["content-type"]

    def test_response_has_request_id_header(self, sync_client, mock_agent_plain):
        resp = sync_client.post("/chat", json={"message": "hi"})
        assert "x-request-id" in resp.headers

    def test_returns_503_when_api_key_missing(self, sync_client, mock_agent_plain, monkeypatch):
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        import os
        os.environ.pop("OPENROUTER_API_KEY", None)
        # Re-patch the env check in app
        import app as app_module
        original = app_module.os.getenv

        def patched_getenv(key, *args):
            if key == "OPENROUTER_API_KEY":
                return None
            return original(key, *args)

        monkeypatch.setattr(app_module.os, "getenv", patched_getenv)
        resp = sync_client.post("/chat", json={"message": "hi"})
        assert resp.status_code == 503
