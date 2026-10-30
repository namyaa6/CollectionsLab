"""One eval call end to end: simulate -> summarize -> deterministic checks -> judge.

Returns a record for db.save_call. status is "failed" when the call cannot be graded:
the transcript ended in agent_error/debtor_error (checks and judge are skipped, so no
requests are spent on them) or the judge reply was unusable. Exceptions (including
QuotaExhaustedError) propagate to the runner.
"""
from typing import Optional

from backend.agent.summarizer import summarize
from backend.eval.checks import run_all_checks
from backend.eval.judge import JudgePrompt, judge_call
from backend.llm.client import LLMClientProtocol
from backend.prompts import Prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import Scenario
from backend.sim.simulator import simulate
from backend.sim.transcript import Transcript

FAILED_ENDINGS = ("agent_error", "debtor_error")


def failed_record(scenario: Scenario, error: str, transcript: Optional[Transcript] = None,
                  **parts) -> dict:
    record = {"status": "failed", "error": error, "scenario": scenario.model_dump(mode="json"),
              "transcript": transcript.model_dump(mode="json") if transcript else None}
    if transcript:
        record.update(_cost(transcript))
    return {**record, **parts}


def _cost(t: Transcript) -> dict:
    tot = t.totals
    return {"latency_ms": tot["agent_latency_ms"],
            "tokens": tot["agent_input_tokens"] + tot["agent_output_tokens"]}


def evaluate_call(scenario: Scenario, client: LLMClientProtocol, prompt: Prompt, models: dict,
                  index: PolicyIndex, judge_prompt: JudgePrompt, policy_text: str,
                  seed: int) -> dict:
    t = simulate(scenario, client, prompt, models["agent"], models["sim"], index, seed=seed)
    if t.end_reason in FAILED_ENDINGS:
        return failed_record(scenario, f"{t.end_reason}: {t.end_detail}", t)
    summary = summarize(t, client, models["judge"])
    checks = run_all_checks(t, summary, scenario.invoice)
    judge = judge_call(t, scenario.invoice, client, models["judge"], judge_prompt, policy_text)
    parts = {"summary": summary.model_dump(mode="json"),
             "checks": checks.model_dump(mode="json"), "judge": judge}
    if judge["error"]:
        return failed_record(scenario, judge["error"], t, **parts)
    return {"status": "ok", "error": None, "scenario": scenario.model_dump(mode="json"),
            "transcript": t.model_dump(mode="json"), **parts, **_cost(t)}
