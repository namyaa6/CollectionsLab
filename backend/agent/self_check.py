"""Optional self-check (v4+): review the agent's draft reply before it is spoken.

One extra model call per turn, with no tools. The checker sees only what the agent has seen
(its instructions, tool results, the conversation), so hidden invoice fields never reach it.
If the check fails for any reason the draft is spoken as is.
"""
import json
from typing import Optional

from pydantic import BaseModel

from backend.llm.client import LLMClientProtocol
from backend.llm.types import LLMResponseError

FACT_TOOLS = ("get_invoice", "search_policy")  # results the draft must be consistent with


class SelfCheckVerdict(BaseModel):
    ok: bool
    issues: list[str] = []
    revised: str = ""  # the full reply to speak; equal to the draft when ok


def _parts(message: dict):
    """(spoken text, tool call names) of a model message, plain or raw Gemini Content."""
    raw = message.get("raw")
    if raw is None:
        calls = [c["name"] if isinstance(c, dict) else c.name for c in message.get("tool_calls", [])]
        return message.get("text", ""), calls
    parts = raw.parts or []
    text = "".join(p.text for p in parts if p.text and not p.thought)
    return text, [p.function_call.name for p in parts if p.function_call]


def render_for_check(agent_system: str, history: list[dict], turn_start: int, draft: str) -> str:
    facts, convo, did = [], [], []
    for i, m in enumerate(history):
        if m["role"] == "tool":
            for r in m["results"]:
                line = f"{r['name']}: {json.dumps(r['response'], ensure_ascii=True)}"
                (facts if r["name"] in FACT_TOOLS else did if i >= turn_start else convo).append(line)
        elif m["role"] == "user":
            convo.append(f"CUSTOMER: {m['text']}")
        else:
            text, calls = _parts(m)
            if i < turn_start and text:
                convo.append(f"AGENT: {text}")
            did += [f"called {name}" for name in calls if i >= turn_start]
    return (f"AGENT INSTRUCTIONS:\n{agent_system}\n\n"
            f"TOOL RESULTS SO FAR:\n{chr(10).join(facts) or '(none)'}\n\n"
            f"CONVERSATION SO FAR:\n{chr(10).join(convo) or '(none)'}\n\n"
            f"AGENT ACTIONS THIS TURN:\n{chr(10).join(did) or '(none)'}\n\n"
            f"DRAFT:\n{draft}")


def run_self_check(client: LLMClientProtocol, model: str, check_system: str, agent_system: str,
                   history: list[dict], turn_start: int, draft: str) -> dict:
    """Returns the record kept on the turn. `final` is what gets spoken."""
    record = {"draft": draft, "final": draft, "revised": False, "issues": [], "latency_ms": 0,
              "input_tokens": 0, "output_tokens": 0, "cached": True, "error": None}
    message = {"role": "user", "text": render_for_check(agent_system, history, turn_start, draft)}
    try:
        resp = client.generate(model, [message], system=check_system, temperature=0.0,
                               response_schema=SelfCheckVerdict)
    except LLMResponseError as exc:
        record["error"] = str(exc)
        return record
    record.update(latency_ms=resp.latency_ms, input_tokens=resp.input_tokens,
                  output_tokens=resp.output_tokens, cached=resp.cached)
    verdict: Optional[SelfCheckVerdict] = resp.parsed
    if verdict is None:
        record["error"] = f"no usable reply (finish_reason={resp.finish_reason})"
        return record
    record["issues"] = list(verdict.issues)
    revised = verdict.revised.strip()
    if not verdict.ok and revised and revised != draft:
        record.update(final=revised, revised=True)
    return record


def replace_spoken(history: list[dict], turn_start: int, final: str) -> None:
    """Make this turn's model messages say `final`, so later turns see what was spoken.

    Text moves onto the last model message that had any; function calls (and the thought
    signatures stored with raw Content) are left alone.
    """
    spoken = [i for i in range(turn_start, len(history))
              if history[i]["role"] == "model" and _parts(history[i])[0]]
    for i in spoken:
        history[i] = _with_text(history[i], final if i == spoken[-1] else "")


def _with_text(message: dict, text: str) -> dict:
    raw: Optional[object] = message.get("raw")
    if raw is None:
        return {**message, "text": text}
    new_parts, put = [], False
    for p in raw.parts or []:
        if p.text and not p.thought:
            if text and not put:
                new_parts.append(p.model_copy(update={"text": text}))
                put = True
        else:
            new_parts.append(p)
    return {**message, "raw": raw.model_copy(update={"parts": new_parts})}
