"""
Langfuse tracing initialisation.

Langfuse v4 is OpenTelemetry-based and gracefully self-disables when
LANGFUSE_PUBLIC_KEY / LANGFUSE_SECRET_KEY are absent — no special
mocking is needed in tests or local dev without credentials.

Usage (at app startup):
    from src.tracing import setup_tracing
    setup_tracing()

Usage inside a function:
    from langfuse import get_client
    lf = get_client()
    with lf.start_as_current_observation(name="my-span", as_type="span"):
        ...
"""

import logging
import os

logger = logging.getLogger(__name__)


def setup_tracing() -> bool:
    """
    Log whether Langfuse tracing is active.
    Returns True if credentials are present and tracing is enabled.
    """
    public_key = os.getenv("LANGFUSE_PUBLIC_KEY")
    secret_key = os.getenv("LANGFUSE_SECRET_KEY")

    if public_key and secret_key:
        host = os.getenv("LANGFUSE_HOST", "https://cloud.langfuse.com")
        logger.info("Langfuse tracing enabled | host=%s", host)
        return True

    logger.info(
        "Langfuse tracing disabled — set LANGFUSE_PUBLIC_KEY + LANGFUSE_SECRET_KEY to enable"
    )
    return False
