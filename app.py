"""
ShopSmart Customer Support — FastAPI web application.
Exposes a streaming SSE chat endpoint backed by the MCP agent.
"""

import json
import logging
import os
import uuid
from collections import OrderedDict
from datetime import UTC, datetime, timedelta

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from pydantic import BaseModel, Field

from src.agent.runner import run_agent
from src.observability import (
    configure_logging,
    get_request_id,
    metrics_store,
    set_request_id,
)
from src.tracing import setup_tracing

load_dotenv()
configure_logging()
setup_tracing()
logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Application
# ---------------------------------------------------------------------------

app = FastAPI(
    title="ShopSmart Support Agent",
    version="1.0.0",
    description="AI-powered customer support backed by MCP tools and OpenRouter.",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["POST", "GET", "OPTIONS"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request-ID middleware — assigns a UUID to every request for log correlation
# ---------------------------------------------------------------------------


@app.middleware("http")
async def request_id_middleware(request: Request, call_next):
    req_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
    set_request_id(req_id)
    response = await call_next(request)
    response.headers["X-Request-ID"] = req_id
    return response


# ---------------------------------------------------------------------------
# Session store (LRU-style, in-memory — swap for Redis in scaled deployments)
# ---------------------------------------------------------------------------

SESSION_TTL = timedelta(minutes=30)
MAX_SESSIONS = 500
_sessions: OrderedDict[str, dict] = OrderedDict()


def _get_history(session_id: str) -> list[dict]:
    """Return the conversation history for a session, creating it if absent."""
    now = datetime.now(tz=UTC)

    expired = [k for k, v in _sessions.items() if now - v["last_active"] > SESSION_TTL]
    for k in expired:
        del _sessions[k]

    if session_id not in _sessions:
        if len(_sessions) >= MAX_SESSIONS:
            _sessions.popitem(last=False)
        _sessions[session_id] = {"history": [], "last_active": now}
    else:
        _sessions[session_id]["last_active"] = now
        _sessions.move_to_end(session_id)

    return _sessions[session_id]["history"]


def _update_history(session_id: str, user_msg: str, assistant_msg: str) -> None:
    if session_id not in _sessions:
        return
    history = _sessions[session_id]["history"]
    history.append({"role": "user", "content": user_msg})
    history.append({"role": "assistant", "content": assistant_msg})
    if len(history) > 40:
        _sessions[session_id]["history"] = history[-40:]


# ---------------------------------------------------------------------------
# Request / Response models
# ---------------------------------------------------------------------------


class ChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=2000)
    session_id: str | None = Field(default=None)


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------


@app.get("/health")
async def health():
    return {
        "status": "ok",
        "service": "shopsmart-support",
        "active_sessions": len(_sessions),
        "timestamp": datetime.now(tz=UTC).isoformat(),
    }


@app.get("/metrics")
async def get_metrics():
    """Runtime metrics: LLM token usage, tool call breakdown, error rates."""
    return metrics_store.get_summary()


@app.post("/chat")
async def chat(body: ChatRequest, request: Request):
    """
    Stream an agent response as Server-Sent Events.

    Each event is a JSON object with a 'type' field:
    - {"type": "session_id", "session_id": "<uuid>"}
    - {"type": "text", "content": "<chunk>"}
    - {"type": "tool", "name": "<tool_name>"}
    - {"type": "done"}
    - {"type": "error", "message": "<error>"}
    """
    if not os.getenv("OPENROUTER_API_KEY"):
        raise HTTPException(status_code=503, detail="OPENROUTER_API_KEY is not configured.")

    session_id = body.session_id or str(uuid.uuid4())
    req_id = get_request_id()
    history = _get_history(session_id)
    metrics_store.record_request()

    logger.info(
        "Chat request received | session_id=%s message_len=%d",
        session_id,
        len(body.message),
    )

    async def event_stream():
        yield _sse({"type": "session_id", "session_id": session_id})

        text_buffer: list[str] = []
        try:
            async for chunk in run_agent(
                body.message,
                history,
                request_id=req_id,
                session_id=session_id,
            ):
                if chunk.startswith("\x00TOOL:"):
                    tool_name = chunk[6:].strip()
                    yield _sse({"type": "tool", "name": tool_name})
                else:
                    text_buffer.append(chunk)
                    yield _sse({"type": "text", "content": chunk})
        except Exception as exc:
            metrics_store.record_error()
            logger.exception("Agent error | request_id=%s: %s", req_id, exc)
            yield _sse({
                "type": "error",
                "message": "An unexpected error occurred. Please try again.",
                "request_id": req_id,
            })
            return

        assistant_response = "".join(text_buffer).strip()
        _update_history(session_id, body.message, assistant_response)
        yield _sse({"type": "done"})

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
        },
    )


@app.get("/")
async def root():
    return FileResponse("static/index.html")


def _sse(data: dict) -> str:
    return f"data: {json.dumps(data)}\n\n"
