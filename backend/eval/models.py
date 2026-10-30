"""Result models for the deterministic checks (no LLM involved)."""
from typing import Literal, Optional

from pydantic import BaseModel


class Violation(BaseModel):
    turn: int  # index into transcript.turns
    category: str
    snippet: str


class FactItem(BaseModel):
    turn: int
    kind: Literal["amount", "days", "date"]
    status: Literal["matched", "unverified", "unparsed"]
    snippet: str
    value: Optional[str] = None  # normalised: "65200", "78", "2026-11-10" or "--11-10"


class FactReport(BaseModel):
    matched: int = 0
    unverified: int = 0
    unparsed: int = 0
    items: list[FactItem] = []


class PolicyViolation(BaseModel):
    rule: str
    detail: str


class OutcomeResult(BaseModel):
    passed: bool
    outcome: str
    expected: list[str]
    in_expected: bool
    forbidden_pairs: list[list[str]] = []


class RetrievalStats(BaseModel):
    search_calls: int = 0
    empty_results: int = 0
    queries: list[str] = []


class CheckResult(BaseModel):
    invoice_source: Literal["provided", "stored", "regenerated", "get_invoice", "none"]
    summary_llm_used: bool
    voice_violations: list[Violation]
    voice_counts: dict[str, int]
    facts: Optional[FactReport] = None  # None when no invoice could be found
    policy_violations: Optional[list[PolicyViolation]] = None  # None when skipped
    outcome: OutcomeResult
    retrieval: RetrievalStats
    notes: list[str] = []
