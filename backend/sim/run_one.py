"""Run one simulated call against the real API: python -m backend.sim.run_one --scenario 0 --prompt v1"""
import argparse
from pathlib import Path
from typing import Optional

from backend.config import get_config
from backend.llm.client import LLMClient
from backend.prompts import load_prompt
from backend.rag.policy_index import PolicyIndex
from backend.scenarios.generator import generate_scenarios
from backend.sim.simulator import simulate
from backend.sim.transcript import Transcript

DEFAULT_OUT = Path(__file__).resolve().parents[2] / "data" / "transcripts"


def format_transcript(t: Transcript) -> str:
    lines = [f"Scenario {t.scenario_id} | persona={t.persona} | prompt={t.prompt_version} | "
             f"expected={t.expected_outcomes}", ""]
    for turn in t.turns:
        who = "AGENT " if turn.speaker == "agent" else "DEBTOR"
        lines.append(f"{who}: {turn.text or '(no speech)'}")
        for c in turn.tool_calls:
            lines.append(f"    [tool] {c['tool']}({c['args']}) -> {c['result']}")
        if turn.error:
            lines.append(f"    [error] {turn.error}")
    tot = t.totals
    lines += ["", f"Ended: {t.end_reason}" + (f" ({t.end_detail})" if t.end_detail else ""),
              f"Logged actions: {[a['tool'] for a in t.actions] or 'none'}",
              f"Agent: {tot['agent_turns']} turns, {tot['agent_latency_ms']} ms, "
              f"{tot['agent_input_tokens']} in / {tot['agent_output_tokens']} out tokens"]
    return "\n".join(lines)


def main(argv: Optional[list[str]] = None) -> None:
    p = argparse.ArgumentParser(description="Run one simulated call (live API)")
    p.add_argument("--scenario", type=int, default=0)
    p.add_argument("--prompt", default="v1")
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--pool", type=int, default=14, help="scenarios generated before picking one")
    p.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = p.parse_args(argv)

    pool = generate_scenarios(args.pool, args.seed)
    if not 0 <= args.scenario < len(pool):
        p.error(f"--scenario must be 0..{len(pool) - 1}")
    cfg = get_config()
    transcript = simulate(pool[args.scenario], LLMClient.from_config(cfg), load_prompt(args.prompt),
                          cfg.agent_model, cfg.sim_model, PolicyIndex.from_file(), seed=args.seed)
    print(format_transcript(transcript))
    path = transcript.save(args.out, f"{args.prompt}_s{args.scenario}_seed{args.seed}.json")
    print(f"\nSaved: {path}")


if __name__ == "__main__":
    main()
