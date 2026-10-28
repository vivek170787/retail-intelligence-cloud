"""
Shared OpenAI SDK configuration for this project.

Centralizes reading OPENAI_API_KEY / OPENAI_MODEL from the environment
(loaded from .env via python-dotenv) and constructing a single, reused
OpenAI client, so individual agents don't each build their own client or
duplicate credential-handling logic.

Importing this module makes NO network call and never prints or logs the
API key. The client is constructed lazily -- only when get_openai_client()
is first called -- so simply importing this module (e.g. at application
startup) never talks to the OpenAI API.
"""

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()

DEFAULT_MODEL = "gpt-5.6-luna"


def get_openai_api_key():
    """Return the configured API key, or None if it isn't set. Never logged."""
    return os.getenv("OPENAI_API_KEY") or None


def is_configured():
    """True if an OpenAI API key is present in the environment/.env file."""
    return get_openai_api_key() is not None


def get_openai_model():
    """Return the configured model name (OPENAI_MODEL), or DEFAULT_MODEL."""
    return os.getenv("OPENAI_MODEL", DEFAULT_MODEL)


@lru_cache(maxsize=1)
def get_openai_client():
    """Return a single, shared, lazily-constructed OpenAI client.

    Raises RuntimeError with a clear message if OPENAI_API_KEY is not set,
    rather than returning a client that would fail confusingly later. The
    @lru_cache means every caller across the project gets the same client
    instance instead of each constructing its own.
    """
    api_key = get_openai_api_key()
    if not api_key:
        raise RuntimeError(
            "OPENAI_API_KEY is not set. Copy .env.example to .env and set a "
            "real API key before calling get_openai_client()."
        )
    from openai import OpenAI
    return OpenAI(api_key=api_key)
