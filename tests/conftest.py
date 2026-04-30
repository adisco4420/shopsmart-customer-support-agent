"""
Shared pytest fixtures.
"""

import json
from collections.abc import AsyncIterator
from unittest.mock import patch

import pytest
from fastapi.testclient import TestClient
from httpx import ASGITransport, AsyncClient


# ---------------------------------------------------------------------------
# FastAPI app fixture — imported here to avoid circular imports in tests
# ---------------------------------------------------------------------------


@pytest.fixture(scope="session")
def app():
    from app import app as fastapi_app
    return fastapi_app


@pytest.fixture()
def sync_client(app):
    """Synchronous TestClient for simple endpoint tests."""
    with TestClient(app, raise_server_exceptions=True) as c:
        yield c


@pytest.fixture()
async def async_client(app):
    """Async HTTPX client for streaming / async endpoint tests."""
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


# ---------------------------------------------------------------------------
# Mock agent — avoids spawning a real MCP subprocess + LLM call in app tests
# ---------------------------------------------------------------------------


async def _fake_agent_plain(user_message, conversation_history=None, request_id="-", session_id=None):
    """Returns a fixed text response (no tool calls)."""
    yield "Here is your answer."


async def _fake_agent_with_tool(user_message, conversation_history=None, request_id="-", session_id=None):
    """Simulates one tool call followed by a text response."""
    yield "\x00TOOL:get_order_status\n"
    yield "Your order ORD-12345 is currently "
    yield "shipped and expected by May 2, 2026."


async def _fake_agent_error(user_message, conversation_history=None, request_id="-", session_id=None):
    """Raises an exception to test error handling."""
    raise RuntimeError("Simulated agent failure")
    yield  # make it an async generator


@pytest.fixture()
def mock_agent_plain():
    with patch("app.run_agent", _fake_agent_plain):
        yield


@pytest.fixture()
def mock_agent_with_tool():
    with patch("app.run_agent", _fake_agent_with_tool):
        yield


@pytest.fixture()
def mock_agent_error():
    with patch("app.run_agent", _fake_agent_error):
        yield


# ---------------------------------------------------------------------------
# Helper: collect SSE events from a streaming response body
# ---------------------------------------------------------------------------


async def collect_sse_events(response) -> list[dict]:
    """Parse all `data: {...}` lines from an SSE response into dicts."""
    events: list[dict] = []
    async for line in response.aiter_lines():
        if line.startswith("data: "):
            events.append(json.loads(line[6:]))
    return events
