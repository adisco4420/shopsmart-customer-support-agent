"""
CLI script to run the evaluation suite.

Examples:
    # Run all test cases
    uv run python src/eval/run_eval.py

    # Run a specific category
    uv run python src/eval/run_eval.py --category order_tracking returns

    # Run specific cases and save results
    uv run python src/eval/run_eval.py --cases TC-001 TC-002 --output results.json
"""

import argparse
import asyncio
import logging
import sys

from dotenv import load_dotenv

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")


async def main() -> int:
    parser = argparse.ArgumentParser(description="Run ShopSmart agent evaluation suite")
    parser.add_argument("--cases", nargs="+", help="Specific case IDs to run")
    parser.add_argument("--category", nargs="+", help="Filter by category")
    parser.add_argument("--output", help="JSON file path for results")
    parser.add_argument("--concurrency", type=int, default=2, help="Parallel evaluations")
    args = parser.parse_args()

    from src.eval.evaluator import run_evaluation

    summary = await run_evaluation(
        case_ids=args.cases,
        categories=args.category,
        concurrency=args.concurrency,
        output_path=args.output,
    )

    summary.print_report()
    return 0 if summary.pass_rate >= 0.8 else 1


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
