"""Regexes shared by the voice linter and the fact extractor, plus span masking."""
import re

EMAIL = re.compile(r"[\w.+-]+@[\w-]+(?:\.[\w-]+)+")
DOMAIN = re.compile(r"\b[\w-]+\.(?:com|in|org|net|co\.in)\b", re.I)
# Ten digits, optionally split 5+5, optionally with +91 or a leading 0.
PHONE = re.compile(r"(?<![\w.])(?:\+91[\s-]?|0)?\d{5}[\s-]?\d{5}(?![\w])")
# INV-2026-1004 style ids, and long digit runs such as a 12-digit UTR.
CODE = re.compile(r"\b[A-Z]{2,6}-(?:[A-Z0-9]+-)*\d[A-Z0-9-]*\b|(?<![\w.])\d{11,}(?!\w)")


def spans(pattern: re.Pattern, text: str) -> list[tuple[int, int]]:
    return [m.span() for m in pattern.finditer(text)]


def mask(text: str, spans_: list[tuple[int, int]]) -> str:
    """Blank out the spans with spaces, keeping every other character at its index."""
    chars = list(text)
    for start, end in spans_:
        chars[start:end] = " " * (end - start)
    return "".join(chars)
