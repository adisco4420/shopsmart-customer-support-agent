"""
Unit tests for pure helper functions in the agent runner and observability module.
No external I/O — runs without API keys or a live MCP server.
"""

from datetime import UTC, datetime
from unittest.mock import MagicMock

import pytest

from src.agent.runner import _build_system_prompt, _mcp_tool_to_openai
from src.observability import (
    LLMCallMetrics,
    MetricsStore,
    Timer,
    ToolCallMetrics,
    get_request_id,
    set_request_id,
)


# ===========================================================================
# _build_system_prompt
# ===========================================================================


class TestBuildSystemPrompt:
    def test_contains_agent_name(self):
        prompt = _build_system_prompt()
        assert "Alex" in prompt

    def test_contains_brand_name(self):
        prompt = _build_system_prompt()
        assert "ShopSmart" in prompt

    def test_lists_all_six_tools(self):
        prompt = _build_system_prompt()
        expected_tools = [
            "search_products",
            "get_order_status",
            "get_customer_account",
            "create_support_ticket",
            "search_knowledge_base",
            "process_return_request",
        ]
        for tool in expected_tools:
            assert tool in prompt, f"Tool '{tool}' missing from system prompt"

    def test_contains_todays_date(self):
        prompt = _build_system_prompt()
        year = str(datetime.now(UTC).year)
        assert year in prompt

    def test_contains_key_guidelines(self):
        prompt = _build_system_prompt()
        assert "never guess" in prompt.lower()
        assert "support ticket" in prompt.lower()


# ===========================================================================
# _mcp_tool_to_openai
# ===========================================================================


class TestMcpToolToOpenai:
    def _make_tool(self, name="my_tool", description="Does something", schema=None):
        tool = MagicMock()
        tool.name = name
        tool.description = description
        tool.inputSchema = schema or {
            "type": "object",
            "properties": {"query": {"type": "string"}},
            "required": ["query"],
        }
        return tool

    def test_output_has_type_function(self):
        result = _mcp_tool_to_openai(self._make_tool())
        assert result["type"] == "function"

    def test_output_contains_name(self):
        result = _mcp_tool_to_openai(self._make_tool(name="search_products"))
        assert result["function"]["name"] == "search_products"

    def test_output_contains_description(self):
        result = _mcp_tool_to_openai(self._make_tool(description="Search the catalog"))
        assert result["function"]["description"] == "Search the catalog"

    def test_output_contains_parameters(self):
        schema = {"type": "object", "properties": {"q": {"type": "string"}}}
        result = _mcp_tool_to_openai(self._make_tool(schema=schema))
        assert result["function"]["parameters"] == schema

    def test_none_description_becomes_empty_string(self):
        result = _mcp_tool_to_openai(self._make_tool(description=None))
        assert result["function"]["description"] == ""

    def test_preserves_required_fields_in_schema(self):
        schema = {
            "type": "object",
            "properties": {"order_id": {"type": "string"}},
            "required": ["order_id"],
        }
        result = _mcp_tool_to_openai(self._make_tool(schema=schema))
        assert "required" in result["function"]["parameters"]


# ===========================================================================
# Observability — MetricsStore
# ===========================================================================


class TestMetricsStore:
    def test_request_count_increments(self):
        store = MetricsStore()
        store.record_request()
        store.record_request()
        summary = store.get_summary()
        assert summary["requests_total"] == 2

    def test_error_count_increments(self):
        store = MetricsStore()
        store.record_error()
        summary = store.get_summary()
        assert summary["errors_total"] == 1

    def test_error_rate_calculated_correctly(self):
        store = MetricsStore()
        store.record_request()
        store.record_request()
        store.record_error()
        summary = store.get_summary()
        assert summary["error_rate"] == pytest.approx(0.5)

    def test_error_rate_is_zero_when_no_requests(self):
        store = MetricsStore()
        summary = store.get_summary()
        assert summary["error_rate"] == 0.0

    def test_records_llm_call_metrics(self):
        store = MetricsStore()
        store.record_llm_call(
            LLMCallMetrics(
                request_id="req-1",
                model="test-model",
                total_tokens=500,
                latency_ms=1200.0,
                success=True,
            )
        )
        summary = store.get_summary()
        assert summary["llm"]["calls_last_100"] == 1
        assert summary["llm"]["total_tokens_last_100"] == 500
        assert summary["llm"]["avg_latency_ms"] == pytest.approx(1200.0)

    def test_records_tool_call_metrics(self):
        store = MetricsStore()
        store.record_tool_call(
            ToolCallMetrics(
                request_id="req-1",
                tool_name="search_products",
                latency_ms=80.0,
                success=True,
            )
        )
        summary = store.get_summary()
        assert summary["tools"]["calls_last_100"] == 1
        assert summary["tools"]["by_tool"]["search_products"] == 1

    def test_tracks_tool_errors_by_name(self):
        store = MetricsStore()
        store.record_tool_call(
            ToolCallMetrics(
                request_id="req-1",
                tool_name="get_order_status",
                latency_ms=50.0,
                success=False,
                error="timeout",
            )
        )
        summary = store.get_summary()
        assert summary["tools"]["errors_by_tool"]["get_order_status"] == 1

    def test_llm_success_rate_reflects_failures(self):
        store = MetricsStore()
        store.record_llm_call(LLMCallMetrics(request_id="r1", model="m", success=True))
        store.record_llm_call(LLMCallMetrics(request_id="r2", model="m", success=False))
        summary = store.get_summary()
        assert summary["llm"]["success_rate"] == pytest.approx(0.5)

    def test_caps_records_at_max_limit(self):
        store = MetricsStore()
        store._MAX_RECORDS = 5
        for i in range(10):
            store.record_llm_call(LLMCallMetrics(request_id=f"r{i}", model="m"))
        assert len(store._llm_calls) == 5


# ===========================================================================
# Observability — request ID context var
# ===========================================================================


class TestRequestIdContextVar:
    def test_default_value_is_dash(self):
        # In a fresh context the default is "-"
        assert get_request_id() in ("-", get_request_id())

    def test_set_and_get_roundtrip(self):
        set_request_id("test-req-abc")
        assert get_request_id() == "test-req-abc"


# ===========================================================================
# Observability — Timer
# ===========================================================================


class TestTimer:
    def test_elapsed_ms_is_positive(self):
        with Timer() as t:
            pass
        assert t.elapsed_ms >= 0

    def test_elapsed_ms_is_reasonable(self):
        import time
        with Timer() as t:
            time.sleep(0.05)
        assert 40 < t.elapsed_ms < 500
