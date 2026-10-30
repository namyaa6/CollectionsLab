"""Resumable eval run: python -m backend.eval.runner --prompt v1 --n 5 --seed 42

A run is identified by its settings (prompt file, judge prompt, models, seed, scenario
pool), not by n. Rerunning the same command continues where it stopped; a larger --n
extends the run; a smaller --n only reports. Completed calls are never re-run, and
failed calls only with --retry-failed.
"""
import argparse
import hashlib
import json
import sys
from pathlib import Path
from typing import Callable, Optional

from backend import db
from backend.config import Config, get_config
from backend.eval.judge import JudgePrompt, load_judge_prompt
from backend.eval.metrics import compute_metrics
from backend.eval.pipeline import evaluate_call, failed_record
from backend.eval.report import format_metrics
from backend.llm.client import LLMClientProtocol
from backend.llm.types import QuotaExhaustedError
from backend.prompts import load_prompt, prompt_file_hash
from backend.rag.policy_index import DEFAULT_POLICY_PATH, PolicyIndex
from backend.scenarios.generator import POOL_SIZE, scenario_pool

CONFIRM_ABOVE = 100  # estimated requests
# No calls measured yet: 12 debtor turns + 13 agent turns x ~1.5 model calls + summary + judge.
DEFAULT_REQUESTS_PER_CALL = 34
MAX_CONSECUTIVE_FAILURES = 3
EXIT_ABORTED, EXIT_QUOTA, EXIT_FAILURES, EXIT_INTERRUPTED = 1, 2, 3, 130


def _say(text: str) -> None:
    print(text.encode("ascii", "replace").decode("ascii"))  # Windows consoles can't print the rupee sign


def _sha(obj) -> str:
    return hashlib.sha256(json.dumps(obj, sort_keys=True).encode("utf-8")).hexdigest()


def build_spec(prompt_version: str, seed: int, models: dict, judge: JudgePrompt) -> dict:
    pool = [s.model_dump(mode="json") for s in scenario_pool(seed)]
    spec = {"prompt_version": prompt_version, "prompt_hash": prompt_file_hash(prompt_version),
            "judge_version": judge.version, "judge_prompt_hash": judge.file_hash,
            "seed": seed, "models": models, "scenarios": pool, "pool_hash": _sha(pool)}
    key_fields = ("prompt_version", "prompt_hash", "judge_prompt_hash", "seed", "models", "pool_hash")
    spec["run_key"] = _sha({k: spec[k] for k in key_fields})  # n is deliberately not part of it
    return spec


def requests_per_call(calls: list[dict]) -> float:
    """Measured from stored transcripts (model calls per turn + summary + judge), else the default."""
    seen = [sum(t["llm_calls"] for t in c["transcript"]["turns"]) + 2
            for c in calls if c.get("transcript")]
    return sum(seen) / len(seen) if seen else DEFAULT_REQUESTS_PER_CALL


def confirm(estimate: int, assume_yes: bool, input_fn: Callable[[str], str]) -> bool:
    _say(f"Estimated LLM requests: ~{estimate} (cache hits make it lower).")
    if estimate <= CONFIRM_ABOVE or assume_yes:
        return True
    try:
        answer = input_fn(f"That is over {CONFIRM_ABOVE}. Continue? [y/N] ")
    except EOFError:
        answer = ""
    return answer.strip().lower() in ("y", "yes")


def _stopped(conn, run_id: int, n: int, why: str, resume_cmd: str) -> None:
    stored = sum(1 for i in db.call_statuses(conn, run_id) if i < n)
    _say(f"\n{why}\nProgress saved: {stored}/{n} calls stored. To continue, rerun:\n  {resume_cmd}")


def parse_args(argv: Optional[list[str]]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Resumable eval run (live API)")
    p.add_argument("--prompt", default="v1")
    p.add_argument("--n", type=int, default=5)
    p.add_argument("--seed", type=int, default=42)
    p.add_argument("--yes", action="store_true", help="skip the request-count confirmation")
    p.add_argument("--retry-failed", action="store_true", help="rerun only failed calls")
    p.add_argument("--db", type=Path, default=db.DEFAULT_DB)
    args = p.parse_args(argv)
    if not 1 <= args.n <= POOL_SIZE:
        p.error(f"--n must be 1..{POOL_SIZE} (the scenario pool size)")
    return args


def main(argv: Optional[list[str]] = None, cfg: Optional[Config] = None,
         client: Optional[LLMClientProtocol] = None,
         input_fn: Callable[[str], str] = input) -> int:
    args = parse_args(argv)
    cfg = cfg or get_config()
    if client is None:
        from backend.llm.client import LLMClient
        client = LLMClient.from_config(cfg)
    if cfg.judge_model == cfg.agent_model:
        _say("WARNING: JUDGE_MODEL equals AGENT_MODEL; the judge is grading its own model.")
    prompt, judge = load_prompt(args.prompt), load_judge_prompt()
    models = {"agent": cfg.agent_model, "sim": cfg.sim_model, "judge": cfg.judge_model}
    spec = build_spec(args.prompt, args.seed, models, judge)
    pool = scenario_pool(args.seed)

    conn = db.connect(args.db)
    run_id, created = db.find_or_create_run(conn, spec)
    statuses = db.call_statuses(conn, run_id)
    wanted = "failed" if args.retry_failed else None
    todo = [i for i in range(args.n) if statuses.get(i) == wanted]
    n_ok = sum(1 for i, s in statuses.items() if i < args.n and s == "ok")
    _say(f"Run #{run_id} ({'new' if created else 'existing'}): prompt {args.prompt}, seed "
         f"{args.seed}, n={args.n}. Stored: {n_ok} ok, "
         f"{sum(1 for i, s in statuses.items() if i < args.n and s == 'failed')} failed. "
         f"To run now: {len(todo)}.")
    base_cmd = f"python -m backend.eval.runner --prompt {args.prompt} --n {args.n} --seed {args.seed}"
    resume_cmd = base_cmd + (" --retry-failed" if args.retry_failed else "")

    if todo:
        estimate = round(len(todo) * requests_per_call(db.get_calls(conn, run_id)))
        if not confirm(estimate, args.yes, input_fn):
            _say("Aborted. No calls were made.")
            return EXIT_ABORTED
        db.set_requested_n(conn, run_id, args.n)  # after confirm, before any call
        index, policy_text = PolicyIndex.from_file(), DEFAULT_POLICY_PATH.read_text(encoding="utf-8")
        in_a_row = 0
        for k, idx in enumerate(todo, 1):
            scenario = pool[idx]
            try:
                record = evaluate_call(scenario, client, prompt, models, index, judge,
                                       policy_text, args.seed)
            except QuotaExhaustedError as exc:
                _stopped(conn, run_id, args.n, f"Stopped: {exc}\nGemini daily quotas reset at "
                         "midnight Pacific time. (A different model in .env starts a new run.)",
                         resume_cmd)
                return EXIT_QUOTA
            except KeyboardInterrupt:
                _stopped(conn, run_id, args.n, "Interrupted.", resume_cmd)
                return EXIT_INTERRUPTED
            except Exception as exc:  # store it and move on; see MAX_CONSECUTIVE_FAILURES
                record = failed_record(scenario, f"{type(exc).__name__}: {exc}")
            db.save_call(conn, run_id, idx, record)
            outcome = (record.get("checks") or {}).get("outcome") or {}
            _say(f"[{k}/{len(todo)}] call {idx} {scenario.persona}: {record['status']}"
                 + (f", outcome {outcome['outcome']} ({'pass' if outcome['passed'] else 'fail'})"
                    if outcome else "") + (f" - {record['error']}" if record["error"] else ""))
            in_a_row = in_a_row + 1 if record["status"] == "failed" else 0
            if in_a_row >= MAX_CONSECUTIVE_FAILURES:
                _stopped(conn, run_id, args.n, f"Stopped after {in_a_row} failed calls in a row: "
                         "likely a bug or an outage, not a bad call.", resume_cmd)
                return EXIT_FAILURES

    db.update_run(conn, run_id, args.n, compute_metrics(db.get_calls(conn, run_id)))
    metrics = compute_metrics(db.get_calls(conn, run_id, max_idx=args.n))
    run_n = db.get_run(conn, run_id)["n"]
    if run_n > args.n:
        _say(f"Note: this run holds {run_n} calls; showing the first {args.n}.")
    _say("\n" + format_metrics(metrics))
    if metrics["overall"]["n_failed"]:
        _say(f"\n{metrics['overall']['n_failed']} failed call(s) excluded. Retry them with:\n  "
             f"{base_cmd} --retry-failed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
