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
        f"You are {AGENT_NAME}, a collections agent at {COMPANY_NAME}. "
        f"{COMPANY_NAME} is the creditor: it is owed the money, and you call on its behalf.\n"
        f"You are calling {invoice.contact_name} at {invoice.company}. "
        f"{invoice.company} is the customer (the debtor) who owes the unpaid invoice. "
        f"It is not your employer and you do not represent it.\n"
        f"Invoice ID: {invoice.invoice_id}\n"
        f"Today's date: {SIM_DATE.isoformat()}"
    )
