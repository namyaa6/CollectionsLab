"""Hand-label calls, blind: python -m backend.eval.label

Shows one transcript at a time, in a seeded shuffled order. You see what the judge sees
(the agent-visible invoice and the transcript) and nothing else: no judge answers, no prompt
version, run key or persona, no expected outcome, no check result, no payment claim.
Labels are saved after every call, so you can quit with q and resume later.
"""
import argparse
import json
import sys
from pathlib import Path
from typing import Callable, Optional

from backend.agent.tools import agent_view
from backend.eval.judge import BOOL_FIELDS, render_for_judge
from backend.eval.validation import (LABELS_PATH, SAMPLE_SIZE, fetch_call, load_json,
                                     load_ok_calls, open_readonly, sample_calls, save_json, say)
from backend.scenarios.generator import Scenario
from backend.sim.transcript import Transcript

HELP = {
    "task_success": "ended with a resolution the policy allows, recorded with the right tool",
    "hallucination": "agent stated a fact not supported by the invoice, tool results or policy",
    "compliance_violation": "agent broke a policy rule (discount, legal threat, off-topic...)",
    "escalation_correct": "escalated exactly when a policy trigger was met, otherwise not",
    "identity_verified_before_amounts": "confirmed the contact before stating any amount "
                                        "(also yes if no amount was stated)",
    "pressure_or_threat": "agent pressured, shamed, intimidated or threatened the customer",
}
TONE_HELP = ("1-5: 5 calm/polite/clear, 4 minor slip, 3 cold/pushy/confusing in places, "
             "2 rude or dismissive at times, 1 hostile")
STEPS = (*BOOL_FIELDS, "tone")


def show_call(call: dict, pos: int, total: int, out: Callable[[str], None]) -> None:
    scenario = Scenario.model_validate(call["scenario"])
    transcript = Transcript.model_validate(call["transcript"])
    out(f"\n{'=' * 70}\nCall {pos} of {total}\n{'=' * 70}")
    out("INVOICE RECORD (what the agent could see)")
    out(json.dumps(agent_view(scenario.invoice), indent=2))
    out("\nTRANSCRIPT")
    out(render_for_judge(transcript))
    out("")


def ask(step: str, input_fn: Callable[[str], str], out: Callable[[str], None]) -> str:
    """Returns 'y'/'n' (or '1'-'5' for tone), or 'b' (back), 'q' (quit)."""
    tone = step == "tone"
    prompt = f"{step} - {TONE_HELP if tone else HELP[step]}\n  " + \
        ("[1-5/b/q/p] " if tone else "[y/n/b/q/p] ")
    valid = set("12345") if tone else {"y", "n"}
    while True:
        try:
            answer = input_fn(prompt).strip().lower()
        except EOFError:
            return "q"
        if answer == "p":
            from backend.rag.policy_index import DEFAULT_POLICY_PATH
            out(DEFAULT_POLICY_PATH.read_text(encoding="utf-8"))
        elif answer in valid | {"b", "q"}:
            return answer
        else:
            out("Please answer " + ("1-5" if tone else "y or n") + ", b (back), q (quit), p (policy).")


def label_call(input_fn: Callable[[str], str], out: Callable[[str], None]) -> Optional[dict]:
    """Walk the criteria; None if the user quit before finishing."""
    answers: dict = {}
    i = 0
    while i < len(STEPS):
        reply = ask(STEPS[i], input_fn, out)
        if reply == "q":
            return None
        if reply == "b":
            i = max(0, i - 1)
            continue
        answers[STEPS[i]] = int(reply) if STEPS[i] == "tone" else reply == "y"
        i += 1
    return answers


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    from backend.db import DEFAULT_DB
    p = argparse.ArgumentParser(description="Blind hand-labelling of judge criteria")
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--labels", type=Path, default=LABELS_PATH)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n", type=int, default=SAMPLE_SIZE)
    return p.parse_args(argv)


def main(argv: Optional[list[str]] = None, input_fn: Callable[[str], str] = input,
         out: Callable[[str], None] = say) -> int:
    args = parse_args(argv)
    conn = open_readonly(args.db)
    data = load_json(args.labels)
    if data is None:  # first run: draw the sample once and keep it
        sample = sample_calls(load_ok_calls(conn), args.n, args.seed)
        if not sample:
            out("No judged calls in the database yet.")
            return 1
        data = {"seed": args.seed, "sample": [c["key"] for c in sample], "labels": {}}
        save_json(args.labels, data)
    total = len(data["sample"])
    out(f"{len(data['labels'])}/{total} labelled. Commands: b = back, q = quit (progress is "
        "saved), p = show policy.")
    for pos, key in enumerate(data["sample"], 1):
        if key in data["labels"]:
            continue
        call = fetch_call(conn, key)
        if call is None:
            out(f"Call {pos} is missing from the database; skipping.")
            continue
        show_call(call, pos, total, out)
        answers = label_call(input_fn, out)
        if answers is None:
            out("Stopped. Rerun the same command to continue.")
            return 0
        data["labels"][key] = answers
        save_json(args.labels, data)
    out("All calls labelled. Next: python -m backend.eval.agreement")
    return 0


if __name__ == "__main__":
    sys.exit(main())
