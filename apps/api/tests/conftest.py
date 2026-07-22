"""Shared test setup.

Forces development mode (so config.validate_production_config() does not fire on
import) and loads the repo-root .env so integration ("live") tests can reach the
real Neon / Neo4j / Gemini services. Unit tests never connect — engine creation is
lazy — so they run with these values present but unused.
"""
import os

os.environ.setdefault("ENVIRONMENT", "development")
os.environ.setdefault("DEBUG", "True")

from dotenv import load_dotenv  # noqa: E402

_REPO_ROOT_ENV = os.path.join(
    os.path.dirname(__file__), "..", "..", "..", ".env"
)
load_dotenv(_REPO_ROOT_ENV)

# Never let a test accidentally run production validation.
os.environ["ENVIRONMENT"] = "development"

import socket  # noqa: E402

import pytest  # noqa: E402


def _host_reachable(host: str, port: int = 443, timeout: float = 3.0) -> bool:
    try:
        socket.getaddrinfo(host, port)
        return True
    except Exception:
        return False


@pytest.fixture(scope="session")
def live_ready():
    """Skip live tests unless a Gemini key is available.

    Phase 6: Neo4j reachability no longer gates anything — the KT pipeline
    runs entirely on Postgres/pgvector.
    """
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    return True
