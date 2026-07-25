"""Vendor-neutral metrics facade.

Sentry retired custom/DDM metrics, so under ``sentry`` a metric is recorded as
(a) data on the current span/transaction and (b) a structured Sentry Log — both
queryable and alertable. Under ``otel`` the same call drives a real OpenTelemetry
instrument exported over OTLP. Under ``none`` it's a no-op.

Because the call sites are identical, switching backends needs no code change.
"""
import logging

from .telemetry import _otel, get_backend

logger = logging.getLogger("observability.metrics")


def _sentry_record(name: str, value: float, unit: str, tags: dict) -> None:
    try:
        import sentry_sdk

        span = sentry_sdk.get_current_span()
        if span is not None:
            span.set_data(f"metric.{name}", value)
        # Structured Sentry Log — shows in the Logs view, filterable by attributes.
        sentry_logger = getattr(sentry_sdk, "logger", None)
        try:
            if sentry_logger is None:
                raise AttributeError("sentry logs unavailable")
            sentry_logger.info(
                "metric %s=%s%s",
                name,
                value,
                unit if unit and unit != "none" else "",
                attributes={"metric": name, "value": value, "unit": unit, **tags},
            )
        except Exception:
            # Older SDKs: fall back to a breadcrumb (attaches to the next event).
            sentry_sdk.add_breadcrumb(
                category="metric", message=name,
                data={"value": value, "unit": unit, **tags}, level="info",
            )
    except Exception as e:
        logger.debug("sentry metric failed: %s", e)


def _otel_instrument(kind: str, name: str, unit: str):
    cache = _otel.get("instruments", {})
    key = (kind, name)
    if key in cache:
        return cache[key]
    meter = _otel.get("meter")
    if meter is None:
        return None
    if kind == "counter":
        inst = meter.create_counter(name, unit=unit)
    elif kind == "gauge":
        inst = meter.create_gauge(name, unit=unit)
    else:
        inst = meter.create_histogram(name, unit=unit)
    cache[key] = inst
    return inst


def counter(name: str, value: float = 1, unit: str = "none", **tags) -> None:
    b = get_backend()
    if b == "sentry":
        _sentry_record(name, value, unit, tags)
    elif b == "otel":
        try:
            inst = _otel_instrument("counter", name, unit)
            if inst is not None:
                inst.add(value, tags)
        except Exception as e:
            logger.debug("otel counter failed: %s", e)


def distribution(name: str, value: float, unit: str = "millisecond", **tags) -> None:
    b = get_backend()
    if b == "sentry":
        _sentry_record(name, value, unit, tags)
    elif b == "otel":
        try:
            inst = _otel_instrument("histogram", name, unit)
            if inst is not None:
                inst.record(value, tags)
        except Exception as e:
            logger.debug("otel histogram failed: %s", e)


def gauge(name: str, value: float, unit: str = "none", **tags) -> None:
    b = get_backend()
    if b == "sentry":
        _sentry_record(name, value, unit, tags)
    elif b == "otel":
        try:
            inst = _otel_instrument("gauge", name, unit)
            if inst is not None:
                inst.set(value, tags)
        except Exception as e:
            logger.debug("otel gauge failed: %s", e)
