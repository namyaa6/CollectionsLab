"""BM25Plus search over the collections policy, one chunk per `## ` section.

BM25Plus, written out (N chunks, n(t) = chunks containing term t, f = count of t in chunk d):
    idf(t)      = ln((N + 1) / n(t))                      always > 0
    tf_part     = f * (k1 + 1) / (f + k1 * (1 - b + b * |d| / avgdl))
    score(q, d) = sum over query terms t in d of idf(t) * (delta + tf_part)
Okapi BM25 uses ln((N - n + 0.5) / (n + 0.5)), which is <= 0 for terms in half or more of
a tiny corpus (N=10). BM25Plus keeps IDF positive, and delta gives any matching term a
floor, so a relevant match is never scored zero. Absent terms still add nothing.
"""
import math
import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

DEFAULT_POLICY_PATH = Path(__file__).resolve().parents[2] / "data" / "policy" / "collections_policy.md"
K1, B, DELTA = 1.5, 0.75, 1.0
# BM25 scores have no absolute scale, so drop hits far below the best one instead.
MIN_RELATIVE_SCORE = 0.5
STOPWORDS = frozenset(
    "a an and are as at be by can do does for from he her his i if in into is it its me my "
    "of on or our she so that the their them they this to us was we what when which who "
    "will with you your".split()
)


@dataclass
class Chunk:
    title: str
    text: str


def load_chunks(path: Path = DEFAULT_POLICY_PATH) -> list[Chunk]:
    """Split on `## ` headings; the `# ` title and intro paragraph are dropped."""
    chunks: list[Chunk] = []
    for block in re.split(r"^## ", path.read_text(encoding="utf-8"), flags=re.M)[1:]:
        title, _, body = block.partition("\n")
        chunks.append(Chunk(title.strip(), body.strip()))
    return chunks


def tokenize(text: str) -> list[str]:
    tokens = []
    for tok in re.findall(r"[a-z0-9]+", text.lower()):
        if tok in STOPWORDS:
            continue
        if len(tok) > 3 and tok.endswith("s") and not tok.endswith("ss"):
            tok = tok[:-1]  # crude plural stripping: installments -> installment
        tokens.append(tok)
    return tokens


class PolicyIndex:
    def __init__(self, chunks: list[Chunk]):
        self.chunks = chunks
        # Body only. Indexing titles too (even once) let "payment" in the title "Payment
        # Promise Window" outrank "Installment Rules" for an installments query.
        self.docs = [Counter(tokenize(c.text)) for c in chunks]
        self.lengths = [sum(d.values()) for d in self.docs]
        self.avgdl = sum(self.lengths) / len(self.lengths)
        n = len(chunks)
        df = Counter(t for d in self.docs for t in d)
        self.idf = {t: math.log((n + 1) / c) for t, c in df.items()}

    @classmethod
    def from_file(cls, path: Optional[Path] = None) -> "PolicyIndex":
        return cls(load_chunks(path or DEFAULT_POLICY_PATH))

    def scores(self, query: str) -> list[float]:
        """BM25Plus score of every chunk (0.0 when no query term appears in it)."""
        terms = [t for t in set(tokenize(query)) if t in self.idf]
        out = []
        for doc, length in zip(self.docs, self.lengths):
            norm = K1 * (1 - B + B * length / self.avgdl)
            out.append(sum(
                self.idf[t] * (DELTA + doc[t] * (K1 + 1) / (doc[t] + norm))
                for t in terms if doc[t]
            ))
        return out

    def search(self, query: str, k: int = 3) -> list[dict]:
        """Top-k chunks, best first. Only chunks sharing a query term are candidates, and
        only those scoring at least MIN_RELATIVE_SCORE x the best are kept."""
        scored = sorted(
            ((s, c) for s, c in zip(self.scores(query), self.chunks) if s > 0),
            key=lambda x: -x[0],
        )
        if not scored:
            return []
        cutoff = scored[0][0] * MIN_RELATIVE_SCORE
        return [{"section": c.title, "text": c.text, "score": round(s, 4)}
                for s, c in scored if s >= cutoff][:k]
