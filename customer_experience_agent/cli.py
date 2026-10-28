"""
Command-line interface for the Customer Experience Intelligence Agent.
Follows the same conventions as the other agents' cli.py.

Usage:
    python -m customer_experience_agent.cli --impact-risks
    python -m customer_experience_agent.cli --order ORD-000103
    python -m customer_experience_agent.cli --at-risk
    python -m customer_experience_agent.cli --at-risk --limit 5
    python -m customer_experience_agent.cli --recovery
    python -m customer_experience_agent.cli --summary
    python -m customer_experience_agent.cli "Which orders need attention today?"

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from customer_experience_agent.cx_engine import (
    analyze_customer_order_experience,
    get_at_risk_customer_orders,
    get_customer_experience_summary,
    get_customer_impact_risks,
    get_service_recovery_recommendations,
)
from customer_experience_agent.llm_explainer import answer_question


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.impact_risks:
        _print_json(get_customer_impact_risks())
    elif args.order:
        _print_json(analyze_customer_order_experience(args.order))
    elif args.at_risk:
        _print_json(get_at_risk_customer_orders(limit=args.limit))
    elif args.recovery:
        _print_json(get_service_recovery_recommendations())
    elif args.summary:
        _print_json(get_customer_experience_summary())
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
    parser = argparse.ArgumentParser(description="Customer Experience Intelligence Agent CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument("--impact-risks", action="store_true", help="List all orders with a customer-impacting fulfillment risk")
    parser.add_argument("--order", metavar="ORDER_ID", help="Full customer experience analysis for one order")
    parser.add_argument("--at-risk", action="store_true", help="Top-priority at-risk customer orders")
    parser.add_argument("--limit", type=int, default=10, metavar="N", help="Limit for --at-risk (default: 10)")
    parser.add_argument("--recovery", action="store_true", help="Recommended service recovery actions")
    parser.add_argument("--summary", action="store_true", help="Customer experience summary")
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

    print("Customer Experience Intelligence Agent -- type a question (or 'quit' to exit).")
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
