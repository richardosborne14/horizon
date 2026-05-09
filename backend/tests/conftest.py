"""
Pytest configuration for all backend tests.

WHY session-scoped event loop: asyncpg connections are tied to the event loop
they were created on. The FastAPI app's DB engine is a module-level singleton —
its connection pool holds asyncpg connections from the first test's loop. With
function-scoped loops (the default), subsequent tests get a NEW loop and the
pool's OLD connections fail with "Future attached to a different loop".

Solution: use ONE event loop for the entire pytest session so the pool's
connections stay valid across all tests.

This must be in conftest.py (not pytest.ini) because it requires a fixture.
See LEARNINGS.md: "asyncpg + pytest: use session-scoped event loop"
"""

import asyncio
import pytest


@pytest.fixture(scope="session")
def event_loop():
    """
    Session-scoped event loop.

    Shared by all async tests in the session. Prevents asyncpg
    "Future attached to a different loop" errors when the FastAPI
    app's DB engine pool holds connections across test function boundaries.
    """
    policy = asyncio.get_event_loop_policy()
    loop = policy.new_event_loop()
    yield loop
    loop.close()
