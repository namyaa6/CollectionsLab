"""Voice linter: is the AGENT's spoken text fit for text-to-speech?

Each lint_* function takes (turn_index, text) and returns Violations for one category.
Run on a whole transcript with lint_transcript().
"""
import re
from collections import Counter

from backend.eval.dates import find_dates
from backend.eval.models import Violation
from backend.eval.patterns import CODE, DOMAIN, EMAIL, PHONE, mask, spans
from backend.sim.transcript import Transcript

MAX_SENTENCES = 2
CATEGORIES = ("symbols_markdown", "long_turn", "digit_amount", "numeric_date",
              "code_token", "unspelled_contact")


def _snip(text: str, start: int, end: int, pad: int = 12) -> str:
    return text[max(0, start - pad):end + pad].replace("\n", " ").strip()


def _violations(turn: int, category: str, text: str, pattern: re.Pattern) -> list[Violation]:
    return [Violation(turn=turn, category=category, snippet=_snip(text, *m.span()))
            for m in pattern.finditer(text)]


# --- symbols_markdown -------------------------------------------------------
_EMOJI = "\U0001F300-\U0001FAFF☀-➿⭐️‍"
_SYMBOLS = re.compile(
    rf"[₹$€£*#`%•▪◦‣●_{_EMOJI}]"          # currency, markdown marks, percent, bullets, emoji
    r"|(?<!\d)/|/(?!\d)"                 # slash, except between digits (that is a numeric date)
    r"|^\s*[-–—]\s"                      # "- item"
    r"|^\s*\d+[.)]\s"                    # "1. item"
    r"|\[[^\]]+\]\([^)]+\)",             # [text](link)
    re.M)


def lint_symbols_markdown(turn: int, text: str) -> list[Violation]:
    return _violations(turn, "symbols_markdown", text, _SYMBOLS)


# --- long_turn --------------------------------------------------------------
_ABBREV = re.compile(r"\b(Mr|Mrs|Ms|Dr|Sr|Jr|St|Prof|Rs)\.")
_SENTENCE_END = re.compile(r"(?<=[.!?])[\"')\]]*\s+(?=\S)")


def count_sentences(text: str) -> int:
    t = _ABBREV.sub(lambda m: m.group(1) + "\u0000", text.strip())
    t = re.sub(r"(?<=\d)\.(?=\d)", "\u0000", t)  # decimals
    t = re.sub(r"\.{2,}", ".", t)
    parts = _SENTENCE_END.split(t)
    return sum(1 for p in parts if re.search(r"\w", p))


def lint_long_turn(turn: int, text: str) -> list[Violation]:
    n, paragraphs = count_sentences(text), len(re.split(r"\n\s*\n", text.strip()))
    if n <= MAX_SENTENCES and paragraphs <= 1:
        return []
    reason = f"{n} sentences" + (f", {paragraphs} paragraphs" if paragraphs > 1 else "")
    return [Violation(turn=turn, category="long_turn", snippet=f"{reason}: {text.strip()[:50]}")]


# --- masking helpers: what each digit check must not look at -----------------
def _other_tokens_masked(text: str, *, keep_dates: bool = False) -> str:
    """Blank out contacts, codes and (unless keep_dates) every date, so checks don't overlap."""
    s = mask(text, spans(PHONE, text) + spans(EMAIL, text))
    s = mask(s, spans(CODE, s))
    if not keep_dates:
        s = mask(s, [(h.start, h.end) for h in find_dates(s)])
    return s


# --- digit_amount -----------------------------------------------------------
_NUM = r"\d[\d,]*(?:\.\d+)?"
_AMOUNT = re.compile(
    rf"(?:₹|\$|\b(?:Rs\.?|INR))\s*{_NUM}"                                # ₹65,200  Rs 500
    rf"|{_NUM}\s*(?:lakhs?|thousand|crore|k)?\s*(?:rupees?|rs|inr)\b"  # 500 rupees
    rf"|{_NUM}\s*(?:lakhs?|thousand|crore)\b"                         # 2.5 lakh
    r"|\b\d{1,3}(?:,\d{2,3})+(?:\.\d+)?\b"                            # 65,200
    r"|(?<![\d,.])\d{4,}(?![\d,]|\.\d)", re.I)
_YEAR_ONLY = re.compile(r"(?:19|20)\d{2}")


def lint_digit_amount(turn: int, text: str) -> list[Violation]:
    s = _other_tokens_masked(text)
    out = []
    for m in _AMOUNT.finditer(s):
        if _YEAR_ONLY.fullmatch(m.group(0)):  # a stray year is not an amount
            continue
        out.append(Violation(turn=turn, category="digit_amount", snippet=_snip(text, *m.span())))
    return out


# --- numeric_date -----------------------------------------------------------
def lint_numeric_date(turn: int, text: str) -> list[Violation]:
    s = _other_tokens_masked(text, keep_dates=True)
    return [Violation(turn=turn, category="numeric_date", snippet=_snip(text, h.start, h.end))
            for h in find_dates(s) if h.kind == "numeric"]


# --- code_token -------------------------------------------------------------
def lint_code_token(turn: int, text: str) -> list[Violation]:
    s = mask(text, spans(PHONE, text) + spans(EMAIL, text))
    return _violations(turn, "code_token", s, CODE)


# --- unspelled_contact ------------------------------------------------------
def lint_unspelled_contact(turn: int, text: str) -> list[Violation]:
    found = [m.span() for p in (EMAIL, PHONE) for m in p.finditer(text)]
    rest = mask(text, found)
    found += spans(DOMAIN, rest)
    return [Violation(turn=turn, category="unspelled_contact", snippet=_snip(text, s, e))
            for s, e in sorted(found)]


LINTERS = {
    "symbols_markdown": lint_symbols_markdown, "long_turn": lint_long_turn,
    "digit_amount": lint_digit_amount, "numeric_date": lint_numeric_date,
    "code_token": lint_code_token, "unspelled_contact": lint_unspelled_contact,
}


def lint_transcript(t: Transcript) -> list[Violation]:
    out: list[Violation] = []
    for i, turn in enumerate(t.turns):
        if turn.speaker != "agent" or not turn.text.strip():
            continue
        for fn in LINTERS.values():
            out += fn(i, turn.text)
    return out


def count_by_category(violations: list[Violation]) -> dict[str, int]:
    counts = Counter(v.category for v in violations)
    return {c: counts.get(c, 0) for c in CATEGORIES}
