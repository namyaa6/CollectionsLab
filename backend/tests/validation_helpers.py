"""A small fixture database for the judge-validation tests (labels, agreement, export)."""
import copy
from pathlib import Path

from backend import db
from backend.agent.tools import agent_view
from backend.tests.eval_helpers import JUDGE_OK, get_invoice_call, make_scenario, make_transcript

VERSIONS = {"vTESTA": "runkeyAAAAAAAA", "vTESTB": "runkeyBBBBBBBB"}
PERSONAS = ["cooperative", "already_paid", "stalling", "cooperative"]
UTR = "987654321098"


def invoice_id(version: str, idx: int) -> str:
    """Opaque on purpose: the invoice id is shown to labellers, so it must not hint at the version."""
    slot = list(VERSIONS).index(version) if version in VERSIONS else 9
    return f"INV-{slot * 100 + idx:04d}"


def verdict(idx: int) -> dict:
    v = copy.deepcopy(JUDGE_OK)
    v["task_success"]["value"] = idx % 2 == 0
    v["tone"]["score"] = 3 + idx % 3
    return v


def run_spec(version: str, run_key: str, judge_model: str = "judge-m") -> dict:
    return {"run_key": run_key, "prompt_version": version, "prompt_hash": "h", "judge_version": "j1",
            "judge_prompt_hash": "jh", "seed": 42, "pool_hash": "p", "scenarios": [],
            "models": {"agent": "a", "sim": "s", "judge": judge_model}}


def call_record(version: str, idx: int, persona: str) -> dict:
    claim = {"utr": UTR, "date": "2026-10-01", "amount_inr": 5000}
    scenario = make_scenario(persona, invoice_id=invoice_id(version, idx),
                             **({"payment_claim": claim} if persona == "already_paid" else {}))
    transcript = make_transcript(
        [("agent", "Hello, am I speaking with Arjun Chauhan?", [get_invoice_call(scenario.invoice)]),
         ("debtor", "Yes, go ahead."),
         ("agent", f"Your balance is 65200 rupees. Call number {idx}.")],
        persona=persona, scenario=scenario, scenario_id=idx)
    return {"status": "ok", "scenario": scenario.model_dump(mode="json"),
            "transcript": transcript.model_dump(mode="json"), "summary": {"outcome": "x"},
            "checks": {"outcome": {"passed": True}},
            "judge": {"verdict": verdict(idx), "evidence_found": {}, "judge_version": "j1",
                      "error": None}}


def build_db(tmp_path: Path, judge_model: str = "judge-m") -> tuple[Path, dict]:
    """Two runs (vTESTA, vTESTB) x 4 calls. Returns (db path, {key: invoice_id})."""
    path = tmp_path / "t.db"
    conn = db.connect(path)
    keys = {}
    for version, run_key in VERSIONS.items():
        run_id, _ = db.find_or_create_run(conn, run_spec(version, run_key, judge_model))
        for idx, persona in enumerate(PERSONAS):
            db.save_call(conn, run_id, idx, call_record(version, idx, persona))
            keys[f"{run_key}:{idx}"] = invoice_id(version, idx)
        db.update_run(conn, run_id, len(PERSONAS), {"overall": {"n_calls": 4, "n_failed": 0}})
    conn.close()
    return path, keys


def invoice_view(version: str, idx: int) -> dict:
    return agent_view(make_scenario(PERSONAS[idx], invoice_id=invoice_id(version, idx)).invoice)
