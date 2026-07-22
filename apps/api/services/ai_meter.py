"""AI usage metering — records tokens + estimated cost for every Gemini call.

Design:
- Per-request org/user are held in contextvars, set by a middleware that decodes
  the JWT (see main.py). AI calls deep in the service layer therefore attribute
  cost to the right tenant without threading org_id through every signature.
- Recording is best-effort: any failure is logged and swallowed so it can never
  break the underlying AI feature.
- Prices are coarse public estimates (USD per 1M tokens); adjust in PRICING.
"""
import contextvars
import logging

logger = logging.getLogger("ai.meter")

# USD per 1,000,000 tokens (input, output). Estimates — tune to your billing.
PRICING: dict[str, tuple[float, float]] = {
    "gemini-2.5-flash": (0.30, 2.50),
    "gemini-2.0-flash": (0.10, 0.40),
    "gemini-embedding-001": (0.15, 0.0),
}
_DEFAULT_PRICE = (0.30, 2.50)

_org_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar("ai_org", default=None)
_user_ctx: contextvars.ContextVar[int | None] = contextvars.ContextVar("ai_user", default=None)


def set_request_context(org_id: int | None, user_id: int | None) -> None:
    _org_ctx.set(org_id)
    _user_ctx.set(user_id)


def clear_request_context() -> None:
    _org_ctx.set(None)
    _user_ctx.set(None)


def _estimate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    in_rate, out_rate = PRICING.get(model, _DEFAULT_PRICE)
    return round(
        (input_tokens / 1_000_000) * in_rate + (output_tokens / 1_000_000) * out_rate, 6
    )


def extract_tokens(response) -> tuple[int, int]:
    """Pull (input_tokens, output_tokens) from a google-genai response, if present."""
    try:
        um = getattr(response, "usage_metadata", None)
        if um is None:
            return 0, 0
        inp = getattr(um, "prompt_token_count", 0) or 0
        out = getattr(um, "candidates_token_count", 0) or 0
        return int(inp), int(out)
    except Exception:  # noqa: BLE001
        return 0, 0


async def record(
    feature: str,
    model: str,
    input_tokens: int,
    output_tokens: int,
    org_id: int | None = None,
    user_id: int | None = None,
) -> None:
    """Persist one usage row. Best-effort; never raises."""
    try:
        from database import db_session_factory
        from models.ai_usage import AIUsage

        oid = org_id if org_id is not None else _org_ctx.get()
        uid = user_id if user_id is not None else _user_ctx.get()
        async with db_session_factory() as db:
            db.add(
                AIUsage(
                    organization_id=oid,
                    user_id=uid,
                    feature=feature,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    est_cost_usd=_estimate_cost(model, input_tokens, output_tokens),
                )
            )
            await db.commit()
    except Exception as e:  # noqa: BLE001
        logger.warning("ai_meter.record failed (%s/%s): %s", feature, model, e)


async def record_response(feature: str, model: str, response) -> None:
    """Convenience: extract tokens from a genai response and record."""
    inp, out = extract_tokens(response)
    await record(feature, model, inp, out)
