"""Pull the amounts, day counts and dates a speaker says out of free text.

Amounts: digits ("65,200", "Rs 65,200", "2.5 lakh") and number words ("sixty-five thousand
two hundred"). Day counts: "78 days", "sixty days". Dates come from dates.find_dates.
A hit with value None is "unparsed": it looked like a number but could not be evaluated.
"""
import re
from dataclasses import dataclass
from typing import Optional, Union

from backend.eval.dates import DateHit, find_dates
from backend.eval.number_words import NUMBER_WORDS, SCALES, words_to_int
from backend.eval.patterns import CODE, EMAIL, PHONE, mask, spans

Number = Union[int, float]
_MULT = {"lakh": 100_000, "lakhs": 100_000, "thousand": 1_000, "crore": 10_000_000, "k": 1_000}
_NUM = r"(?P<num>\d[\d,]*(?:\.\d+)?)"
_MULT_RE = r"(?P<mult>lakhs?|thousand|crore|k)"
_DIGIT_PATTERNS = [
    re.compile(rf"(?:₹|\$|\b(?:Rs\.?|INR))\s*{_NUM}(?:\s*{_MULT_RE}\b)?", re.I),
    re.compile(rf"{_NUM}\s*(?:{_MULT_RE}\s*)?(?:rupees?|rs|inr)\b", re.I),
    re.compile(rf"{_NUM}\s*{_MULT_RE}\b", re.I),
    re.compile(r"\b(?P<num>\d{1,3}(?:,\d{2,3})+(?:\.\d+)?)\b"),
    re.compile(r"(?<![\d,.])(?P<num>\d{4,})(?![\d,]|\.\d)"),
]
_DAYS_DIGITS = re.compile(r"(?<![\d,.])(?P<num>\d{1,3})[\s-]*days?\b", re.I)
_VAGUE = re.compile(r"\b(?:hundreds?|thousands?|lakhs?|crores?)\s+of\s+rupees|₹(?!\s*\d)", re.I)
_WORD = re.compile(r"[A-Za-z]+")
_CURRENCY_WORDS = {"rupees", "rupee", "rs", "inr"}


@dataclass
class NumHit:
    kind: str  # amount | days
    value: Optional[Number]
    snippet: str
    start: int
    end: int


def _norm(x: float) -> Number:
    return int(x) if float(x).is_integer() else x


def _digits_value(m: re.Match) -> Number:
    value = float(m["num"].replace(",", ""))
    mult = (m.groupdict().get("mult") or "").lower()
    return _norm(value * _MULT.get(mult, 1))


def _word_runs(s: str):
    """Yield (start, end, tokens, next_word, next_end) for each run of number words."""
    words = list(_WORD.finditer(s))
    i = 0
    while i < len(words):
        w = words[i].group(0).lower()
        nxt = words[i + 1].group(0).lower() if i + 1 < len(words) else ""
        starts_run = w in NUMBER_WORDS or (w == "a" and (nxt in SCALES or nxt == "hundred"))
        if not starts_run:
            i += 1
            continue
        j, tokens = i, [w]
        while j + 1 < len(words):
            gap = s[words[j].end():words[j + 1].start()]
            cand = words[j + 1].group(0).lower()
            after = words[j + 2].group(0).lower() if j + 2 < len(words) else ""
            if not re.fullmatch(r"[\s-]+", gap):
                break
            if cand in NUMBER_WORDS or (cand == "and" and after in NUMBER_WORDS):
                tokens.append(cand)
                j += 1
            else:
                break
        follow = words[j + 1] if j + 1 < len(words) else None
        if follow and not re.fullmatch(r"\s+", s[words[j].end():follow.start()]):
            follow = None
        yield (words[i].start(), words[j].end(), tokens,
               follow.group(0).lower() if follow else "", follow.end() if follow else words[j].end())
        i = j + 1


def extract_numbers(text: str) -> list[NumHit]:
    """Amounts and day counts, in order of appearance."""
    s = mask(text, spans(PHONE, text) + spans(EMAIL, text))
    s = mask(s, spans(CODE, s))
    s = mask(s, [(d.start, d.end) for d in find_dates(s)])
    hits: list[NumHit] = []

    def add(kind, value, start, end):
        nonlocal s
        hits.append(NumHit(kind, value, text[start:end].strip(), start, end))
        s = mask(s, [(start, end)])  # later patterns must not count the same digits again

    for m in _VAGUE.finditer(s):
        add("amount", None, *m.span())
    for m in _DAYS_DIGITS.finditer(s):
        add("days", int(m["num"]), *m.span())
    for pat in _DIGIT_PATTERNS:
        for m in pat.finditer(s):
            add("amount", _digits_value(m), *m.span())
    for start, end, tokens, follow, follow_end in _word_runs(s):
        has_scale = any(t in SCALES or t == "hundred" for t in tokens)
        if follow in ("day", "days"):
            kind, end = "days", follow_end
        elif follow in _CURRENCY_WORDS:
            kind, end = "amount", follow_end
        elif has_scale:
            kind = "amount"
        else:
            continue
        add(kind, words_to_int(tokens), start, end)
    return sorted(hits, key=lambda h: h.start)


def extract_dates(text: str) -> list[DateHit]:
    s = mask(text, spans(PHONE, text) + spans(EMAIL, text))
    return find_dates(mask(s, spans(CODE, s)))
