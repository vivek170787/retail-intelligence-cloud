"""
Command-line interface for the Inventory Intelligence Agent.

Usage:
    python -m inventory_agent.cli "Which products are at risk of stockout?"
    python -m inventory_agent.cli --summary
    python -m inventory_agent.cli --product SKU-ELE-0008
    python -m inventory_agent.cli --store ST-001
    python -m inventory_agent.cli --store            (all stores)
    python -m inventory_agent.cli --replenish
    python -m inventory_agent.cli --top 5

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set -- without it, the raw
deterministic evidence is printed instead of an LLM explanation.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from inventory_agent.llm_explainer import answer_question
from inventory_agent.risk_engine import (
    get_inventory_summary,
    get_product_inventory_analysis,
    get_replenishment_recommendations,
    get_store_inventory_risks,
    get_top_stockout_risks,
)


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.summary:
        _print_json(get_inventory_summary())
    elif args.product:
        _print_json(get_product_inventory_analysis(args.product))
    elif args.store is not None:
        _print_json(get_store_inventory_risks(store_id=args.store or None))
    elif args.replenish:
        _print_json(get_replenishment_recommendations())
    elif args.top is not None:
        _print_json(get_top_stockout_risks(limit=args.top))
    else:
        return False
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
    parser = argparse.ArgumentParser(description="Inventory Intelligence Agent CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument("--summary", action="store_true", help="Print the deterministic inventory summary")
    parser.add_argument("--product", metavar="SKU", help="Print the deterministic analysis for one SKU")
    parser.add_argument(
        "--store", metavar="STORE_ID", nargs="?", const="",
        help="Print store-level inventory shortages (all stores if no ID given)",
    )
    parser.add_argument("--replenish", action="store_true", help="Print replenishment recommendations")
    parser.add_argument(
        "--top", type=int, nargs="?", const=10, metavar="N",
        help="Print the top N stockout risks (default 10)",
    )
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

    print("Inventory Intelligence Agent -- type a question (or 'quit' to exit).")
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
