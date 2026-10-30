"""The agent's 8 tools as plain functions over a per-call CallState.

Tools check the shape of their arguments (dates parse, amounts are positive whole
rupees) but do NOT enforce policy: a 5-part plan or a 90-day promise is logged as given,
so the evaluator can catch the agent breaking policy.
"""
from dataclasses import dataclass, field
from datetime import date
from typing import Any, Optional

from backend.agent.tool_specs import TOOL_SPECS  # noqa: F401  (re-exported)
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import Invoice

# Allowlist of what the agent may see. Anything not listed (e.g. payment_claim, the
# debtor's private information) stays hidden, including fields added to Invoice later.
AGENT_VISIBLE_INVOICE_FIELDS = (
    "invoice_id", "company", "contact_name", "amount_inr", "gst_inr", "outstanding_inr",
    "amount_paid_inr", "due_date", "days_overdue", "status", "dispute_history",
    "broken_promises",
)
MUTATING_TOOLS = frozenset({
    "log_promise_to_pay", "log_installment_plan", "log_dispute", "log_payment_claim",
    "escalate_to_human", "end_call",
})


@dataclass
class CallState:
    """Everything about one call. Holds only this call's invoice, so tools cannot leak another."""
    invoice: Invoice  # full invoice; the agent only ever sees agent_view(invoice)
    actions: list[dict] = field(default_factory=list)  # {"tool", "args", "result"}
    ended: bool = False
    end_reason: Optional[str] = None
    escalated: bool = False


def agent_view(invoice: Invoice) -> dict:
    data = invoice.model_dump(mode="json")
    return {k: data[k] for k in AGENT_VISIBLE_INVOICE_FIELDS}


class ToolArgError(ValueError):
    pass


def _amount(value: Any) -> int:
    if isinstance(value, float) and value.is_integer():
        value = int(value)  # JSON from the model may send 5000.0
    if isinstance(value, bool) or not isinstance(value, int) or value <= 0:
        raise ToolArgError(f"amount_inr must be a positive whole number, got {value!r}")
    return value


def _date(value: Any) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ToolArgError(f"date must be YYYY-MM-DD, got {value!r}") from None


def _text(value: Any, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ToolArgError(f"{name} must be a non-empty string")
    return value.strip()


def _record(state: CallState, tool: str, args: dict, result: dict) -> dict:
    state.actions.append({"tool": tool, "args": args, "result": result})
    return result


def get_invoice(state: CallState, invoice_id: str) -> dict:
    if invoice_id != state.invoice.invoice_id:
        return {"error": "invoice not found"}
    return agent_view(state.invoice)


def search_policy(index: PolicyIndex, query: str) -> dict:
    return {"results": [{"section": r["section"], "text": r["text"]}
                        for r in index.search(_text(query, "query"), k=3)]}


def log_promise_to_pay(state: CallState, date: str, amount_inr: int) -> dict:
    args = {"date": _date(date), "amount_inr": _amount(amount_inr)}
    return _record(state, "log_promise_to_pay", args, {"status": "logged"})


def log_installment_plan(state: CallState, parts: list) -> dict:
    if not isinstance(parts, list) or not parts:
        raise ToolArgError("parts must be a non-empty list")
    clean = []
    for p in parts:
        if not isinstance(p, dict):
            raise ToolArgError("each part needs a date and amount_inr")
        clean.append({"date": _date(p.get("date")), "amount_inr": _amount(p.get("amount_inr"))})
    return _record(state, "log_installment_plan", {"parts": clean}, {"status": "logged"})


def log_dispute(state: CallState, reason: str) -> dict:
    return _record(state, "log_dispute", {"reason": _text(reason, "reason")}, {"status": "logged"})


def log_payment_claim(state: CallState, utr: str, date: str, amount_inr: int) -> dict:
    args = {"utr": _text(utr, "utr"), "date": _date(date), "amount_inr": _amount(amount_inr)}
    return _record(state, "log_payment_claim", args, {"status": "logged"})


def escalate_to_human(state: CallState, reason: str) -> dict:
    args = {"reason": _text(reason, "reason")}
    result = _record(state, "escalate_to_human", args, {"status": "escalated"})
    state.escalated, state.ended, state.end_reason = True, True, args["reason"]
    return result


def end_call(state: CallState, reason: str) -> dict:
    args = {"reason": _text(reason, "reason")}
    result = _record(state, "end_call", args, {"status": "call_ended"})
    state.ended, state.end_reason = True, args["reason"]
    return result


_STATE_TOOLS = {f.__name__: f for f in (
    get_invoice, log_promise_to_pay, log_installment_plan, log_dispute,
    log_payment_claim, escalate_to_human, end_call,
)}
TOOL_NAMES = frozenset(_STATE_TOOLS) | {"search_policy"}


def execute_tool(state: CallState, name: str, args: dict, index: PolicyIndex) -> dict:
    """Single entry point for the agent loop. Never raises: bad calls return {"error": ...}."""
    if name not in TOOL_NAMES:
        return {"error": f"unknown tool: {name}"}
    if name in MUTATING_TOOLS and state.ended:
        return {"error": "call has ended"}
    try:
        if name == "search_policy":
            return search_policy(index, **args)
        return _STATE_TOOLS[name](state, **args)
    except ToolArgError as exc:
        return {"error": str(exc)}
    except TypeError as exc:  # missing or unexpected argument names
        return {"error": f"bad arguments for {name}: {exc}"}
