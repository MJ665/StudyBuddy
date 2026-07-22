import re


def is_injection(text: str) -> bool:
    """Simple prompt injection detection guardrail."""
    if not text:
        return False
    text = text.lower()
    suspicious_patterns = [
        r"ignore previous",
        r"ignore all",
        r"disregard",
        r"system prompt",
        r"you are now",
        r"dump.*database",
        r"forget everything",
    ]
    for pattern in suspicious_patterns:
        if re.search(pattern, text):
            return True
    return False
