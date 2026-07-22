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
    """Skip live tests unless Gemini key + Neo4j host are available."""
    if not os.environ.get("GEMINI_API_KEY"):
        pytest.skip("GEMINI_API_KEY not set")
    instance = os.environ.get("NEO4J_INSTANCE")
    uri = os.environ.get("NEO4J_URI")
    host = None
    if uri and "://" in uri:
        host = uri.split("://", 1)[1].split(":")[0].split("/")[0]
    elif instance:
        host = f"{instance}.databases.neo4j.io"
    if not host or not _host_reachable(host):
        pytest.skip(f"Neo4j host unreachable ({host}) — instance paused/deleted?")
    return True
