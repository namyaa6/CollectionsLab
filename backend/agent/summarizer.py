"""Turns a transcript + logged actions into a CallSummary.

Two readings: the logged actions (authoritative, no LLM) and an LLM reading of the
dialogue alone. Action-derived fields win; any disagreement is written to `discrepancies`.
Run: python -m backend.agent.summarizer --transcript data/transcripts/v1_s0_seed42.json
"""
import argparse
from pathlib import Path
from typing import Optional

from backend.agent.summary_schema import CallSummary, InstallmentPart, LLMReading, PaymentClaim
from backend.config import get_config
from backend.llm.client import LLMClient, LLMClientProtocol
from backend.llm.types import LLMResponseError
from backend.scenarios.generator import SIM_DATE
from backend.sim.transcript import Transcript

TOOL_OUTCOME = {
    "log_promise_to_pay": "promise_to_pay",
    "log_installment_plan": "installment_plan",
    "log_dispute": "dispute_logged",
    "log_payment_claim": "payment_claim_logged",
    "escalate_to_human": "escalated",
}
# One outcome has to be picked for the single `outcome` field; logged_outcomes keeps the rest.
PRECEDENCE = ["escalated", "dispute_logged", "payment_claim_logged",
              "installment_plan", "promise_to_pay"]
EXACT_FIELDS = ("promise_date", "amount_inr", "installment_plan", "payment_claim")
FALLBACK_NEXT_ACTION = {
    "promise_to_pay": "Confirm the payment arrives by the promised date.",
    "installment_plan": "Confirm each installment arrives on its date.",
    "dispute_logged": "Pass the dispute to the billing team for review.",
    "payment_claim_logged": "Verify the claimed payment against the UTR.",
    "escalated": "A human agent follows up.",
    "no_resolution": "Call the customer again.",
}
SYSTEM = (
    "You summarize a collections phone call. Read only the dialogue and fill the JSON. "
    "outcome is what the customer and agent actually agreed or raised: promise_to_pay, "
    "installment_plan, dispute_logged, payment_claim_logged, escalated, or no_resolution. "
    "Dates are YYYY-MM-DD; resolve relative dates against today's date. amount_inr is the "
    "single promised amount in whole rupees (null for installment plans). Use null for anything "
    "not said. next_action is one short sentence for the collections team."
)


def derive_from_actions(actions: list[dict]) -> tuple[dict, list[str], list[str]]:
    """Returns (fields, logged_outcomes in call order, notes). The last call of a tool wins."""
    fields: dict = {}
    logged: list[str] = []
    notes: list[str] = []
    seen: set[str] = set()
    for a in actions:
        tool, args = a["tool"], a["args"]
        if tool not in TOOL_OUTCOME:
            continue
        if tool in seen:
            notes.append(f"{tool} was logged more than once; the last one is used.")
        seen.add(tool)
        if TOOL_OUTCOME[tool] not in logged:
            logged.append(TOOL_OUTCOME[tool])
        if tool == "log_promise_to_pay":
            fields.update(promise_date=args["date"], amount_inr=args["amount_inr"])
        elif tool == "log_installment_plan":
            fields["installment_plan"] = [InstallmentPart(**p) for p in args["parts"]]
        elif tool == "log_dispute":
            fields["dispute_reason"] = args["reason"]
        elif tool == "log_payment_claim":
            fields["payment_claim"] = PaymentClaim(**args)
    return fields, logged, notes


def pick_outcome(logged: list[str]) -> str:
    return next((o for o in PRECEDENCE if o in logged), "no_resolution")


def build_dialogue(t: Transcript) -> str:
    lines = [f"Today's date: {SIM_DATE.isoformat()}", ""]
    for turn in t.turns:
        if turn.text.strip():
            lines.append(f"{turn.speaker.upper()}: {turn.text.strip()}")
    return "\n".join(lines)


def _differs(name: str, logged_val, llm_val) -> Optional[str]:
    if name == "dispute_reason":  # free text: compare presence only
        if bool(logged_val) == bool(llm_val):
            return None
    elif logged_val == llm_val:
        return None
    return f"{name}: logged {_show(logged_val)}, LLM read {_show(llm_val)}."


def _show(value) -> str:
    if isinstance(value, list):
        return str([v.model_dump() for v in value])
    return str(value.model_dump() if hasattr(value, "model_dump") else value)


def compare_with_llm(fields: dict, logged: list[str], escalated: bool, llm: LLMReading) -> list[str]:
    out = []
    if llm.outcome not in logged and not (llm.outcome == "no_resolution" and not logged):
        out.append(f"outcome: logged {logged or 'none'}, LLM read {llm.outcome}.")
    for name in (*EXACT_FIELDS, "dispute_reason"):
        if (msg := _differs(name, fields.get(name), getattr(llm, name))):
            out.append(msg)
    if llm.escalated != escalated:
        out.append(f"escalated: logged {escalated}, LLM read {llm.escalated}.")
    return out


def summarize_offline(transcript: Transcript) -> CallSummary:
    """The summary from logged actions alone: no LLM call."""
    return summarize(transcript, None, "")


def summarize(transcript: Transcript, client: Optional[LLMClientProtocol], model: str) -> CallSummary:
    """With client=None the LLM reading is skipped (llm_used=False)."""
    fields, logged, notes = derive_from_actions(transcript.actions)
    if len([o for o in logged if o != "escalated"]) > 1:
        notes.append("Multiple outcomes logged: " + ", ".join(logged) + " (order of calls).")
    outcome = pick_outcome(logged)
    escalated = "escalated" in logged
    llm_used, next_action = False, FALLBACK_NEXT_ACTION[outcome]
    if client is not None:
        try:
            resp = client.generate(model, [{"role": "user", "text": build_dialogue(transcript)}],
                                   system=SYSTEM, response_schema=LLMReading)
            llm: LLMReading = resp.parsed
            notes += compare_with_llm(fields, logged, escalated, llm)
            next_action, llm_used = llm.next_action, True
        except LLMResponseError as exc:
            notes.append(f"LLM reading unavailable, record built from logged actions only: {exc}")
    return CallSummary(outcome=outcome, escalated=escalated, next_action=next_action,
                       logged_outcomes=logged, discrepancies=notes, llm_used=llm_used, **fields)


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Summarize one saved transcript (live API, 1 call)")
    p.add_argument("--transcript", type=Path, required=True)
    args = p.parse_args(argv)
    cfg = get_config()
    summary = summarize(Transcript.load(args.transcript), LLMClient.from_config(cfg), cfg.judge_model)
    print(summary.model_dump_json(indent=2))


if __name__ == "__main__":
    main()
