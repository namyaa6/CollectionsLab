"""The call summary record (SPEC section 7), validated by Pydantic."""
from datetime import date
from typing import Literal, Optional

from pydantic import BaseModel, field_validator

Outcome = Literal["promise_to_pay", "installment_plan", "dispute_logged",
                  "payment_claim_logged", "escalated", "no_resolution"]


def _check_date(value: Optional[str]) -> Optional[str]:
    if value is None:
        return None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError:
        raise ValueError(f"date must be YYYY-MM-DD, got {value!r}") from None


def _check_amount(value: Optional[int]) -> Optional[int]:
    if value is not None and value <= 0:
        raise ValueError(f"amount_inr must be positive, got {value}")
    return value


class InstallmentPart(BaseModel):
    date: str
    amount_inr: int

    _date = field_validator("date")(_check_date)
    _amount = field_validator("amount_inr")(_check_amount)


class PaymentClaim(BaseModel):
    utr: str
    date: str
    amount_inr: int

    _date = field_validator("date")(_check_date)
    _amount = field_validator("amount_inr")(_check_amount)


class LLMReading(BaseModel):
    """What the LLM fills in from the dialogue alone. Also the model's response schema."""
    outcome: Outcome
    promise_date: Optional[str] = None
    amount_inr: Optional[int] = None  # the single promised amount; null for installment plans
    installment_plan: Optional[list[InstallmentPart]] = None
    dispute_reason: Optional[str] = None
    payment_claim: Optional[PaymentClaim] = None
    escalated: bool = False
    next_action: str

    _date = field_validator("promise_date")(_check_date)
    _amount = field_validator("amount_inr")(_check_amount)


class CallSummary(LLMReading):
    """Final record. Logged actions win over the LLM; code fills the last three fields."""
    logged_outcomes: list[Outcome] = []  # every distinct outcome logged, in call order
    discrepancies: list[str] = []
    llm_used: bool = True
