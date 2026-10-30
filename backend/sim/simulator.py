"""Runs one call: the agent speaks first, then agent and debtor alternate."""
import json

from backend.agent.agent import run_agent_turn
from backend.agent.context import COMPANY_NAME, build_call_context
from backend.agent.tools import CallState
from backend.llm.client import LLMClientProtocol
from backend.llm.types import LLMResponseError
from backend.prompts import Prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import SIM_DATE, Scenario
from backend.scenarios.personas import PERSONAS
from backend.sim.transcript import Transcript, Turn

MAX_DEBTOR_TURNS = 12
DEBTOR_TEMPERATURE = 0.7
CONNECTED = "[The call has connected.]"  # Gemini needs a first user message


def debtor_system(scenario: Scenario) -> str:
    """Persona behavior plus the full invoice as private context (including payment_claim)."""
    invoice = json.dumps(scenario.invoice.model_dump(mode="json"), indent=2)
    return (
        f"{PERSONAS[scenario.persona].behavior}\n\n"
        f"You are on a phone call with a collections agent from {COMPANY_NAME}. "
        f"Today's date is {SIM_DATE.isoformat()}. Reply with the words you would say "
        "aloud only: no stage directions, no quotation marks.\n\n"
        f"PRIVATE CONTEXT (your invoice; the agent may not know all of it):\n{invoice}"
    )


def simulate(scenario: Scenario, client: LLMClientProtocol, prompt: Prompt, agent_model: str,
             sim_model: str, index: PolicyIndex, seed: int = 0,
             max_debtor_turns: int = MAX_DEBTOR_TURNS) -> Transcript:
    state = CallState(invoice=scenario.invoice)
    agent_system = f"{prompt.system}\n\n{build_call_context(scenario.invoice)}"
    debtor_sys = debtor_system(scenario)
    agent_hist: list[dict] = [{"role": "user", "text": CONNECTED}]
    debtor_hist: list[dict] = []
    turns: list[Turn] = []
    end_reason, end_detail = "turn_limit", None

    for _ in range(max_debtor_turns):
        at = run_agent_turn(client, agent_model, agent_system, agent_hist, state, index)
        turns.append(Turn(speaker="agent", text=at.text, tool_calls=at.tool_calls,
                          latency_ms=at.latency_ms, input_tokens=at.input_tokens,
                          output_tokens=at.output_tokens, llm_calls=at.llm_calls,
                          cached=at.cached, error=at.error))
        if state.ended:
            end_reason = "escalated" if state.escalated else "end_call"
            end_detail = state.end_reason
            break
        if at.error:
            end_reason, end_detail = "agent_error", at.error
            break
        debtor_hist.append({"role": "user", "text": at.text})
        try:
            resp = client.generate(sim_model, debtor_hist, system=debtor_sys,
                                   temperature=DEBTOR_TEMPERATURE, cache_salt=f"seed={seed}")
        except LLMResponseError as exc:
            end_reason, end_detail = "debtor_error", str(exc)
            break
        if not resp.text.strip():
            end_reason, end_detail = "debtor_error", f"empty reply ({resp.finish_reason})"
            break
        turns.append(Turn(speaker="debtor", text=resp.text.strip(), latency_ms=resp.latency_ms,
                          input_tokens=resp.input_tokens, output_tokens=resp.output_tokens,
                          llm_calls=1, cached=resp.cached))
        debtor_hist.append({"role": "model", "text": resp.text.strip()})
        agent_hist.append({"role": "user", "text": resp.text.strip()})

    return Transcript(
        scenario_id=scenario.scenario_id, persona=scenario.persona,
        expected_outcomes=scenario.expected_outcomes, prompt_version=prompt.version,
        agent_model=agent_model, sim_model=sim_model, seed=seed, turns=turns,
        actions=state.actions, end_reason=end_reason, end_detail=end_detail)
