"""Re-judge the hand-labelled sample with a second judge model (live API when you run it):

    python -m backend.eval.cross_judge --judge-model <model>

Results go to data/labels/cross_judge_<model>.json, never into the eval database, so the
main verdicts are untouched. Saved after every call; rerun to continue after a quota stop.
"""
import argparse
import re
import sys
from pathlib import Path
from typing import Callable, Optional

from backend.config import Config
from backend.eval.judge import judge_call, load_judge_prompt
from backend.eval.validation import (LABELS_PATH, SAMPLE_SIZE, fetch_call, load_json,
                                     load_ok_calls, open_readonly, sample_calls, save_json, say)
from backend.llm.client import LLMClientProtocol
from backend.llm.types import QuotaExhaustedError
from backend.rag.policy_index import DEFAULT_POLICY_PATH
from backend.scenarios.generator import Scenario
from backend.sim.transcript import Transcript


def output_path(labels: Path, model: str) -> Path:
    return labels.parent / f"cross_judge_{re.sub(r'[^A-Za-z0-9._-]', '_', model)}.json"


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    from backend.db import DEFAULT_DB
    p = argparse.ArgumentParser(description="Cross-judge check on the labelled sample")
    p.add_argument("--judge-model", required=True)
    p.add_argument("--db", type=Path, default=DEFAULT_DB)
    p.add_argument("--labels", type=Path, default=LABELS_PATH)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--n", type=int, default=SAMPLE_SIZE)
    p.add_argument("--yes", action="store_true", help="skip the confirmation")
    return p.parse_args(argv)


def sample_keys(labels: Path, conn, n: int, seed: int) -> list[str]:
    """The hand-labelled sample if it exists, else the same seeded draw label.py would make."""
    data = load_json(labels)
    if data:
        return data["sample"]
    return [c["key"] for c in sample_calls(load_ok_calls(conn), n, seed)]


def main(argv: Optional[list[str]] = None, cfg: Optional[Config] = None,
         client: Optional[LLMClientProtocol] = None,
         input_fn: Callable[[str], str] = input, out: Callable[[str], None] = say) -> int:
    args = parse_args(argv)
    conn = open_readonly(args.db)
    keys = sample_keys(args.labels, conn, args.n, args.seed)
    path = output_path(args.labels, args.judge_model)
    stored = load_json(path, {"judge_model": args.judge_model, "results": {}})
    todo = [k for k in keys if not (stored["results"].get(k) or {}).get("verdict")]
    out(f"Sample: {len(keys)} calls. Already judged by {args.judge_model}: "
        f"{len(keys) - len(todo)}. Live requests needed: {len(todo)} (one per call).")
    if not todo:
        return 0
    if not args.yes:
        try:
            answer = input_fn(f"Make {len(todo)} live requests to {args.judge_model}? [y/N] ")
        except EOFError:
            answer = ""
        if answer.strip().lower() not in ("y", "yes"):
            out("Aborted. No calls were made.")
            return 1
    if client is None:
        from backend.config import get_config
        from backend.llm.client import LLMClient
        client = LLMClient.from_config(cfg or get_config())
    prompt, policy = load_judge_prompt(), DEFAULT_POLICY_PATH.read_text(encoding="utf-8")
    for k, key in enumerate(todo, 1):
        call = fetch_call(conn, key)
        if call is None:
            out(f"[{k}/{len(todo)}] {key[:8]}: missing from the database, skipped")
            continue
        transcript = Transcript.model_validate(call["transcript"])
        invoice = Scenario.model_validate(call["scenario"]).invoice
        try:
            result = judge_call(transcript, invoice, client, args.judge_model, prompt, policy)
        except QuotaExhaustedError as exc:
            out(f"Stopped: {exc}\nProgress saved. Rerun the same command to continue.")
            return 2
        stored["results"][key] = result
        save_json(path, stored)
        out(f"[{k}/{len(todo)}] judged" + (f" - {result['error']}" if result["error"] else ""))
    out(f"Saved to {path}\nNext: python -m backend.eval.agreement --cross {path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
