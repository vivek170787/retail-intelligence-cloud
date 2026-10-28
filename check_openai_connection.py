"""
Standalone OpenAI API connectivity check.

This is a MANUAL verification script, separate from the pytest suite --
it makes a real network call to OpenAI, so it is never run automatically
by `pytest` or by importing any application module. Run it yourself:

    python check_openai_connection.py           # free: checks auth + model access, no tokens spent
    python check_openai_connection.py --live      # also sends one minimal chat completion (tiny real cost)

It never prints or logs the API key.
"""

import argparse
import sys

from openai_config import get_openai_client, get_openai_model, is_configured


def main():
    parser = argparse.ArgumentParser(description="Check OpenAI API connectivity.")
    parser.add_argument(
        "--live",
        action="store_true",
        help="Also send one minimal chat completion (tiny real cost) to confirm a full round trip, not just auth.",
    )
    args = parser.parse_args()

    if not is_configured():
        print("FAIL: OPENAI_API_KEY is not set.")
        print("Copy .env.example to .env and set a real key, then try again.")
        sys.exit(1)

    model = get_openai_model()
    print(f"Configured model: {model}")

    try:
        client = get_openai_client()
    except RuntimeError as exc:
        print(f"FAIL: {exc}")
        sys.exit(1)

    try:
        client.models.retrieve(model)
        print("PASS: authenticated, and the configured model is accessible (no tokens spent).")
    except Exception as exc:
        print(f"FAIL: could not verify API access -- {type(exc).__name__}: {exc}")
        sys.exit(1)

    if args.live:
        try:
            response = client.chat.completions.create(
                model=model,
                max_tokens=5,
                messages=[{"role": "user", "content": "Reply with exactly: OK"}],
            )
            reply = response.choices[0].message.content
            print(f"PASS: live completion succeeded -- model replied: {reply!r}")
        except Exception as exc:
            print(f"FAIL: live completion failed -- {type(exc).__name__}: {exc}")
            sys.exit(1)


if __name__ == "__main__":
    main()
