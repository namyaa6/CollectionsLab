"""English number words to integers, including Indian scales (lakh, crore)."""
from typing import Optional

UNITS = {w: i for i, w in enumerate(
    "zero one two three four five six seven eight nine".split())}
TEENS = {w: 10 + i for i, w in enumerate(
    "ten eleven twelve thirteen fourteen fifteen sixteen seventeen eighteen nineteen".split())}
TENS = {w: 10 * (i + 2) for i, w in enumerate(
    "twenty thirty forty fifty sixty seventy eighty ninety".split())}
SCALES = {"thousand": 1_000, "lakh": 100_000, "lakhs": 100_000,
          "crore": 10_000_000, "crores": 10_000_000}
NUMBER_WORDS = set(UNITS) | set(TEENS) | set(TENS) | set(SCALES) | {"hundred"}

# What may follow what inside one group (below a hundred): "sixty five" is fine, "five six" is not.
_BAD_PAIRS = {("unit", "unit"), ("unit", "teen"), ("unit", "tens"), ("teen", "unit"),
              ("teen", "teen"), ("teen", "tens"), ("tens", "tens"), ("tens", "teen")}


def _kind(word: str) -> str:
    if word in UNITS:
        return "unit"
    if word in TEENS:
        return "teen"
    return "tens"


def words_to_int(tokens: list[str]) -> Optional[int]:
    """["sixty", "five", "thousand", "two", "hundred"] -> 65200. None if it makes no sense."""
    total = current = 0
    last: Optional[str] = None  # kind of the previous word within the current group
    seen_any = False
    for raw in tokens:
        w = raw.lower()
        if w == "and":
            continue
        if w == "a" and not seen_any:  # "a hundred", "a thousand"
            current, last, seen_any = 1, "unit", True
            continue
        if w in SCALES:
            total += (current or 1) * SCALES[w]
            current, last = 0, None
        elif w == "hundred":
            if last in ("tens", "teen") or current >= 100:
                return None
            current = (current or 1) * 100
            last = "hundred"
        elif w in UNITS or w in TEENS or w in TENS:
            kind = _kind(w)
            if (last, kind) in _BAD_PAIRS:
                return None
            current += UNITS.get(w) or TEENS.get(w) or TENS.get(w) or 0
            last = kind
        else:
            return None
        seen_any = True
    return total + current if seen_any else None
