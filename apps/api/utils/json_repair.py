import json
import logging
import re

logger = logging.getLogger("json_repair")


def repair_json(raw: str) -> str:
    """
    STRAT-AI-V4: Robust JSON extraction and structural repair.
    1. Extracts the first valid JSON object/array from noisy text.
    2. Balances missing closing braces for truncated responses.
    3. Cleans invalid trailing commas.
    """
    if not raw:
        return "{}"

    # 1. Extraction: Find the start of JSON ([ or {)
    match = re.search(r"[\[\{]", raw)
    if not match:
        return raw

    raw = raw[match.start() :]

    # 2. Structural Balancing (Handle Truncation)
    stack = []
    end_idx = len(raw)

    for i, char in enumerate(raw):
        if char in "[{":
            stack.append(char)
        elif char in "]}":
            if not stack:
                # Malformed: closing bracket without opening
                end_idx = i
                break
            opening = stack.pop()
            if (opening == "[" and char != "]") or (opening == "{" and char != "}"):
                # Mismatched bracket
                end_idx = i
                break

        # If we reach here, char is part of valid-so-far JSON
        if not stack:
            end_idx = i + 1
            break

    # If stack is not empty, it's truncated
    raw = raw[:end_idx]
    while stack:
        opening = stack.pop()
        raw += "]" if opening == "[" else "}"

    # 3. Cleanup: Trailing commas and whitespace
    raw = re.sub(r",\s*([\]\}])", r"\1", raw)

    return raw.strip()


def safe_json_loads(raw: str, fallback=None):
    """Attempt to parse JSON with repair, falling back to provided value."""
    try:
        repaired = repair_json(raw)
        return json.loads(repaired)
    except Exception as e:
        logger.warning(f"JSON Parse Failure after repair: {e}")
        return fallback
