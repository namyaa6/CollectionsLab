"""One simulated call, as saved to JSON."""
from pathlib import Path
from typing import Literal, Optional

from pydantic import BaseModel, computed_field

EndReason = Literal["end_call", "escalated", "turn_limit", "agent_error", "debtor_error"]


class Turn(BaseModel):
    speaker: Literal["agent", "debtor"]
    text: str
    tool_calls: list[dict] = []  # agent only: {"tool", "args", "result"}
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    cached: bool = False
    error: Optional[str] = None


class Transcript(BaseModel):
    scenario_id: int
    persona: str
    expected_outcomes: list[str]
    prompt_version: str
    agent_model: str
    sim_model: str
    seed: int
    turns: list[Turn]
    actions: list[dict]  # what the agent logged, from CallState
    end_reason: EndReason
    end_detail: Optional[str] = None

    @computed_field
    @property
    def totals(self) -> dict:
        agent = [t for t in self.turns if t.speaker == "agent"]
        debtor = [t for t in self.turns if t.speaker == "debtor"]
        return {
            "agent_turns": len(agent),
            "debtor_turns": len(debtor),
            "agent_latency_ms": sum(t.latency_ms for t in agent),
            "agent_input_tokens": sum(t.input_tokens for t in agent),
            "agent_output_tokens": sum(t.output_tokens for t in agent),
            "debtor_input_tokens": sum(t.input_tokens for t in debtor),
            "debtor_output_tokens": sum(t.output_tokens for t in debtor),
        }

    def save(self, directory: Path, name: str) -> Path:
        directory.mkdir(parents=True, exist_ok=True)
        path = directory / name
        path.write_text(self.model_dump_json(indent=2), encoding="utf-8")
        return path

    @classmethod
    def load(cls, path: Path) -> "Transcript":
        return cls.model_validate_json(path.read_text(encoding="utf-8"))
