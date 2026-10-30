import pytest

from backend import db
from backend.config import Config
from backend.eval import runner
from backend.llm.fake import text_reply
from backend.llm.types import QuotaExhaustedError
from backend.tests.eval_helpers import RoutedFake

CFG = Config(gemini_api_key="x", agent_model="agent-m", sim_model="sim-m",
             judge_model="judge-m", rpm_limit=10)


def no_input(prompt):
    raise AssertionError("should not ask for confirmation")


@pytest.fixture
def run(tmp_path):
    path = tmp_path / "t.db"

    def _run(*args, client=None, input_fn=no_input):
        client = client or RoutedFake()
        code = runner.main(["--db", str(path), "--prompt", "v1", "--seed", "42", *args],
                           cfg=CFG, client=client, input_fn=input_fn)
        return code, client
    _run.path = path
    return _run


def stored(path):
    conn = db.connect(path)
    run_ids = [r["id"] for r in conn.execute("SELECT id FROM runs")]
    calls = {rid: db.get_calls(conn, rid) for rid in run_ids}
    runs = {rid: db.get_run(conn, rid) for rid in run_ids}
    conn.close()
    return runs, calls


def started(client):  # one "greet" request per simulated call
    return client.counts.get("greet", 0)


def test_full_run_stores_calls_metrics_and_prints_table(run, capsys):
    code, client = run("--n", "3", "--yes")
    assert code == 0 and started(client) == 3 and len(client.calls) == 15  # 5 requests per call
    runs, calls = stored(run.path)
    (rid, r), = runs.items()
    assert [c["idx"] for c in calls[rid]] == [0, 1, 2]
    assert all(c["status"] == "ok" and c["judge"]["verdict"] for c in calls[rid])
    assert r["n"] == 3 and r["metrics"]["overall"]["n_calls"] == 3
    assert r["models"] == {"agent": "agent-m", "sim": "sim-m", "judge": "judge-m"}
    assert len(r["scenarios"]) == 28 and len(r["pool_hash"]) == 64 and len(r["prompt_hash"]) == 64
    assert {c["model"] for c in client.calls if c["kind"] == "judge"} == {"judge-m"}
    out = capsys.readouterr().out
    assert "== Overall ==" in out and "3 ok, 0 failed" in out


def test_resume_after_ctrl_c_runs_only_unfinished_calls(run, capsys):
    code, _ = run("--n", "3", "--yes", client=RoutedFake({("judge", 2): KeyboardInterrupt()}))
    assert code == runner.EXIT_INTERRUPTED
    assert "Progress saved: 1/3" in capsys.readouterr().out
    code, client = run("--n", "3", "--yes")
    assert code == 0 and started(client) == 2  # calls 1 and 2 only
    _, calls = stored(run.path)
    (cs,) = calls.values()
    assert [c["idx"] for c in cs] == [0, 1, 2]


def test_interrupted_run_records_requested_n_without_metrics_and_key_is_stable(run):
    run("--n", "3", "--yes", client=RoutedFake({("judge", 2): KeyboardInterrupt()}))
    runs, _ = stored(run.path)
    (rid, r), = runs.items()
    assert r["n"] == 3 and r["metrics"] is None
    key = r["run_key"]
    run("--n", "3", "--yes")
    runs, _ = stored(run.path)
    assert list(runs.values())[0]["run_key"] == key and len(runs) == 1


def test_extending_run_records_new_n_before_calls(run):
    run("--n", "2", "--yes")
    run("--n", "4", "--yes", client=RoutedFake({("greet", 2): KeyboardInterrupt()}))
    (r,) = stored(run.path)[0].values()
    assert r["n"] == 4


def test_declined_confirmation_does_not_record_n(run):
    run("--n", "5", input_fn=lambda _: "n")
    (r,) = stored(run.path)[0].values()
    assert r["n"] == 0


def test_quota_exhausted_saves_progress_and_exits_cleanly(run, capsys):
    quota = QuotaExhaustedError("Daily quota exhausted for model 'agent-m'.")
    code, _ = run("--n", "3", "--yes", client=RoutedFake({("greet", 2): quota}))
    out = capsys.readouterr().out
    assert code == runner.EXIT_QUOTA
    assert "Progress saved: 1/3" in out and "midnight Pacific" in out
    assert "python -m backend.eval.runner --prompt v1 --n 3 --seed 42" in out
    code, client = run("--n", "3", "--yes")
    assert code == 0 and started(client) == 2


def test_completed_run_rerun_makes_no_requests(run):
    run("--n", "2")
    code, client = run("--n", "2")
    assert code == 0 and client.calls == []


def test_larger_n_extends_same_run_smaller_n_only_reports(run, capsys):
    run("--n", "2")
    code, client = run("--n", "4")
    assert code == 0 and started(client) == 2
    runs, calls = stored(run.path)
    assert len(runs) == 1 and [c["idx"] for c in calls[next(iter(runs))]] == [0, 1, 2, 3]
    capsys.readouterr()
    code, client = run("--n", "2")
    out = capsys.readouterr().out
    assert code == 0 and client.calls == []
    assert "holds 4 calls; showing the first 2" in out and "2 ok, 0 failed" in out
    assert stored(run.path)[0][next(iter(runs))]["n"] == 4


def test_changed_prompt_file_starts_a_new_run(run, monkeypatch):
    run("--n", "1")
    monkeypatch.setattr(runner, "prompt_file_hash", lambda v: "edited")
    code, client = run("--n", "1")
    assert code == 0 and started(client) == 1 and len(stored(run.path)[0]) == 2


def test_big_estimate_asks_and_declining_makes_no_requests(run, capsys):
    code, client = run("--n", "5", input_fn=lambda p: "n")  # 5 x 34 = 170 > 100
    assert code == runner.EXIT_ABORTED and client.calls == []
    assert "~170" in capsys.readouterr().out

    def eof(prompt):
        raise EOFError
    assert run("--n", "5", input_fn=eof)[0] == runner.EXIT_ABORTED
    code, client = run("--n", "5", input_fn=lambda p: "y")
    assert code == 0 and started(client) == 5


def test_yes_flag_skips_confirmation(run):
    code, client = run("--n", "5", "--yes")
    assert code == 0 and started(client) == 5


def test_small_estimate_does_not_ask(run):
    assert run("--n", "2")[0] == 0  # 68 requests: no_input would raise


def test_failed_calls_are_stored_skipped_and_retried(run, capsys):
    hooks = {("greet", 1): RuntimeError("boom"), ("greet", 2): text_reply("")}
    code, client = run("--n", "3", "--yes", client=RoutedFake(hooks))
    assert code == 0 and started(client) == 3  # the run went on past both failures
    (rid, r), = stored(run.path)[0].items()
    cs = stored(run.path)[1][rid]
    assert [c["status"] for c in cs] == ["failed", "failed", "ok"]
    assert cs[0]["error"] == "RuntimeError: boom" and cs[0]["transcript"] is None
    assert cs[1]["error"].startswith("agent_error") and cs[1]["transcript"]
    assert r["metrics"]["overall"]["n_calls"] == 1 and r["metrics"]["overall"]["n_failed"] == 2
    assert "--retry-failed" in capsys.readouterr().out

    assert run("--n", "3", "--yes")[1].calls == []  # failed calls are not rerun by default
    code, client = run("--n", "3", "--yes", "--retry-failed")
    assert code == 0 and started(client) == 2
    cs = stored(run.path)[1][rid]
    assert [c["status"] for c in cs] == ["ok", "ok", "ok"] and len(cs) == 3


def test_unusable_judge_reply_fails_the_call(run):
    code, _ = run("--n", "1", client=RoutedFake({("judge", 1): text_reply("not json")}))
    (cs,) = stored(run.path)[1].values()
    assert code == 0 and cs[0]["status"] == "failed" and "judge" in cs[0]["error"]
    assert cs[0]["checks"] and cs[0]["judge"]["verdict"] is None


def test_three_failures_in_a_row_stop_the_run(run, capsys):
    hooks = {("greet", k): RuntimeError("down") for k in (1, 2, 3)}
    code, client = run("--n", "5", "--yes", client=RoutedFake(hooks))
    assert code == runner.EXIT_FAILURES and started(client) == 3
    assert "3 failed calls in a row" in capsys.readouterr().out


def test_n_must_fit_the_pool(run):
    with pytest.raises(SystemExit):
        run("--n", "29")


def test_warns_when_judge_is_agent_model(tmp_path, capsys):
    cfg = Config(gemini_api_key="x", agent_model="same", sim_model="s", judge_model="same",
                 rpm_limit=10)
    runner.main(["--db", str(tmp_path / "t.db"), "--n", "1"], cfg=cfg, client=RoutedFake(),
                input_fn=no_input)
    assert "WARNING: JUDGE_MODEL equals AGENT_MODEL" in capsys.readouterr().out
