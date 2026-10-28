"""
CLI entry point for the retail data assistant.

WARNING: running this script makes a real, billed call to the OpenAI API
and requires a real OPENAI_API_KEY (see .env.example). Do not run this
automatically -- it is a manual, user-initiated verification step.

Usage:
    python -m retail_agent.runner "What's the current inventory for SKU-APP-0001?"
"""

import asyncio
import os
import sys

from dotenv import load_dotenv

from agents import Runner, SQLiteSession

from retail_agent.agent import retail_agent


async def main(user_message: str) -> None:
    if not os.getenv("OPENAI_API_KEY"):
        print(
            "ERROR: OPENAI_API_KEY is not set.\n"
            "Copy .env.example to .env and fill in a real key before running this script."
        )
        sys.exit(1)

    session = SQLiteSession("retail-agent-session", "conversations.db")
    result = await Runner.run(retail_agent, user_message, session=session)
    print(result.final_output)


if __name__ == "__main__":
    load_dotenv()
    if len(sys.argv) < 2:
        print('Usage: python -m retail_agent.runner "<your question>"')
        sys.exit(1)
    asyncio.run(main(" ".join(sys.argv[1:])))
