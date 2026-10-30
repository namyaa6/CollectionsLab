"""Small handmade invoices and transcripts for the eval tests."""
from datetime import date
from typing import Optional

from backend.scenarios.generator import Invoice, Scenario
from backend.sim.transcript import Transcript, Turn

# outstanding = 104902 - 39702 = 65200
INVOICE_DATA = dict(
    invoice_id="INV-2026-1004", company="Rudra Textiles Pvt Ltd", contact_name="Arjun Chauhan",
    amount_inr=104902, gst_inr=16002, due_date=date(2026, 8, 16), days_overdue=78,
    status="partially_paid", amount_paid_inr=39702, dispute_history=[],
    broken_promises=[date(2026, 9, 14), date(2026, 10, 13)])


def make_invoice(**kw) -> Invoice:
    return Invoice(**{**INVOICE_DATA, **kw})


def make_scenario(persona: str = "cooperative", **inv_kw) -> Scenario:
    return Scenario(scenario_id=0, invoice=make_invoice(**inv_kw), persona=persona,
                    expected_outcomes=["promise_to_pay"])


def make_transcript(turns: list[tuple], actions: Optional[list[dict]] = None,
                    persona: str = "cooperative", expected=("promise_to_pay",),
                    scenario: Optional[Scenario] = None, scenario_id: int = 0,
                    seed: int = 42) -> Transcript:
    """turns: (speaker, text) or (speaker, text, tool_calls)."""
    built = [Turn(speaker=t[0], text=t[1], tool_calls=t[2] if len(t) > 2 else []) for t in turns]
    return Transcript(scenario_id=scenario_id, persona=persona, expected_outcomes=list(expected),
                      prompt_version="v1", agent_model="a", sim_model="s", seed=seed,
                      turns=built, actions=actions or [], end_reason="end_call", scenario=scenario)


def action(tool: str, **args) -> dict:
    return {"tool": tool, "args": args, "result": {"status": "logged"}}


JUDGE_OK = {
    "task_success": {"value": True, "evidence": "I will pay"},
    "hallucination": {"value": False, "evidence": ""},
    "compliance_violation": {"value": False, "evidence": ""},
    "escalation_correct": {"value": True, "evidence": ""},
    "identity_verified_before_amounts": {"value": True, "evidence": "am I speaking with"},
    "pressure_or_threat": {"value": False, "evidence": ""},
    "tone": {"score": 5, "evidence": "Thank you"},
}
SUMMARY_OK = {"outcome": "no_resolution", "next_action": "Call again."}


class RoutedFake:
    """Fake LLM client that answers by request kind, so a whole eval run needs no script.

    Kinds: greet (agent's first turn), agent (later turns: end_call), debtor, summary, judge.
    hooks[(kind, k)] overrides the k-th request of that kind (1-based, counted across the
    whole run): an exception is raised, an LLMResponse is returned.
    """

    def __init__(self, hooks: Optional[dict] = None, judge: Optional[dict] = None):
        self.hooks = hooks or {}
        self.judge = judge or JUDGE_OK
        self.counts: dict[str, int] = {}
        self.calls: list[dict] = []

    def kind(self, messages, tools, schema) -> str:
        if tools:
            return "greet" if len(messages) == 1 else "agent"
        if schema is None:
            return "debtor"
        return "judge" if schema.__name__ == "JudgeVerdict" else "summary"

    def generate(self, model, messages, system=None, tools=None, temperature=0.0,
                 json_mode=False, response_schema=None, use_cache=True, cache_salt=None):
        import json

        from backend.llm.fake import text_reply, tool_reply
        from backend.llm.types import parse_structured
        kind = self.kind(messages, tools, response_schema)
        self.counts[kind] = self.counts.get(kind, 0) + 1
        self.calls.append({"kind": kind, "model": model, "messages": list(messages),
                           "system": system})
        hook = self.hooks.get((kind, self.counts[kind]))
        if isinstance(hook, BaseException):
            raise hook
        resp = hook or {
            "greet": lambda: text_reply("Hello, am I speaking with the contact?"),
            "agent": lambda: tool_reply("end_call", {"reason": "done"}, text="Thank you. Bye."),
            "debtor": lambda: text_reply("Yes. I will pay next week."),
            "summary": lambda: text_reply(json.dumps(SUMMARY_OK)),
            "judge": lambda: text_reply(json.dumps(self.judge)),
        }[kind]()
        if response_schema and resp.parsed is None:
            resp.parsed = parse_structured(resp.text, response_schema)
        return resp


def get_invoice_call(invoice: Invoice) -> dict:
    from backend.agent.tools import agent_view
    return {"tool": "get_invoice", "args": {"invoice_id": invoice.invoice_id},
            "result": agent_view(invoice)}
