"""
Command-line interface for the combined orchestration service.
Follows the same conventions as inventory_agent/cli.py and
demand_forecasting_agent/cli.py.

Usage:
    python -m orchestration.cli --analyze                        # all products
    python -m orchestration.cli --analyze SKU-APP-0001             # one SKU
    python -m orchestration.cli --analyze --store ST-001            # all products at one store
    python -m orchestration.cli --analyze SKU-APP-0001 --store ST-001 --horizon 14
    python -m orchestration.cli --query "Which orders have fulfillment risk?"
    python -m orchestration.cli --query "Give me an executive retail summary"
    python -m orchestration.cli "Should we investigate SKU-APP-0001?"

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set. --query routes through
RetailIntelligenceOrchestrator.handle_query() and never needs an API key --
it is purely deterministic business-query routing, distinct from the
positional "question" argument above (which optionally uses an LLM to
explain the --analyze-style evidence).
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from orchestration.service import analyze_inventory_vs_forecast
from orchestration.llm_explainer import answer_question
from orchestration.query_orchestrator import handle_query as handle_retail_query

_ALL_PRODUCTS = "__ALL__"


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.query:
        _print_json(handle_retail_query(args.query, horizon_days=args.horizon, limit=args.limit))
        return True
    if args.analyze is None:
        return False
    sku = None if args.analyze == _ALL_PRODUCTS else args.analyze
    _print_json(analyze_inventory_vs_forecast(sku=sku, horizon_days=args.horizon, store_id=args.store))
    return True


def _ask(question):
    result = answer_question(question)
    if result["configured"]:
        print(result["answer"])
    else:
        print(result["message"])
        print("\nEvidence gathered:")
        _print_json(result["evidence"])


def build_parser():
    parser = argparse.ArgumentParser(description="Retail Orchestration Service CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument(
        "--analyze", nargs="?", const=_ALL_PRODUCTS, default=None, metavar="SKU",
        help="Run combined inventory-vs-forecast analysis (all products if no SKU given)",
    )
    parser.add_argument("--store", metavar="STORE_ID", help="Scope --analyze to one store")
    parser.add_argument(
        "--horizon", type=int, default=7, metavar="DAYS",
        help="Forecast horizon in days (default: 7)",
    )
    parser.add_argument(
        "--query", metavar="TEXT",
        help="Submit a natural-language retail query to RetailIntelligenceOrchestrator "
             "and print the structured combined result (deterministic, no API key needed)",
    )
    parser.add_argument("--limit", type=int, default=10, metavar="N", help="Limit for --query result lists (default: 10)")
    return parser


def main(argv=None):
    load_dotenv()
    args = build_parser().parse_args(argv)

    try:
        if _run_deterministic(args):
            return
        if args.question:
            _ask(args.question)
            return
    except ValueError as exc:
        print(f"Error: {exc}")
        sys.exit(1)

    print("Retail Orchestration Service -- type a question (or 'quit' to exit).")
    while True:
        try:
            question = input("> ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            break
        if not question or question.lower() in {"quit", "exit"}:
            break
        try:
            _ask(question)
        except ValueError as exc:
            print(f"Error: {exc}")


if __name__ == "__main__":
    main()
