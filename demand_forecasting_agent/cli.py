"""
Command-line interface for the Demand Forecasting Agent.
Follows the same conventions as inventory_agent/cli.py.

Usage:
    python -m demand_forecasting_agent.cli --forecast SKU-APP-0001
    python -m demand_forecasting_agent.cli --forecast SKU-APP-0001 --horizon 14 --store ST-001
    python -m demand_forecasting_agent.cli --top
    python -m demand_forecasting_agent.cli --top 5 --horizon 14
    python -m demand_forecasting_agent.cli --spikes
    python -m demand_forecasting_agent.cli --declines
    python -m demand_forecasting_agent.cli --compare SKU-APP-0001
    python -m demand_forecasting_agent.cli --evaluate SKU-APP-0001
    python -m demand_forecasting_agent.cli --summary

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set -- without it, the raw
deterministic evidence is printed instead of an LLM explanation.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from demand_forecasting_agent.forecasting_engine import (
    compare_forecast_with_inventory,
    detect_declining_demand,
    detect_demand_spikes,
    evaluate_forecast,
    forecast_demand,
    get_demand_summary,
    get_top_forecasted_products,
)
from demand_forecasting_agent.llm_explainer import answer_question


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.summary:
        _print_json(get_demand_summary())
    elif args.forecast:
        _print_json(forecast_demand(args.forecast, horizon_days=args.horizon, store_id=args.store))
    elif args.top is not None:
        _print_json(get_top_forecasted_products(horizon_days=args.horizon, limit=args.top))
    elif args.spikes:
        _print_json(detect_demand_spikes())
    elif args.declines:
        _print_json(detect_declining_demand())
    elif args.compare:
        _print_json(compare_forecast_with_inventory(args.compare, horizon_days=args.horizon))
    elif args.evaluate:
        _print_json(evaluate_forecast(args.evaluate, store_id=args.store))
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
    parser = argparse.ArgumentParser(description="Demand Forecasting Agent CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument("--summary", action="store_true", help="Print the catalog-wide demand summary")
    parser.add_argument("--forecast", metavar="SKU", help="Forecast demand for one SKU")
    parser.add_argument("--store", metavar="STORE_ID", help="Scope --forecast/--evaluate to one store")
    parser.add_argument(
        "--horizon", type=int, default=None, metavar="DAYS",
        help="Forecast horizon in days (default: 7)",
    )
    parser.add_argument(
        "--top", type=int, nargs="?", const=10, metavar="N",
        help="Print the top N forecasted products (default 10)",
    )
    parser.add_argument("--spikes", action="store_true", help="Detect demand spikes across the catalog")
    parser.add_argument("--declines", action="store_true", help="Detect declining demand across the catalog")
    parser.add_argument("--compare", metavar="SKU", help="Compare forecast demand with current inventory for one SKU")
    parser.add_argument("--evaluate", metavar="SKU", help="Run a time-based backtest evaluation for one SKU")
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

    print("Demand Forecasting Agent -- type a question (or 'quit' to exit).")
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
