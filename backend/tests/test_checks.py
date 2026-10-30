import json

from backend.agent.summarizer import summarize_offline
from backend.eval.checks import main, resolve_invoice, run_all_checks
from backend.scenarios.generator import generate_scenarios
from backend.sim.transcript import Transcript
from backend.tests.eval_helpers import (
    action,
    get_invoice_call,
    make_invoice,
    make_scenario,
    make_transcript,
)

PROMISE = action("log_promise_to_pay", date="2026-11-10", amount_inr=65200)
TURNS = [
    ("agent", "Hello, this is Asha. How are you?", []),
    ("debtor", "I can pay on the tenth."),
    ("agent", "Noted, thank you.", [PROMISE]),
]


def old_transcript(invoice, **kw):
    """A transcript saved before M6: no stored scenario, agent called get_invoice."""
    turns = [("agent", "Hi.", [get_invoice_call(invoice)])] + TURNS[1:]
    return make_transcript(turns, actions=[PROMISE], **kw)


# --- invoice resolution -----------------------------------------------------------
def test_stored_scenario_wins_over_everything_else():
    stored = make_scenario(amount_paid_inr=0)  # outstanding differs from the get_invoice result
    t = old_transcript(make_invoice())
    t.scenario = stored
    inv, source, notes = resolve_invoice(t)
    assert source == "stored" and inv.outstanding_inr == stored.invoice.outstanding_inr
    assert notes == []


def test_old_transcript_uses_regenerated_invoice_when_ids_match():
    regenerated = generate_scenarios(14, 42)[0].invoice
    inv, source, notes = resolve_invoice(old_transcript(regenerated))
    assert source == "regenerated" and inv == regenerated
    assert any("No scenario stored" in n for n in notes)


def test_id_mismatch_ignores_regenerated_invoice_and_uses_get_invoice():
    other = make_invoice(invoice_id="INV-2026-9999", amount_paid_inr=0)
    regenerated = generate_scenarios(14, 42)[0].invoice
    assert regenerated.invoice_id != other.invoice_id
    inv, source, notes = resolve_invoice(old_transcript(other))
    assert source == "get_invoice"
    assert inv.invoice_id == "INV-2026-9999" and inv.outstanding_inr == other.outstanding_inr
    assert any("does not match" in n for n in notes)


def test_no_scenario_and_no_get_invoice_skips_invoice_checks():
    t = make_transcript(TURNS, actions=[PROMISE])
    inv, source, notes = resolve_invoice(t)
    assert inv is None and source == "none"
    assert any("cannot be verified" in n for n in notes) and any("skipped" in n for n in notes)
    result = run_all_checks(t, summarize_offline(t))
    assert result.facts is None and result.policy_violations is None
    assert result.outcome.passed and result.invoice_source == "none"


def test_scenario_id_out_of_range_falls_back_cleanly():
    t = old_transcript(make_invoice(), scenario_id=99)
    assert resolve_invoice(t)[1] == "get_invoice"


# --- Transcript storage -------------------------------------------------------------
def test_transcript_round_trips_scenario_and_old_json_still_loads(tmp_path):
    t = make_transcript(TURNS, scenario=make_scenario())
    loaded = Transcript.model_validate_json(t.model_dump_json())
    assert loaded.scenario == t.scenario and loaded.scenario.invoice.outstanding_inr == 65200
    data = json.loads(t.model_dump_json())
    del data["scenario"]
    assert Transcript.model_validate(data).scenario is None


# --- run_all_checks -----------------------------------------------------------------
def test_run_all_checks_end_to_end():
    t = make_transcript([
        ("agent", "You owe ₹65,200. Pay by 10/11. Thanks. Bye.", [
            {"tool": "search_policy", "args": {"query": "promise"}, "result": {"results": []}}]),
        ("debtor", "I can pay on the tenth."),
        ("agent", "Noted for November 10th, 2026.", [PROMISE]),
    ], actions=[PROMISE], scenario=make_scenario())
    r = run_all_checks(t, summarize_offline(t))
    assert r.invoice_source == "stored" and r.summary_llm_used is False
    assert r.voice_counts["symbols_markdown"] == 1 and r.voice_counts["digit_amount"] == 1
    assert r.voice_counts["numeric_date"] == 1 and r.voice_counts["long_turn"] == 1
    assert {v.turn for v in r.voice_violations} == {0}
    # "10/11" in turn 0 is unverified: the debtor only says "the tenth" later.
    assert (r.facts.matched, r.facts.unverified, r.facts.unparsed) == (2, 1, 0)
    assert r.policy_violations == []
    assert r.outcome.passed
    assert (r.retrieval.search_calls, r.retrieval.empty_results) == (1, 1)


def test_explicit_invoice_override_is_reported_as_provided():
    t = make_transcript(TURNS, actions=[PROMISE])
    assert run_all_checks(t, summarize_offline(t), invoice=make_invoice()).invoice_source == "provided"


def test_summarize_offline_needs_no_llm():
    s = summarize_offline(make_transcript(TURNS, actions=[PROMISE]))
    assert s.outcome == "promise_to_pay" and s.llm_used is False and s.discrepancies == []


# --- CLI ------------------------------------------------------------------------------
def test_cli_prints_only_json(tmp_path, capsys):
    path = tmp_path / "t.json"
    path.write_text(make_transcript(TURNS, actions=[PROMISE], scenario=make_scenario())
                    .model_dump_json(), encoding="utf-8")
    main(["--transcript", str(path)])
    printed = json.loads(capsys.readouterr().out)
    assert printed["invoice_source"] == "stored" and printed["outcome"]["passed"] is True
