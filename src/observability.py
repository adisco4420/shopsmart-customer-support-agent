"""
Observability: structured JSON logging, request-ID tracing, and LLM/tool metrics.

Usage:
    from src.observability import metrics_store, set_request_id, configure_logging

    configure_logging()          # call once at startup
    set_request_id("req-abc")    # set per-request (middleware does this automatically)
    metrics_store.record_llm_call(...)
"""

import contextvars
import json
import logging
import threading
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

# ---------------------------------------------------------------------------
# Request-ID propagation (works across async boundaries via contextvars)
# ---------------------------------------------------------------------------

_request_id_var: contextvars.ContextVar[str] = contextvars.ContextVar(
    "request_id", default="-"
)


def set_request_id(request_id: str) -> None:
    _request_id_var.set(request_id)


def get_request_id() -> str:
    return _request_id_var.get()


# ---------------------------------------------------------------------------
# Structured JSON log formatter
# ---------------------------------------------------------------------------


class JsonFormatter(logging.Formatter):
    """
    Emits every log record as a single JSON line, including the request_id
    from the current async context so log lines can be correlated across
    concurrent requests.
    """

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "timestamp": datetime.now(tz=timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "request_id": get_request_id(),
        }
        if record.exc_info:
            entry["exception"] = self.formatException(record.exc_info)
        if hasattr(record, "extra"):
            entry.update(record.extra)
        return json.dumps(entry)


def configure_logging(level: int = logging.INFO) -> None:
    """Replace the root handler with a structured JSON handler."""
    handler = logging.StreamHandler()
    handler.setFormatter(JsonFormatter())
    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(level)


# ---------------------------------------------------------------------------
# Metrics data classes
# ---------------------------------------------------------------------------


@dataclass
class LLMCallMetrics:
    request_id: str
    model: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    total_tokens: int = 0
    latency_ms: float = 0.0
    tool_call_count: int = 0
    iterations: int = 0
    success: bool = True
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


@dataclass
class ToolCallMetrics:
    request_id: str
    tool_name: str
    latency_ms: float
    success: bool
    error: Optional[str] = None
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )


# ---------------------------------------------------------------------------
# In-memory metrics store (thread-safe; swap for Prometheus / OTLP in prod)
# ---------------------------------------------------------------------------


class MetricsStore:
    """
    Lightweight, thread-safe in-memory store for runtime metrics.

    Retains only the most recent 1 000 records per category to bound memory
    usage. For production scale swap this for a Prometheus counter/histogram
    or an OTEL exporter.
    """

    _MAX_RECORDS = 1_000

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._llm_calls: list[LLMCallMetrics] = []
        self._tool_calls: list[ToolCallMetrics] = []
        self._request_count: int = 0
        self._error_count: int = 0

    # ------------------------------------------------------------------
    # Write methods
    # ------------------------------------------------------------------

    def record_request(self) -> None:
        with self._lock:
            self._request_count += 1

    def record_error(self) -> None:
        with self._lock:
            self._error_count += 1

    def record_llm_call(self, m: LLMCallMetrics) -> None:
        with self._lock:
            self._llm_calls.append(m)
            if len(self._llm_calls) > self._MAX_RECORDS:
                self._llm_calls = self._llm_calls[-self._MAX_RECORDS :]

    def record_tool_call(self, m: ToolCallMetrics) -> None:
        with self._lock:
            self._tool_calls.append(m)
            if len(self._tool_calls) > self._MAX_RECORDS:
                self._tool_calls = self._tool_calls[-self._MAX_RECORDS :]

    # ------------------------------------------------------------------
    # Read methods
    # ------------------------------------------------------------------

    def get_summary(self) -> dict:
        with self._lock:
            recent_llm = self._llm_calls[-100:]
            recent_tools = self._tool_calls[-100:]

        tool_counts: dict[str, int] = defaultdict(int)
        tool_errors: dict[str, int] = defaultdict(int)
        for tc in recent_tools:
            tool_counts[tc.tool_name] += 1
            if not tc.success:
                tool_errors[tc.tool_name] += 1

        successful_llm = [c for c in recent_llm if c.success]
        avg_latency = (
            sum(c.latency_ms for c in successful_llm) / len(successful_llm)
            if successful_llm
            else 0.0
        )
        total_tokens = sum(c.total_tokens for c in recent_llm)

        return {
            "requests_total": self._request_count,
            "errors_total": self._error_count,
            "error_rate": (
                round(self._error_count / self._request_count, 4)
                if self._request_count
                else 0.0
            ),
            "llm": {
                "calls_last_100": len(recent_llm),
                "success_rate": (
                    round(len(successful_llm) / len(recent_llm), 4) if recent_llm else 1.0
                ),
                "avg_latency_ms": round(avg_latency, 1),
                "total_tokens_last_100": total_tokens,
                "avg_tokens_per_call": (
                    round(total_tokens / len(recent_llm)) if recent_llm else 0
                ),
            },
            "tools": {
                "calls_last_100": len(recent_tools),
                "by_tool": dict(tool_counts),
                "errors_by_tool": dict(tool_errors),
            },
        }


# ---------------------------------------------------------------------------
# Timing context manager
# ---------------------------------------------------------------------------


class Timer:
    """Simple wall-clock timer: `with Timer() as t: ...; t.elapsed_ms`"""

    def __enter__(self) -> "Timer":
        self._start = time.perf_counter()
        return self

    def __exit__(self, *_) -> None:
        self.elapsed_ms = (time.perf_counter() - self._start) * 1000


# ---------------------------------------------------------------------------
# Module-level singleton — import and use directly
# ---------------------------------------------------------------------------

metrics_store = MetricsStore()
