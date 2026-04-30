"""
LLM-as-judge evaluation framework.

The evaluator runs the agent against each test case in test_cases.py and
uses a second LLM call (the judge) to score the response on a rubric.
This provides a measurable quality baseline that can be tracked over time.

Usage:
    from src.eval.evaluator import run_evaluation
    asyncio.run(run_evaluation())

Or via CLI:
    uv run python src/eval/run_eval.py
"""

import asyncio
import json
import logging
import os
from dataclasses import dataclass, field
from datetime import datetime, timezone

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
JUDGE_MODEL = "anthropic/claude-3.5-sonnet"

# ---------------------------------------------------------------------------
# Judge prompt — structured rubric for scoring agent responses
# ---------------------------------------------------------------------------

JUDGE_PROMPT = """\
You are an impartial evaluator assessing an AI customer support agent.

## User query
{user_query}

## Agent response
{agent_response}

## Expected tools used (if any)
{expected_tools}

## Scoring rubric (rate each 1–5)
- accuracy: Is the information factually correct and complete?
- helpfulness: Does the response fully address what the user needs?
- tone: Is the response warm, professional, and empathetic?
- tool_usage: Were the right tools called at the right time? (5 = perfect, 1 = wrong/missing tools, N/A if no tools needed → score 5)
- conciseness: Is the response appropriately brief without omitting key information?

## Instructions
- Be strict: a score of 5 means excellent with no room for improvement.
- An overall score of 4+ means the response is acceptable for production.
- Return ONLY valid JSON with no markdown fences.

Return JSON:
{{"accuracy": <1-5>, "helpfulness": <1-5>, "tone": <1-5>, "tool_usage": <1-5>, "conciseness": <1-5>, "overall": <1-5>, "reasoning": "<one or two sentences>"}}
"""


# ---------------------------------------------------------------------------
# Result data classes
# ---------------------------------------------------------------------------


@dataclass
class EvalResult:
    test_case_id: str
    test_case_name: str
    scores: dict[str, int | float]
    overall: int
    reasoning: str
    passed: bool
    keyword_check_passed: bool
    agent_response: str
    tools_called: list[str]
    timestamp: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    def to_dict(self) -> dict:
        return {
            "test_case_id": self.test_case_id,
            "test_case_name": self.test_case_name,
            "scores": self.scores,
            "overall": self.overall,
            "reasoning": self.reasoning,
            "passed": self.passed,
            "keyword_check_passed": self.keyword_check_passed,
            "tools_called": self.tools_called,
            "timestamp": self.timestamp,
        }


@dataclass
class EvalSummary:
    total: int
    passed: int
    failed: int
    pass_rate: float
    avg_overall_score: float
    results: list[EvalResult]
    run_at: str = field(
        default_factory=lambda: datetime.now(tz=timezone.utc).isoformat()
    )

    def print_report(self) -> None:
        bar = "=" * 60
        print(f"\n{bar}")
        print(f"  EVAL REPORT — {self.run_at}")
        print(f"  Pass rate : {self.pass_rate:.0%}  ({self.passed}/{self.total})")
        print(f"  Avg score : {self.avg_overall_score:.2f} / 5.0")
        print(bar)
        for r in self.results:
            icon = "✓" if r.passed else "✗"
            print(
                f"  [{icon}] {r.test_case_id} {r.test_case_name:<45} "
                f"score={r.overall}  kw={'OK' if r.keyword_check_passed else 'FAIL'}"
            )
            if not r.passed:
                print(f"         {r.reasoning}")
        print(bar + "\n")


# ---------------------------------------------------------------------------
# Evaluator
# ---------------------------------------------------------------------------


class LLMJudgeEvaluator:
    """
    Runs each test case through the live agent and scores the response
    using a second LLM call acting as judge.
    """

    def __init__(self, judge_model: str = JUDGE_MODEL) -> None:
        self._client = AsyncOpenAI(
            base_url=OPENROUTER_BASE_URL,
            api_key=os.environ["OPENROUTER_API_KEY"],
            default_headers={"X-Title": "ShopSmart Eval Judge"},
        )
        self._judge_model = judge_model

    async def _collect_agent_response(self, user_input: str) -> tuple[str, list[str]]:
        """Run the agent and return (full_text_response, list_of_tools_called)."""
        from src.agent.runner import run_agent

        text_parts: list[str] = []
        tools_called: list[str] = []

        async for chunk in run_agent(user_input, request_id="eval"):
            if chunk.startswith("\x00TOOL:"):
                tools_called.append(chunk[6:].strip())
            else:
                text_parts.append(chunk)

        return "".join(text_parts).strip(), tools_called

    async def _judge_response(
        self,
        user_query: str,
        agent_response: str,
        expected_tools: list[str],
    ) -> dict:
        """Ask the judge LLM to score the agent response."""
        prompt = JUDGE_PROMPT.format(
            user_query=user_query,
            agent_response=agent_response,
            expected_tools=", ".join(expected_tools) if expected_tools else "none",
        )
        completion = await self._client.chat.completions.create(
            model=self._judge_model,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"},
        )
        return json.loads(completion.choices[0].message.content)

    def _check_keywords(self, response: str, case: dict) -> bool:
        resp_lower = response.lower()
        for kw in case.get("must_contain", []):
            if kw.lower() not in resp_lower:
                return False
        for kw in case.get("must_not_contain", []):
            if kw.lower() in resp_lower:
                return False
        return True

    async def evaluate_case(self, case: dict) -> EvalResult:
        logger.info("Evaluating %s: %s", case["id"], case["name"])

        agent_response, tools_called = await self._collect_agent_response(
            case["user_input"]
        )
        keyword_ok = self._check_keywords(agent_response, case)

        try:
            scores = await self._judge_response(
                case["user_input"], agent_response, case.get("expected_tools", [])
            )
        except Exception as exc:
            logger.error("Judge call failed for %s: %s", case["id"], exc)
            scores = {
                "accuracy": 0,
                "helpfulness": 0,
                "tone": 0,
                "tool_usage": 0,
                "conciseness": 0,
                "overall": 0,
                "reasoning": f"Judge error: {exc}",
            }

        overall = scores.get("overall", 0)
        min_score = case.get("min_score", 4)

        return EvalResult(
            test_case_id=case["id"],
            test_case_name=case["name"],
            scores={k: v for k, v in scores.items() if k != "reasoning"},
            overall=overall,
            reasoning=scores.get("reasoning", ""),
            passed=overall >= min_score and keyword_ok,
            keyword_check_passed=keyword_ok,
            agent_response=agent_response,
            tools_called=tools_called,
        )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


async def run_evaluation(
    case_ids: list[str] | None = None,
    categories: list[str] | None = None,
    concurrency: int = 3,
    output_path: str | None = None,
) -> EvalSummary:
    """
    Run the full evaluation suite (or a filtered subset) and return a summary.

    Args:
        case_ids: Only run cases with these IDs (e.g. ["TC-001", "TC-002"]).
        categories: Only run cases in these categories.
        concurrency: Max parallel evaluations (keep low to avoid rate limits).
        output_path: If set, write JSON results to this file.
    """
    from src.eval.test_cases import EVAL_CASES

    cases = EVAL_CASES
    if case_ids:
        cases = [c for c in cases if c["id"] in case_ids]
    if categories:
        cases = [c for c in cases if c.get("category") in categories]

    evaluator = LLMJudgeEvaluator()
    semaphore = asyncio.Semaphore(concurrency)

    async def bounded_eval(case: dict) -> EvalResult:
        async with semaphore:
            return await evaluator.evaluate_case(case)

    results = await asyncio.gather(*[bounded_eval(c) for c in cases])

    passed = sum(1 for r in results if r.passed)
    avg_score = sum(r.overall for r in results) / len(results) if results else 0.0

    summary = EvalSummary(
        total=len(results),
        passed=passed,
        failed=len(results) - passed,
        pass_rate=passed / len(results) if results else 0.0,
        avg_overall_score=avg_score,
        results=list(results),
    )

    if output_path:
        with open(output_path, "w") as f:
            json.dump(
                {
                    "summary": {
                        "total": summary.total,
                        "passed": summary.passed,
                        "pass_rate": summary.pass_rate,
                        "avg_score": summary.avg_overall_score,
                    },
                    "results": [r.to_dict() for r in results],
                },
                f,
                indent=2,
            )
        logger.info("Results written to %s", output_path)

    return summary
