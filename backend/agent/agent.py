"""One agent turn: call the model, run its tool calls, loop until it speaks."""
from dataclasses import dataclass, field
from typing import Optional

from backend.agent.self_check import replace_spoken, run_self_check
from backend.agent.tools import TOOL_SPECS, CallState, execute_tool
from backend.llm.client import LLMClientProtocol
from backend.llm.types import LLMResponse, LLMResponseError
from backend.rag.policy_index import PolicyIndex

MAX_TOOL_ROUNDS = 6  # model calls per turn; stops a model that never stops calling tools


@dataclass
class AgentTurn:
    text: str = ""
    tool_calls: list[dict] = field(default_factory=list)  # {"tool", "args", "result"}
    latency_ms: int = 0
    input_tokens: int = 0
    output_tokens: int = 0
    llm_calls: int = 0
    cached: bool = True  # True only if every model call came from the cache
    error: Optional[str] = None
    self_check: Optional[dict] = None  # v4+: draft, final, issues and the check's own cost


def _model_message(resp: LLMResponse) -> dict:
    """Replay the raw Content when there is one (keeps Gemini thought signatures)."""
    if resp.raw_content is not None:
        return {"role": "model", "raw": resp.raw_content}
    return {"role": "model", "text": resp.text, "tool_calls": resp.tool_calls}


def run_agent_turn(client: LLMClientProtocol, model: str, system: str, history: list[dict],
                   state: CallState, index: PolicyIndex, temperature: float = 0.0,
                   max_rounds: int = MAX_TOOL_ROUNDS, *, self_check: bool = False,
                   check_system: str = "") -> AgentTurn:
    """Appends this turn's model/tool messages to `history` and returns what was recorded.

    With self_check off (v1-v3) nothing below the loop runs: same requests as before.
    """
    turn = AgentTurn()
    turn_start = len(history)
    texts: list[str] = []
    for _ in range(max_rounds):
        try:
            resp = client.generate(model, history, system=system, tools=TOOL_SPECS,
                                   temperature=temperature)
        except LLMResponseError as exc:
            turn.error = str(exc)
            break
        turn.llm_calls += 1
        turn.latency_ms += resp.latency_ms
        turn.input_tokens += resp.input_tokens
        turn.output_tokens += resp.output_tokens
        turn.cached = turn.cached and resp.cached
        if resp.text.strip():
            texts.append(resp.text.strip())  # the model often speaks and calls end_call together
        history.append(_model_message(resp))
        if not resp.tool_calls:
            if not texts:
                turn.error = f"empty reply (finish_reason={resp.finish_reason})"
            break
        results = []
        for call in resp.tool_calls:
            result = execute_tool(state, call.name, call.args, index)
            turn.tool_calls.append({"tool": call.name, "args": call.args, "result": result})
            results.append({"name": call.name, "response": result})
        history.append({"role": "tool", "results": results})
        if state.ended:
            break
    else:
        turn.error = f"no spoken reply after {max_rounds} model calls"
    turn.text = " ".join(texts)
    if self_check and turn.text and not turn.error:
        _apply_self_check(turn, client, model, check_system, system, history, turn_start)
    return turn


def _apply_self_check(turn: AgentTurn, client: LLMClientProtocol, model: str, check_system: str,
                      system: str, history: list[dict], turn_start: int) -> None:
    check = run_self_check(client, model, check_system, system, history, turn_start, turn.text)
    turn.self_check = check
    turn.llm_calls += 1  # the check is a model call, so latency and tokens count toward the turn
    turn.latency_ms += check["latency_ms"]
    turn.input_tokens += check["input_tokens"]
    turn.output_tokens += check["output_tokens"]
    turn.cached = turn.cached and check["cached"]
    if check["revised"]:
        turn.text = check["final"]
        replace_spoken(history, turn_start, check["final"])
