"""Vendor-neutral tracing + error-capture facade.

Every hotspot calls these; the active backend (set by ``init_telemetry``) decides
where spans/exceptions go. All calls are no-ops when backend == "none", so the
app is untouched in dev / when telemetry is off.
"""
import contextlib
import logging

from .telemetry import _otel, get_backend

logger = logging.getLogger("observability.tracing")


def _safe(value):
    if isinstance(value, (str, bool, int, float)) or value is None:
        return value
    return str(value)


@contextlib.contextmanager
def span(name: str, op: str = "function", **attrs):
    """Open a span/transaction child around a unit of work."""
    backend = get_backend()
    if backend == "sentry":
        import sentry_sdk

        with sentry_sdk.start_span(op=op, name=name) as s:
            for k, v in attrs.items():
                try:
                    s.set_data(k, _safe(v))
                except Exception:
                    pass
            yield s
        return
    if backend == "otel":
        tracer = _otel.get("tracer")
        if tracer is not None:
            with tracer.start_as_current_span(name) as s:
                for k, v in attrs.items():
                    try:
                        s.set_attribute(k, _safe(v))
                    except Exception:
                        pass
                yield s
            return
    yield None


def capture_exception(exc: BaseException | None = None, **context) -> None:
    """Report an exception with optional structured context (best-effort)."""
    backend = get_backend()
    try:
        if backend == "sentry":
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                for k, v in context.items():
                    scope.set_extra(k, _safe(v))
                sentry_sdk.capture_exception(exc)
        elif backend == "otel":
            from opentelemetry import trace

            cur = trace.get_current_span()
            if cur is not None and exc is not None:
                attrs = {k: _safe(v) for k, v in context.items() if v is not None}
                cur.record_exception(exc, attributes=attrs)  # type: ignore[arg-type]
    except Exception as e:
        logger.debug("capture_exception failed: %s", e)


def capture_message(message: str, level: str = "info", **context) -> None:
    backend = get_backend()
    try:
        if backend == "sentry":
            import sentry_sdk

            with sentry_sdk.new_scope() as scope:
                for k, v in context.items():
                    scope.set_extra(k, _safe(v))
                sentry_sdk.capture_message(message, level=level)  # type: ignore[arg-type]
    except Exception as e:
        logger.debug("capture_message failed: %s", e)


def set_user_org(user_id=None, org_id=None) -> None:
    """Attach the caller's identity to the current scope for triage."""
    if get_backend() != "sentry":
        return
    try:
        import sentry_sdk

        if user_id is not None:
            sentry_sdk.set_user({"id": str(user_id)})
        if org_id is not None:
            sentry_sdk.set_tag("org_id", str(org_id))
    except Exception:
        pass


def add_breadcrumb(category: str, message: str, level: str = "info", **data) -> None:
    if get_backend() != "sentry":
        return
    try:
        import sentry_sdk

        sentry_sdk.add_breadcrumb(
            category=category,
            message=message,
            level=level,
            data={k: _safe(v) for k, v in data.items()},
        )
    except Exception:
        pass
