"""
Command-line interface for the Order Fulfillment Intelligence Agent.
Follows the same conventions as the other agents' cli.py.

Usage:
    python -m order_fulfillment_agent.cli --at-risk
    python -m order_fulfillment_agent.cli --due-today
    python -m order_fulfillment_agent.cli --shortages
    python -m order_fulfillment_agent.cli --order ORD-000123
    python -m order_fulfillment_agent.cli --alternatives ORD-000123
    python -m order_fulfillment_agent.cli --summary
    python -m order_fulfillment_agent.cli --priorities
    python -m order_fulfillment_agent.cli --priorities --limit 5
    python -m order_fulfillment_agent.cli "Which orders are at risk of missing their promised delivery date?"

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from order_fulfillment_agent.fulfillment_engine import (
    analyze_order_fulfillment,
    find_alternative_fulfillment_options,
    get_fulfillment_priorities,
    get_fulfillment_risk_summary,
    get_orders_at_risk,
    get_orders_due_today,
    get_orders_with_inventory_shortages,
)
from order_fulfillment_agent.llm_explainer import answer_question


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.at_risk:
        _print_json(get_orders_at_risk())
    elif args.due_today:
        _print_json(get_orders_due_today())
    elif args.shortages:
        _print_json(get_orders_with_inventory_shortages())
    elif args.order:
        _print_json(analyze_order_fulfillment(args.order))
    elif args.alternatives:
        _print_json(find_alternative_fulfillment_options(args.alternatives))
    elif args.summary:
        _print_json(get_fulfillment_risk_summary())
    elif args.priorities:
        _print_json(get_fulfillment_priorities(limit=args.limit))
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
    parser = argparse.ArgumentParser(description="Order Fulfillment Intelligence Agent CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument("--at-risk", action="store_true", help="List orders at risk (critical/high/medium/unable_to_assess)")
    parser.add_argument("--due-today", action="store_true", help="List open orders due today or already overdue")
    parser.add_argument("--shortages", action="store_true", help="List open orders with an inventory shortage at their assigned location")
    parser.add_argument("--order", metavar="ORDER_ID", help="Full fulfillment analysis for one order")
    parser.add_argument("--alternatives", metavar="ORDER_ID", help="Alternative fulfillment candidates for one order")
    parser.add_argument("--summary", action="store_true", help="Catalog-wide fulfillment risk summary")
    parser.add_argument("--priorities", action="store_true", help="Top-priority at-risk orders")
    parser.add_argument("--limit", type=int, default=10, metavar="N", help="Limit for --priorities (default: 10)")
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

    print("Order Fulfillment Intelligence Agent -- type a question (or 'quit' to exit).")
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
