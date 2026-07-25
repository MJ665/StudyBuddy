"""Structured logging setup. LOG_FORMAT=json emits one JSON object per line
(ideal for Railway/hosted log aggregation + Sentry Logs); LOG_FORMAT=plain keeps
the human-readable format. LOG_LEVEL controls verbosity. Both env-driven.
"""
import logging
import sys

from config import settings

_PLAIN = "%(asctime)s [%(levelname)s] %(name)s – %(message)s"


def setup() -> None:
    level = getattr(logging, (settings.LOG_LEVEL or "INFO").upper(), logging.INFO)
    handler = logging.StreamHandler(sys.stdout)

    if (settings.LOG_FORMAT or "plain").lower() == "json":
        formatter = _json_formatter()
    else:
        formatter = logging.Formatter(_PLAIN)

    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)
    # Tame noisy libraries a notch above the root level.
    for noisy in ("httpx", "httpcore", "apscheduler", "uvicorn.access"):
        logging.getLogger(noisy).setLevel(max(level, logging.WARNING))


def _json_formatter() -> logging.Formatter:
    # python-json-logger moved the class in 3.x; support both layouts.
    try:
        from pythonjsonlogger.json import JsonFormatter  # v3+
    except Exception:
        try:
            from pythonjsonlogger.jsonlogger import JsonFormatter  # type: ignore  # noqa
        except Exception:
            return logging.Formatter(_PLAIN)
    return JsonFormatter("%(asctime)s %(levelname)s %(name)s %(message)s")
