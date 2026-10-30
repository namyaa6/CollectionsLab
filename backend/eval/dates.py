"""Find dates in spoken or written text: numeric, written ("November 10th, 2026"), day-only ("the tenth").

Shared by the voice linter (to mask dates and flag numeric ones) and the fact checker.
"""
import calendar
import re
from dataclasses import dataclass
from typing import Optional

from backend.scenarios.generator import SIM_DATE

MONTHS = {m.lower(): i for i, m in enumerate(calendar.month_name) if m}
MONTHS.update({m.lower(): i for i, m in enumerate(calendar.month_abbr) if m})
MONTHS["sept"] = 9

_ORD_WORDS = ("first second third fourth fifth sixth seventh eighth ninth tenth eleventh twelfth "
              "thirteenth fourteenth fifteenth sixteenth seventeenth eighteenth nineteenth "
              "twentieth").split()
ORDINALS = {w: i + 1 for i, w in enumerate(_ORD_WORDS)}
ORDINALS.update({"thirtieth": 30})
for _tens, _base in (("twenty", 20), ("thirty", 30)):
    for _w, _n in list(ORDINALS.items())[:9]:
        ORDINALS[f"{_tens}-{_w}"] = ORDINALS[f"{_tens} {_w}"] = _base + _n
ORDINALS = {k: v for k, v in ORDINALS.items() if v <= 31}

_MONTH = r"(?P<mon>" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b\.?"
_ORD_W = "|".join(sorted(ORDINALS, key=len, reverse=True))
_DAY = r"(?:(?P<dnum>\d{1,2})(?:st|nd|rd|th)?(?!\d)|(?P<dword>" + _ORD_W + r"))"
_YEAR = r"(?P<year>(?:19|20)\d{2})(?!\d)"

# Order matters: longer, more specific shapes first.
_WRITTEN = [
    re.compile(rf"\b(?:the\s+)?{_DAY}\b(?:\s+of)?\s+{_MONTH}(?:,?\s+{_YEAR})?", re.I),   # 10th of November 2026
    re.compile(rf"\b{_MONTH}\s+(?:the\s+)?{_DAY}\b(?:,?\s+{_YEAR})?", re.I),            # November 10th, 2026
]
_THIS_NEXT = re.compile(r"\s+of\s+(?P<rel>this|next)\s+month\b", re.I)
_DAY_ONLY = re.compile(
    rf"\b(?:the\s+(?P<dnum1>\d{{1,2}})(?:st|nd|rd|th)|(?P<dnum2>\d{{1,2}})(?:st|nd|rd|th)"
    rf"|the\s+(?P<dword>{_ORD_W}))\b", re.I)
_ISO = re.compile(r"(?<![\d-])(?P<y>\d{4})-(?P<m>\d{2})-(?P<d>\d{2})(?![\d-])")
_DMY = re.compile(r"(?<![\d./-])(?P<a>\d{1,2})[/.-](?P<b>\d{1,2})[/.-](?P<y>\d{4}|\d{2})(?![\d/-])")
_DM = re.compile(r"(?<![\d./-])(?P<a>\d{1,2})/(?P<b>\d{1,2})(?![\d/])")


@dataclass
class DateHit:
    kind: str  # numeric | written | day_only
    start: int
    end: int
    snippet: str
    day: Optional[int] = None
    month: Optional[int] = None
    year: Optional[int] = None
    valid: bool = True  # False: looks like a date but cannot be one (31/02)

    def label(self) -> str:
        y = f"{self.year:04d}" if self.year else "-"
        m = f"{self.month:02d}" if self.month else "-"
        d = f"{self.day:02d}" if self.day else "-"
        return f"{y}-{m}-{d}"


def _valid(day: int, month: int, year: Optional[int]) -> bool:
    if not 1 <= month <= 12 or day < 1:
        return False
    return day <= calendar.monthrange(year or 2028, month)[1]  # 2028: leap year, no year given


def _numeric(a: int, b: int, year: Optional[int]) -> tuple[int, int, bool]:
    """Day-first (Indian) reading, month-first only if day-first is impossible."""
    if _valid(a, b, year):
        return a, b, True
    if _valid(b, a, year):
        return b, a, True
    return a, b, False


def _hit(kind: str, m: re.Match, day, month, year) -> DateHit:
    ok = _valid(day, month, year) if month else 1 <= day <= 31
    return DateHit(kind, m.start(), m.end(), m.group(0).strip(), day, month, year, ok)


def find_dates(text: str) -> list[DateHit]:
    hits: list[DateHit] = []
    taken: list[tuple[int, int]] = []

    def free(m: re.Match) -> bool:
        return not any(m.start() < e and s < m.end() for s, e in taken)

    def add(h: DateHit) -> None:
        hits.append(h)
        taken.append((h.start, h.end))

    for m in _ISO.finditer(text):
        y, mo, d = int(m["y"]), int(m["m"]), int(m["d"])
        add(_hit("numeric", m, d, mo, y))
    for m in _DMY.finditer(text):
        if not free(m):
            continue
        year = int(m["y"]) + (2000 if len(m["y"]) == 2 else 0)
        d, mo, ok = _numeric(int(m["a"]), int(m["b"]), year)
        h = _hit("numeric", m, d, mo, year)
        h.valid = ok
        add(h)
    for m in _DM.finditer(text):
        if not free(m):
            continue
        d, mo, ok = _numeric(int(m["a"]), int(m["b"]), None)
        h = _hit("numeric", m, d, mo, None)
        h.valid = ok
        add(h)
    for pat in _WRITTEN:
        for m in pat.finditer(text):
            if not free(m):
                continue
            day = int(m["dnum"]) if m["dnum"] else ORDINALS[m["dword"].lower()]
            year = int(m["year"]) if m["year"] else None
            add(_hit("written", m, day, MONTHS[m["mon"].lower().rstrip(".")], year))
    for m in _DAY_ONLY.finditer(text):
        if not free(m):
            continue
        if m["dword"]:
            day = ORDINALS[m["dword"].lower()]
        else:
            day = int(m["dnum1"] or m["dnum2"])
        tail = _THIS_NEXT.match(text, m.end())
        # "the second" is usually not a date; small word ordinals need "of this/next month".
        if m["dword"] and day < 10 and not tail:
            continue
        month = None
        if tail:
            month = SIM_DATE.month + (1 if tail["rel"].lower() == "next" else 0)
            month = (month - 1) % 12 + 1
        h = DateHit("day_only", m.start(), tail.end() if tail else m.end(),
                    text[m.start():tail.end() if tail else m.end()].strip(), day, month, None,
                    1 <= day <= 31)
        add(h)
    return sorted(hits, key=lambda h: h.start)
