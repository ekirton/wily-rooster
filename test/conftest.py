"""Root test configuration — shared across all test tiers."""

from __future__ import annotations

import asyncio

import pytest


# ---------------------------------------------------------------------------
# Event loop policy — ensure asyncio.get_event_loop() works in sync tests
# that call run_until_complete() (e.g., compatibility analysis tests).
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _ensure_event_loop():
    """Ensure an event loop exists for sync tests using get_event_loop()."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            raise RuntimeError("closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
    yield
