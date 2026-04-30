"""
Agent runner: connects to the MCP server over stdio, then orchestrates
an OpenRouter LLM through the full tool-use loop, streaming text back to the caller.

Retry policy:   up to 3 attempts on RateLimitError / APITimeoutError with
                exponential back-off (1 s, 2 s, 4 s).
Timeouts:       10 s per MCP tool call; 120 s total per agent turn.
Observability:  every LLM call and every tool call is recorded in
                metrics_store AND traced in Langfuse (when credentials present).

Langfuse trace hierarchy per agent turn
──────────────────────────────────────
agent-turn  (as_type="agent")
  ├─ llm-generation-1  (as_type="generation")
  ├─ tool:<name>       (as_type="tool")   ← 0..N per iteration
  ├─ llm-generation-2
  └─ ...
"""

import asyncio
import json
import logging
import os
import sys
import time
from collections.abc import AsyncIterator
from datetime import UTC, datetime

import openai
from langfuse import get_client
from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client
from openai import AsyncOpenAI

from src.observability import LLMCallMetrics, Timer, ToolCallMetrics, metrics_store

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "anthropic/claude-sonnet-4.6"

_RETRYABLE_ERRORS = (
    openai.RateLimitError,
    openai.APITimeoutError,
    openai.APIConnectionError,
)

SYSTEM_PROMPT = """\
You are Alex, a friendly and professional customer support agent for ShopSmart \
— a premium online retail store.

You have access to the following tools:
- search_products: find items in the product catalog
- get_order_status: look up order tracking and status
- get_customer_account: retrieve a customer's account and order history
- create_support_ticket: open a support ticket for unresolved issues
- search_knowledge_base: search FAQs and help articles
- process_return_request: initiate a return or refund

Guidelines:
- Always use your tools to fetch accurate, real-time information — never guess.
- Be concise, warm, and solution-oriented.
- When creating a support ticket, confirm the subject and priority with the customer first.
- If a customer provides an order ID or customer ID, use it directly with the appropriate tool.
- If a tool returns an error, acknowledge it transparently and offer an alternative.
- Today's date is {date}.
"""


def _build_system_prompt() -> str:
    return SYSTEM_PROMPT.format(date=datetime.now(UTC).strftime("%B %d, %Y"))


def _mcp_tool_to_openai(tool) -> dict:
    """Convert an MCP ToolDef to the OpenAI function-calling schema."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description or "",
            "parameters": tool.inputSchema,
        },
    }


async def _call_llm_with_retry(
    client: AsyncOpenAI,
    model: str,
    messages: list[dict],
    tools: list[dict],
    *,
    max_retries: int = 3,
):
    """
    Call the LLM with exponential back-off retry on transient errors.

    Retries on: RateLimitError, APITimeoutError, APIConnectionError.
    Raises immediately on all other API errors.
    """
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            return await client.chat.completions.create(
                model=model,
                messages=messages,
                tools=tools,
                tool_choice="auto",
                stream=True,
                stream_options={"include_usage": True},
            )
        except _RETRYABLE_ERRORS as exc:
            last_exc = exc
            if attempt < max_retries - 1:
                wait_s = 2**attempt
                logger.warning(
                    "LLM call failed on attempt %d/%d — retrying in %ds: %s",
                    attempt + 1,
                    max_retries,
                    wait_s,
                    exc,
                )
                await asyncio.sleep(wait_s)
        except openai.APIError:
            raise
    assert last_exc is not None
    raise last_exc


async def run_agent(
    user_message: str,
    conversation_history: list[dict] | None = None,
    request_id: str = "-",
    session_id: str | None = None,
) -> AsyncIterator[str]:
    """
    Run the support agent for one user turn.

    Yields text chunks as they are produced. Tool-use notifications are yielded
    as lines prefixed with the sentinel '\\x00TOOL:' so the caller can render
    them distinctly.

    Bounded by a 120-second total timeout per turn (asyncio.timeout).
    Every LLM call and tool call is traced in Langfuse when credentials are set.

    Args:
        user_message: The latest message from the user.
        conversation_history: Prior turns (role/content dicts), excluding the
                              current user_message.
        request_id: Trace ID propagated from the HTTP request for log correlation.
        session_id: Conversation session ID — used as Langfuse session for
                    grouping all turns of a single conversation.
    """
    server_params = StdioServerParameters(
        command=sys.executable,
        args=["-m", "src.mcp_server"],
        env={**os.environ},
    )

    model = os.getenv("OPENROUTER_MODEL", DEFAULT_MODEL)
    lf = get_client()

    llm_metrics = LLMCallMetrics(request_id=request_id, model=model)

    try:
        async with asyncio.timeout(120):
            # ----------------------------------------------------------------
            # Langfuse: top-level agent-turn trace
            # ----------------------------------------------------------------
            with lf.start_as_current_observation(
                name="support-agent-turn",
                as_type="agent",
                input={"message": user_message},
                metadata={
                    "request_id": request_id,
                    "session_id": session_id,
                    "model": model,
                },
            ):
                lf.set_current_trace_io(input={"message": user_message})

                async with stdio_client(server_params) as (read, write):
                    async with ClientSession(read, write) as session:
                        await session.initialize()

                        tools_list = await session.list_tools()
                        openai_tools = [_mcp_tool_to_openai(t) for t in tools_list.tools]
                        logger.info(
                            "MCP session initialised with %d tools", len(openai_tools)
                        )

                        client = AsyncOpenAI(
                            base_url=OPENROUTER_BASE_URL,
                            api_key=os.environ["OPENROUTER_API_KEY"],
                            default_headers={
                                "HTTP-Referer": os.getenv("APP_URL", "http://localhost:8000"),
                                "X-Title": "ShopSmart Support Agent",
                            },
                        )

                        messages: list[dict] = [
                            {"role": "system", "content": _build_system_prompt()},
                            *(conversation_history or []),
                            {"role": "user", "content": user_message},
                        ]

                        max_iterations = 8
                        agent_start = time.perf_counter()
                        final_text = ""
                        tools_called: list[str] = []

                        for iteration in range(max_iterations):
                            logger.info(
                                "Agent iteration %d/%d | request_id=%s",
                                iteration + 1,
                                max_iterations,
                                request_id,
                            )

                            # ----------------------------------------------------
                            # Langfuse: one generation span per LLM call
                            # ----------------------------------------------------
                            with lf.start_as_current_observation(
                                name=f"llm-generation-{iteration + 1}",
                                as_type="generation",
                                model=model,
                                model_parameters={
                                    "stream": True,
                                    "tool_choice": "auto",
                                },
                                input=messages,
                            ):
                                response = await _call_llm_with_retry(
                                    client,
                                    model=model,
                                    messages=messages,
                                    tools=openai_tools,
                                )

                                content_parts: list[str] = []
                                tool_calls_raw: dict[int, dict] = {}
                                finish_reason: str | None = None
                                usage_data: dict = {}

                                async for chunk in response:
                                    if hasattr(chunk, "usage") and chunk.usage:
                                        usage_data = {
                                            "prompt_tokens": chunk.usage.prompt_tokens,
                                            "completion_tokens": chunk.usage.completion_tokens,
                                            "total_tokens": chunk.usage.total_tokens,
                                        }

                                    if not chunk.choices:
                                        continue
                                    choice = chunk.choices[0]
                                    finish_reason = choice.finish_reason or finish_reason
                                    delta = choice.delta

                                    if delta.content:
                                        content_parts.append(delta.content)
                                        yield delta.content

                                    if delta.tool_calls:
                                        for tc in delta.tool_calls:
                                            idx = tc.index
                                            if idx not in tool_calls_raw:
                                                tool_calls_raw[idx] = {
                                                    "id": "",
                                                    "type": "function",
                                                    "function": {"name": "", "arguments": ""},
                                                }
                                            if tc.id:
                                                tool_calls_raw[idx]["id"] = tc.id
                                            if tc.function:
                                                if tc.function.name:
                                                    fn_dict = tool_calls_raw[idx]["function"]
                                                    fn_dict["name"] += tc.function.name
                                                if tc.function.arguments:
                                                    fn_dict = tool_calls_raw[idx]["function"]
                                                    fn_dict["arguments"] += tc.function.arguments

                                full_content = "".join(content_parts)

                                # Update generation with streamed output + token usage
                                lf.update_current_generation(
                                    output=full_content,
                                    usage_details={
                                        "input": usage_data.get("prompt_tokens", 0),
                                        "output": usage_data.get("completion_tokens", 0),
                                        "total": usage_data.get("total_tokens", 0),
                                    },
                                    metadata={
                                        "iteration": iteration + 1,
                                        "finish_reason": finish_reason,
                                    },
                                )

                            # Accumulate per-turn token metrics
                            llm_metrics.prompt_tokens += usage_data.get("prompt_tokens", 0)
                            llm_metrics.completion_tokens += usage_data.get("completion_tokens", 0)
                            llm_metrics.total_tokens += usage_data.get("total_tokens", 0)
                            llm_metrics.iterations = iteration + 1

                            tool_calls = list(tool_calls_raw.values())
                            assistant_msg: dict = {"role": "assistant", "content": full_content}
                            if tool_calls:
                                assistant_msg["tool_calls"] = tool_calls
                            messages.append(assistant_msg)

                            if not tool_calls:
                                final_text = full_content
                                break

                            # ------------------------------------------------
                            # Execute each MCP tool call
                            # ------------------------------------------------
                            for tc in tool_calls:
                                fn_name = tc["function"]["name"]
                                raw_args = tc["function"]["arguments"] or "{}"
                                try:
                                    fn_args = json.loads(raw_args)
                                except json.JSONDecodeError:
                                    fn_args = {}

                                logger.info(
                                    "Tool call: %s args=%s | request_id=%s",
                                    fn_name,
                                    fn_args,
                                    request_id,
                                )
                                yield f"\x00TOOL:{fn_name}\n"
                                llm_metrics.tool_call_count += 1
                                tools_called.append(fn_name)

                                # ----------------------------------------
                                # Langfuse: tool span
                                # ----------------------------------------
                                with lf.start_as_current_observation(
                                    name=fn_name,
                                    as_type="tool",
                                    input=fn_args,
                                ):
                                    with Timer() as tool_timer:
                                        tool_success = True
                                        tool_error: str | None = None
                                        try:
                                            async with asyncio.timeout(10):
                                                tool_result = await session.call_tool(
                                                    fn_name, fn_args
                                                )
                                            no_content = json.dumps(
                                                {"error": "Tool returned no content"}
                                            )
                                            result_text = (
                                                tool_result.content[0].text
                                                if tool_result.content
                                                else no_content
                                            )
                                        except TimeoutError:
                                            tool_success = False
                                            tool_error = (
                                                f"Tool '{fn_name}' timed out after 10 seconds"
                                            )
                                            result_text = json.dumps({"error": tool_error})
                                            logger.error(
                                                "Tool timeout: %s | request_id=%s",
                                                fn_name,
                                                request_id,
                                            )
                                        except Exception as exc:
                                            tool_success = False
                                            tool_error = str(exc)
                                            result_text = json.dumps({"error": tool_error})
                                            logger.exception(
                                                "Tool error: %s | request_id=%s",
                                                fn_name,
                                                request_id,
                                            )

                                    lf.update_current_span(
                                        output=result_text,
                                        metadata={
                                            "success": tool_success,
                                            "latency_ms": round(tool_timer.elapsed_ms, 1),
                                            "error": tool_error,
                                        },
                                    )

                                metrics_store.record_tool_call(
                                    ToolCallMetrics(
                                        request_id=request_id,
                                        tool_name=fn_name,
                                        latency_ms=tool_timer.elapsed_ms,
                                        success=tool_success,
                                        error=tool_error,
                                    )
                                )

                                messages.append({
                                    "role": "tool",
                                    "tool_call_id": tc["id"],
                                    "content": result_text,
                                })
                        else:
                            final_text = (
                                "I'm sorry, I wasn't able to complete your request within "
                                "the allowed steps. Please try again or contact support directly."
                            )
                            yield f"\n\n{final_text}"

                        llm_metrics.latency_ms = (time.perf_counter() - agent_start) * 1000
                        llm_metrics.success = True

                        # Update the top-level trace with the final output
                        lf.set_current_trace_io(
                            output={
                                "response": final_text,
                                "tools_called": tools_called,
                                "iterations": llm_metrics.iterations,
                                "total_tokens": llm_metrics.total_tokens,
                            }
                        )

    except TimeoutError:
        llm_metrics.success = False
        llm_metrics.error = "Agent turn exceeded 120s timeout"
        logger.error("Agent turn timed out | request_id=%s", request_id)
        yield "\n\nI'm sorry, the request took too long. Please try again."
    except KeyError as exc:
        llm_metrics.success = False
        llm_metrics.error = str(exc)
        logger.error("Missing config: %s | request_id=%s", exc, request_id)
        raise
    finally:
        metrics_store.record_llm_call(llm_metrics)
