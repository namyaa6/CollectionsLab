"""A fixture database for the API tests: complete j1 run, partial j2 run, run without metrics."""
from pathlib import Path

from backend import db
from backend.tests.validation_helpers import call_record, run_spec

PERSONAS = ["cooperative", "already_paid", "stalling", "cooperative"]


def _metrics(n_calls: int, n_failed: int) -> dict:
    rate = {"k": 1, "n": 2, "rate": 0.5, "ci_low": 0.1, "ci_high": 0.9}
    rates = {k: rate for k in ("outcome_pass", "judge_task_success", "hallucination",
                               "compliance_violation", "escalation_correct", "policy_violation",
                               "pressure_or_threat")}
    rates["identity_verified"] = {"k": 2, "n": 4, "rate": 0.5, "ci_low": 0.2, "ci_high": 0.8}
    group = {"n_calls": n_calls, "n_failed": n_failed, "rates": rates,
             "lint_per_call": {"total": 1.5}, "tone_avg": 4.0, "turns_per_call": 3.0}
    return {"overall": group, "per_persona": {"cooperative": group}}


def _checks(rec: dict, voice_counts: dict) -> None:
    """Give a validation_helpers record the real checks shape (outcome.outcome, voice_counts)."""
    rec["checks"] = {"outcome": {"passed": True, "outcome": "promise_to_pay"},
                     "voice_counts": voice_counts}


def build_api_db(tmp_path: Path) -> Path:
    """Run 1: v-a, j1, complete (4 ok). Run 2: v-b, j2, partial (n=6; 2 ok + 1 failed stored).
    Run 3: v-c, no metrics. Run 1 call 0 has a self_check on its first agent turn."""
    path = tmp_path / "api.db"
    conn = db.connect(path)
    r1, _ = db.find_or_create_run(conn, run_spec("v-a", "keyAAAAAAAA"))
    for idx, persona in enumerate(PERSONAS):
        rec = call_record("vTESTA", idx, persona)
        _checks(rec, {"filler": 1, "other": idx})
        if idx == 0:
            rec["transcript"]["turns"][0]["self_check"] = {"draft": "Hi draft", "final": "Hi final",
                                                           "issues": []}
        db.save_call(conn, r1, idx, rec)
    db.update_run(conn, r1, 4, _metrics(4, 0))

    r2, _ = db.find_or_create_run(conn, dict(run_spec("v-b", "keyBBBBBBBB"), judge_version="j2"))
    for idx in (0, 1):
        rec = call_record("vTESTB", idx, PERSONAS[idx])
        _checks(rec, {})
        db.save_call(conn, r2, idx, rec)
    db.save_call(conn, r2, 2, {"status": "failed", "error": "agent_error: boom",
                               "scenario": call_record("vTESTB", 2, PERSONAS[2])["scenario"]})
    db.update_run(conn, r2, 6, _metrics(2, 1))

    db.find_or_create_run(conn, run_spec("v-c", "keyCCCCCCCC"))
    conn.close()
    return path
