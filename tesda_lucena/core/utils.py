import re

PHONE_RE = re.compile(r"^\+?\d{7,15}$")


def normalize_phone(value: str) -> str:
    """Strip spaces, dashes and parentheses from a mobile number."""
    return re.sub(r"[\s\-()]", "", value or "")
