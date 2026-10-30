"""Fixed call-context block appended to every prompt version's system prompt.

Built by code, not by vN.yaml, so comparing prompt versions stays fair. It holds only
who is calling, who is being called and the date. Amounts and history must come
from the get_invoice tool.
"""
from backend.scenarios.generator import SIM_DATE, Invoice

AGENT_NAME = "Asha"
COMPANY_NAME = "Meridian Receivables"


def build_call_context(invoice: Invoice) -> str:
    return (
        "CALL CONTEXT\n"
        f"You are {AGENT_NAME}, a collections agent at {COMPANY_NAME}.\n"
        f"You are calling {invoice.contact_name} at {invoice.company}.\n"
        f"Invoice ID: {invoice.invoice_id}\n"
        f"Today's date: {SIM_DATE.isoformat()}"
    )
