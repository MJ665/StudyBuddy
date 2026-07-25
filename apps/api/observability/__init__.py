"""StudyBuddy observability — a vendor-neutral telemetry facade.

Sentry today, OpenTelemetry when you want (flip ``TELEMETRY_BACKEND``). The app
imports ONLY from here — never sentry_sdk / opentelemetry directly — so swapping
the backend is an env change, not a code change.

    from observability import telemetry, tracing, metrics, slack
    telemetry.init_telemetry(app)            # once, at startup
    with tracing.span("job.ingest", type="kt"):
        metrics.distribution("job.duration", ms, unit="millisecond", type="kt")
    tracing.capture_exception(err, job_id=42)
    slack.post_alert("KT ingest failed 3×", level="critical", job_id=42)
"""
from . import logging_config, metrics, slack, telemetry, tracing

__all__ = ["telemetry", "tracing", "metrics", "slack", "logging_config"]
