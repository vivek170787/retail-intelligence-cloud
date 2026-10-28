"""
Command-line interface for the Promotion Intelligence Agent.
Follows the same conventions as inventory_agent/cli.py and
demand_forecasting_agent/cli.py.

Usage:
    python -m promotion_agent.cli --upcoming
    python -m promotion_agent.cli --upcoming --days-ahead 30
    python -m promotion_agent.cli --sku SKU-APP-0021
    python -m promotion_agent.cli --sku SKU-APP-0021 --assumed-uplift-pct 15
    python -m promotion_agent.cli --risk
    python -m promotion_agent.cli --stockout-risk
    python -m promotion_agent.cli --summary
    python -m promotion_agent.cli --compare                 # all SKUs with promotion history
    python -m promotion_agent.cli --compare SKU-APP-0021       # one SKU
    python -m promotion_agent.cli --readiness
    python -m promotion_agent.cli "Which upcoming promotions have the highest stockout risk?"

With no arguments, starts an interactive question prompt. Natural-language
questions work with or without OPENAI_API_KEY set.
"""

import argparse
import json
import sys

from dotenv import load_dotenv

from promotion_agent.promotion_engine import (
    analyze_promotion_for_sku,
    compare_promotional_and_nonpromotional_sales,
    get_promotion_readiness_report,
    get_promotional_demand_summary,
    get_promotions_with_inventory_risk,
    get_promotion_stockout_risks,
    get_upcoming_promotions,
)
from promotion_agent.llm_explainer import answer_question

_ALL_SKUS = "__ALL__"


def _print_json(data):
    print(json.dumps(data, indent=2, default=str))


def _run_deterministic(args):
    if args.upcoming:
        _print_json(get_upcoming_promotions(days_ahead=args.days_ahead))
    elif args.sku:
        _print_json(analyze_promotion_for_sku(args.sku, assumed_uplift_pct=args.assumed_uplift_pct))
    elif args.risk:
        _print_json(get_promotions_with_inventory_risk(days_ahead=args.days_ahead))
    elif args.stockout_risk:
        _print_json(get_promotion_stockout_risks(days_ahead=args.days_ahead))
    elif args.summary:
        _print_json(get_promotional_demand_summary(days_ahead=args.days_ahead))
    elif args.compare is not None:
        sku = None if args.compare == _ALL_SKUS else args.compare
        _print_json(compare_promotional_and_nonpromotional_sales(sku=sku))
    elif args.readiness:
        _print_json(get_promotion_readiness_report(days_ahead=args.days_ahead, assumed_uplift_pct=args.assumed_uplift_pct))
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
    parser = argparse.ArgumentParser(description="Promotion Intelligence Agent CLI")
    parser.add_argument("question", nargs="?", help="Natural-language question to ask")
    parser.add_argument("--upcoming", action="store_true", help="List upcoming promotions")
    parser.add_argument("--days-ahead", type=int, default=14, metavar="DAYS", help="Lookahead window for --upcoming/--risk/etc. (default: 14)")
    parser.add_argument("--sku", metavar="SKU", help="Full promotion analysis for one SKU")
    parser.add_argument("--assumed-uplift-pct", type=float, default=None, metavar="PCT", help="What-if promotional uplift percentage for --sku/--readiness scenario analysis")
    parser.add_argument("--risk", action="store_true", help="Promotions with inventory risk (insufficient or undeterminable)")
    parser.add_argument("--stockout-risk", action="store_true", help="Promotions with a confirmed stockout risk (insufficient only)")
    parser.add_argument("--summary", action="store_true", help="Catalog-wide promotional demand summary")
    parser.add_argument(
        "--compare", nargs="?", const=_ALL_SKUS, default=None, metavar="SKU",
        help="Compare promotional vs non-promotional sales (all SKUs with history if no SKU given)",
    )
    parser.add_argument("--readiness", action="store_true", help="Full promotion readiness report")
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

    print("Promotion Intelligence Agent -- type a question (or 'quit' to exit).")
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
