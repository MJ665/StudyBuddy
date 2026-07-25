"""Vendor-neutral telemetry initialization.

One env var — ``TELEMETRY_BACKEND`` (sentry | otel | none) — decides the whole
stack. Sentry is the default; OpenTelemetry deps are lazy-imported (kept in
requirements-otel.txt) so the default image stays lean and OTel is a true flip.

The rest of the app never imports sentry_sdk / opentelemetry directly — it goes
through this package's facade (``observability.tracing`` / ``.metrics`` /
``.slack``), so switching vendors is a one-line env change, not a rewrite.
"""
import logging

from config import settings

logger = logging.getLogger("observability")

_BACKEND = "none"
# Populated only when backend == "otel": {"tracer":..., "meter":..., "instruments":{}}
_otel: dict = {}


def get_backend() -> str:
    return _BACKEND


def _resolve_backend() -> str:
    b = (settings.TELEMETRY_BACKEND or "sentry").lower()
    if b not in ("sentry", "otel", "none"):
        return "none"
    # A chosen backend with no destination degrades to a silent no-op (dev-safe).
    if b == "sentry" and not settings.SENTRY_DSN:
        return "none"
    if b == "otel" and not settings.OTEL_EXPORTER_OTLP_ENDPOINT:
        return "none"
    return b


def init_telemetry(app=None) -> str:
    """Initialize the active backend. Call once, early, from main.py."""
    global _BACKEND
    _BACKEND = _resolve_backend()
    try:
        if _BACKEND == "sentry":
            _init_sentry()
        elif _BACKEND == "otel":
            _init_otel(app)
        else:
            logger.info("Telemetry disabled (backend=none).")
    except Exception as e:  # telemetry must never take the app down
        logger.warning("Telemetry init failed (%s); continuing without it.", e)
        _BACKEND = "none"
    return _BACKEND


def _init_sentry() -> None:
    import sentry_sdk
    from sentry_sdk.integrations.asyncio import AsyncioIntegration
    from sentry_sdk.integrations.fastapi import FastApiIntegration
    from sentry_sdk.integrations.httpx import HttpxIntegration
    from sentry_sdk.integrations.logging import LoggingIntegration
    from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
    from sentry_sdk.integrations.starlette import StarletteIntegration

    env = settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT
    release = settings.SENTRY_RELEASE or f"studybuddy-api@{settings.APP_VERSION}"
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        environment=env,
        release=release,
        traces_sample_rate=settings.SENTRY_TRACES_SAMPLE_RATE,
        profiles_sample_rate=settings.SENTRY_PROFILES_SAMPLE_RATE,
        send_default_pii=settings.SENTRY_SEND_PII,
        enable_logs=True,  # Sentry structured Logs (SDK >= 2.35)
        integrations=[
            StarletteIntegration(),
            FastApiIntegration(),
            SqlalchemyIntegration(),
            HttpxIntegration(),
            AsyncioIntegration(),
            # Breadcrumbs from INFO+, and ERROR+ logs become Sentry issues.
            LoggingIntegration(level=logging.INFO, event_level=logging.ERROR),
        ],
    )
    sentry_sdk.set_tag("component", "api")
    logger.info("✅ Sentry telemetry enabled (env=%s, release=%s).", env, release)


def _parse_otlp_headers(raw: str | None) -> dict:
    # "key1=val1,key2=val2" → {"key1": "val1", ...}
    out: dict = {}
    for pair in (raw or "").split(","):
        if "=" in pair:
            k, v = pair.split("=", 1)
            out[k.strip()] = v.strip()
    return out


def _init_otel(app=None) -> None:
    from opentelemetry import metrics as otel_metrics
    from opentelemetry import trace
    from opentelemetry.exporter.otlp.proto.http.metric_exporter import (
        OTLPMetricExporter,
    )
    from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter
    from opentelemetry.sdk.metrics import MeterProvider
    from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
    from opentelemetry.sdk.resources import Resource
    from opentelemetry.sdk.trace import TracerProvider
    from opentelemetry.sdk.trace.export import BatchSpanProcessor

    endpoint = (settings.OTEL_EXPORTER_OTLP_ENDPOINT or "").rstrip("/")
    headers = _parse_otlp_headers(settings.OTEL_EXPORTER_OTLP_HEADERS)
    resource = Resource.create(
        {
            "service.name": settings.OTEL_SERVICE_NAME,
            "service.version": settings.APP_VERSION,
            "deployment.environment": settings.ENVIRONMENT,
            "component": "api",
        }
    )

    provider = TracerProvider(resource=resource)
    provider.add_span_processor(
        BatchSpanProcessor(
            OTLPSpanExporter(endpoint=f"{endpoint}/v1/traces", headers=headers)
        )
    )
    trace.set_tracer_provider(provider)

    if settings.OTEL_METRICS_ENABLED:
        reader = PeriodicExportingMetricReader(
            OTLPMetricExporter(endpoint=f"{endpoint}/v1/metrics", headers=headers)
        )
        otel_metrics.set_meter_provider(
            MeterProvider(resource=resource, metric_readers=[reader])
        )

    # Auto-instrument the frameworks — each guarded so a missing extra never crashes.
    try:
        from opentelemetry.instrumentation.fastapi import (  # type: ignore[import]
            FastAPIInstrumentor,
        )

        if app is not None:
            FastAPIInstrumentor.instrument_app(app)
    except Exception as e:
        logger.warning("OTel FastAPI instrumentation skipped: %s", e)
    try:
        from opentelemetry.instrumentation.sqlalchemy import (  # type: ignore[import]
            SQLAlchemyInstrumentor,
        )

        import database

        SQLAlchemyInstrumentor().instrument(engine=database.engine)
        async_engine = getattr(database, "async_engine", None)
        if async_engine is not None:
            SQLAlchemyInstrumentor().instrument(engine=async_engine.sync_engine)
    except Exception as e:
        logger.warning("OTel SQLAlchemy instrumentation skipped: %s", e)
    try:
        from opentelemetry.instrumentation.httpx import (  # type: ignore[import]
            HTTPXClientInstrumentor,
        )

        HTTPXClientInstrumentor().instrument()
    except Exception as e:
        logger.warning("OTel HTTPX instrumentation skipped: %s", e)
    try:
        from opentelemetry.instrumentation.logging import (  # type: ignore[import]
            LoggingInstrumentor,
        )

        LoggingInstrumentor().instrument(set_logging_format=False)
    except Exception as e:
        logger.warning("OTel logging instrumentation skipped: %s", e)

    _otel["tracer"] = trace.get_tracer("studybuddy")
    _otel["meter"] = otel_metrics.get_meter("studybuddy")
    _otel["instruments"] = {}
    logger.info("✅ OpenTelemetry enabled → %s", endpoint)
