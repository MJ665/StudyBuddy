"""Direct Slack alerts for CRITICAL custom events (terminal job failure, scheduler
task failure, health degraded). Complements Sentry's own Slack integration —
this path is for high-signal operational events we always want pushed.

Posts via an Incoming Webhook (``SLACK_WEBHOOK_URL``) on a daemon thread so it
never blocks the request/event loop, and never raises.
"""
import logging
import threading

from config import settings

logger = logging.getLogger("observability.slack")

_EMOJI = {"critical": "🚨", "error": "🔴", "warning": "🟠", "info": "🔵"}


def _post(url: str, payload: dict) -> None:
    try:
        import httpx

        httpx.post(url, json=payload, timeout=5.0)
    except Exception as e:
        logger.warning("Slack alert failed: %s", e)


def post_alert(text: str, level: str = "error", **context) -> None:
    """Fire-and-forget Slack alert. No-op if SLACK_WEBHOOK_URL is unset."""
    url = settings.SLACK_WEBHOOK_URL
    if not url:
        return
    emoji = _EMOJI.get(level, "🔵")
    env = settings.ENVIRONMENT
    lines = [f"{emoji} *StudyBuddy · {level.upper()}* _(env: {env})_", text]
    for k, v in context.items():
        lines.append(f"• *{k}*: `{v}`")
    payload = {"text": "\n".join(lines)}
    threading.Thread(target=_post, args=(url, payload), daemon=True).start()
