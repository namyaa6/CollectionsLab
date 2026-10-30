"""LLM judge: one JUDGE_MODEL call per transcript, structured output with quoted evidence.

The judge sees the policy, the agent-visible invoice and the transcript with tool calls.
It does NOT see the persona, the expected outcome or any deterministic check result, so
its reading is independent of the code checks.
"""
import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from pydantic import BaseModel, field_validator

from backend.agent.tools import agent_view
from backend.llm.client import LLMClientProtocol
from backend.llm.types import LLMResponseError
from backend.scenarios.generator import SIM_DATE, Invoice
from backend.sim.transcript import Transcript

JUDGE_PROMPT_PATH = Path(__file__).resolve().parent / "judge_prompt.yaml"
BOOL_FIELDS = ("task_success", "hallucination", "compliance_violation", "escalation_correct",
               "identity_verified_before_amounts", "pressure_or_threat")


class Verdict(BaseModel):
    value: bool
    evidence: str


class ToneVerdict(BaseModel):
    score: int
    evidence: str

    @field_validator("score")
    @classmethod
    def _in_range(cls, v: int) -> int:
        if not 1 <= v <= 5:
            raise ValueError(f"tone score must be 1-5, got {v}")
        return v


class JudgeVerdict(BaseModel):
    """Also the model's response schema."""
    task_success: Verdict
    hallucination: Verdict
    compliance_violation: Verdict
    escalation_correct: Verdict
    identity_verified_before_amounts: Verdict
    pressure_or_threat: Verdict
    tone: ToneVerdict


@dataclass(frozen=True)
class JudgePrompt:
    version: str
    system: str
    file_hash: str


def load_judge_prompt(path: Path = JUDGE_PROMPT_PATH) -> JudgePrompt:
    raw = path.read_bytes()
    data = yaml.safe_load(raw.decode("utf-8")) or {}
    system = str(data.get("system", "")).strip()
    if not system or not data.get("version"):
        raise ValueError(f"{path.name} needs 'version' and 'system'")
    return JudgePrompt(str(data["version"]), system, hashlib.sha256(raw).hexdigest())


def render_for_judge(t: Transcript) -> str:
    lines = []
    for i, turn in enumerate(t.turns):
        lines.append(f"[{i}] {turn.speaker.upper()}: {turn.text.strip() or '(no speech)'}")
        for c in turn.tool_calls:
            lines.append(f"    [tool] {c['tool']}({json.dumps(c['args'])}) -> "
                         f"{json.dumps(c['result'], ensure_ascii=False)}")
    return "\n".join(lines)


def build_judge_input(t: Transcript, invoice: Invoice, policy_text: str) -> str:
    return (f"Today's date: {SIM_DATE.isoformat()}\n\n"
            f"POLICY\n{policy_text.strip()}\n\n"
            f"INVOICE RECORD (what the agent could see)\n"
            f"{json.dumps(agent_view(invoice), indent=2)}\n\n"
            f"TRANSCRIPT\n{render_for_judge(t)}")


def _norm(s: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"[^\w\s]", " ", s.lower())).strip()


def evidence_found(verdict: JudgeVerdict, t: Transcript) -> dict[str, bool]:
    """Does each quote really appear in the transcript? An empty quote counts as found."""
    haystack = _norm(render_for_judge(t))
    return {name: _norm(getattr(verdict, name).evidence) in haystack
            for name in (*BOOL_FIELDS, "tone")}


def judge_call(t: Transcript, invoice: Invoice, client: LLMClientProtocol, model: str,
               prompt: JudgePrompt, policy_text: str) -> dict:
    """Returns {"verdict", "evidence_found", "judge_version", "error"}; verdict is None on error."""
    out = {"verdict": None, "evidence_found": None, "judge_version": prompt.version, "error": None}
    try:
        resp = client.generate(model, [{"role": "user",
                                        "text": build_judge_input(t, invoice, policy_text)}],
                               system=prompt.system, response_schema=JudgeVerdict)
    except LLMResponseError as exc:
        out["error"] = f"judge reply unusable: {exc}"
        return out
    verdict: JudgeVerdict = resp.parsed
    out["verdict"] = verdict.model_dump()
    out["evidence_found"] = evidence_found(verdict, t)
    return out
