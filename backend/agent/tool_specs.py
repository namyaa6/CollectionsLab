"""Tool declarations for the agent (JSON schema; LLMClient turns them into Gemini function declarations)."""
from backend.llm.types import ToolSpec

_STR = {"type": "string"}
_DATE = {"type": "string", "description": "Date as YYYY-MM-DD"}
_AMOUNT = {"type": "integer", "description": "Amount in INR, whole rupees"}


def _obj(properties: dict) -> dict:
    return {"type": "object", "properties": properties, "required": list(properties)}


TOOL_SPECS = [
    ToolSpec("get_invoice", "Get the invoice for this call.",
             _obj({"invoice_id": _STR})),
    ToolSpec("search_policy", "Search the company collections policy. Returns the most relevant sections.",
             _obj({"query": _STR})),
    ToolSpec("log_promise_to_pay", "Record that the debtor promised to pay the full outstanding amount on a date.",
             _obj({"date": _DATE, "amount_inr": _AMOUNT})),
    ToolSpec("log_installment_plan", "Record an agreed installment plan.",
             _obj({"parts": {"type": "array", "description": "One entry per installment",
                             "items": _obj({"date": _DATE, "amount_inr": _AMOUNT})}})),
    ToolSpec("log_dispute", "Record that the debtor disputes the invoice, with the reason they gave.",
             _obj({"reason": _STR})),
    ToolSpec("log_payment_claim", "Record that the debtor says they already paid.",
             _obj({"utr": {"type": "string", "description": "UTR number given by the debtor"},
                   "date": _DATE, "amount_inr": _AMOUNT})),
    ToolSpec("escalate_to_human", "Hand the case to a senior colleague and end the call.",
             _obj({"reason": _STR})),
    ToolSpec("end_call", "End the call.",
             _obj({"reason": _STR})),
]
