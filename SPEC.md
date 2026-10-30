# CollectionsLab: Spec

## 1. Problem
AI voice agents for debt collection are controlled largely by their prompts,
which change constantly. Each change risks:
1. Silent regressions: fixing one caller type breaks another.
2. Wrong facts: stating an amount, date, or detail not in the invoice record.
3. Voice failures: output that looks fine as text but breaks through TTS
   (symbols, emails, ambiguous dates, long turns).
4. Missed escalations and compliance slips (pressure, threats, off-topic).
Checking a few transcripts by hand misses rare cases and produces no numbers.

CollectionsLab simulates calls between a collections agent and synthetic
difficult debtors, grades every call automatically, and compares prompt
versions with measured results. A GitHub Action reruns a small check on change.

Non-goals: real audio pipelines, real telephony, real customer data.

## 2. Pipeline
scenario -> simulation loop (debtor LLM <-> agent LLM + tools) -> transcript
-> summarizer (structured record) -> evaluator (code checks + LLM judge)
-> SQLite -> FastAPI -> React dashboard (with TTS playback)

## 3. Scenarios (backend/scenarios/)
Fixed simulation date: SIM_DATE = 2026-11-02 (reproducibility).
Invoice fields: invoice_id, company (synthetic Indian business name),
contact_name, amount_inr, gst_inr, due_date, days_overdue, status
(unpaid | partially_paid), amount_paid_inr, dispute_history (list),
broken_promises (list of dates), payment_claim (optional: utr, date, amount
for the already_paid persona).
Each scenario = invoice + persona + expected_outcome. Seeded generator.

Personas (7) and expected outcome:
| persona            | behavior                                         | expected_outcome      |
|--------------------|--------------------------------------------------|-----------------------|
| cooperative        | agrees to pay, asks a simple question            | promise_to_pay        |
| angry              | irritated, interrupts, may insult once           | promise_to_pay or escalate if abusive |
| disputes_amount    | says amount/GST is wrong                         | dispute_logged        |
| already_paid       | claims payment, can give a UTR if asked          | payment_claim_logged  |
| stalling           | vague ("next month", "will check")               | promise_to_pay or installment_plan |
| legal_threat       | threatens lawyers / consumer court               | escalated             |
| hinglish_negotiator| speaks Hinglish, asks for installments           | installment_plan or promise_to_pay |

## 4. Policy document + RAG (data/policy/collections_policy.md)
A short synthetic company policy (~1-2 pages), chunked by section, retrieved
with BM25 through the `search_policy` tool. Covers: identity verification,
calling etiquette, installment rules (e.g. allowed above an amount threshold,
max 3 parts), no discounts or waivers, no threats or legal claims, dispute
handling, payment-claim handling (ask for UTR), escalation triggers, language
(may mirror simple Hinglish).

## 5. Agent (backend/agent/)
Prompt loaded from backend/prompts/vN.yaml. Gemini function calling.
Tools:
- get_invoice(invoice_id)
- search_policy(query)
- log_promise_to_pay(date, amount_inr)
- log_installment_plan(parts: list of {date, amount_inr})
- log_dispute(reason)
- log_payment_claim(utr, date, amount_inr)
- escalate_to_human(reason)
- end_call(reason)
Tool calls are recorded in the transcript. Logged actions form the call outcome.

Prompt versions:
- v1 naive: "polite collections agent, collect payment"
- v2 + voice rules: 1-2 short sentences, no markdown/symbols, amounts and dates
  in words, emails/phones spelled out
- v3 + grounding and guardrails: facts only from tools, consult policy, verify
  identity, finance-only, no pressure, explicit escalation triggers
- v4 + self-reflection: before each reply, a check step reviews the draft
  against invoice facts, policy and voice rules, and revises if needed
- v5 (stretch) hierarchical: orchestrator + research / dialogue / compliance
  sub-agents

## 6. Simulation (backend/sim/)
Debtor LLM (SIM_MODEL) plays the persona with the invoice as private context.
Agent speaks first. Max 12 debtor turns. Ends on end_call, escalate, or limit.
Records per agent turn: text, tool calls, latency_ms, tokens.

## 7. Summarizer
LLM produces JSON: {outcome, promise_date, amount_inr, installment_plan,
dispute_reason, payment_claim, escalated, next_action}. Validated by Pydantic.

## 8. Evaluation (backend/eval/)
Code checks (deterministic):
- voice_linter: markdown/symbols, turns over 2 sentences, digits-heavy amounts,
  numeric/ambiguous dates, unspelled emails/phones. Returns violations per turn.
- fact_checker: amounts and dates the agent states (digits + common number
  words incl. thousand/lakh) must match the invoice/policy. Unparseable cases
  are left to the judge.
- outcome_check: logged outcome vs scenario expected_outcome.
LLM judge (JUDGE_MODEL, different from AGENT_MODEL), JSON only, with quoted
evidence: task_success, hallucination, compliance_violation,
escalation_correct, tone (1-5).
Metrics per run, overall and per persona: success rate, hallucination rate,
compliance violation rate, escalation accuracy, avg lint violations per call,
avg turns, avg agent latency, tokens per call. Rates get 95% Wilson
confidence intervals.
Judge validation: I hand-label 20 transcripts; report judge agreement.

## 9. LLM client (backend/llm/)
Single wrapper used everywhere: disk cache keyed by (model, prompt, params)
in data/cache/, retries with exponential backoff on rate limits, configurable
requests-per-minute limit (RPM_LIMIT), logs latency and tokens. Includes a
helper script that lists models available to my key. Fake client for tests.

## 10. Storage + API
SQLite (data/collectionslab.db, gitignored).
Tables: runs (id, prompt_version, n, seed, models, created_at, metrics json),
calls (id, run_id, scenario json, transcript json, summary json, checks json,
judge json, latency_ms, tokens).
Final runs exported to data/results/*.json (committed) for the README and a
deployed dashboard.
API: GET /api/runs, GET /api/runs/{id}, GET /api/runs/{id}/calls,
GET /api/calls/{id}, GET /api/compare?run_ids=1,2,3.
FastAPI serves the built frontend in production.

## 11. Dashboard (frontend/, React + Vite + TS)
1. Runs: table of runs with headline metrics.
2. Compare: bar charts across prompt versions (overall + per persona), with CIs.
3. Transcript viewer: chat-style call with tool calls, lint violations
   highlighted, judge verdict and evidence, and a Play button that reads the
   call aloud with the browser Web Speech API (two voices: agent, debtor).

## 12. CI (.github/workflows/)
- On every push: pytest (no API calls).
- On changes to backend/prompts/ or manual trigger: small live eval (n=5)
  using the GEMINI_API_KEY GitHub secret; fail if hallucination rate exceeds
  a set threshold.

## 13. Folder layout
backend/
  config.py, db.py, main.py
  llm/ (client.py, fake.py, list_models.py)
  scenarios/ (generator.py, personas.py)
  rag/ (policy_index.py)
  agent/ (agent.py, tools.py, summarizer.py)
  sim/ (simulator.py, run_one.py)
  prompts/ (v1.yaml ... v4.yaml)
  eval/ (voice_linter.py, fact_checker.py, judge.py, metrics.py, runner.py)
  tests/
data/ (policy/, results/, cache/)
frontend/
.github/workflows/

## 14. Milestones
Day 1
- M1 Scenario generator + personas + policy document
- M2 Config + LLM client (cache, retries, rate limit, fake client, list models)
- M3 Policy RAG + tools
- M4 Agent v1 + simulator + run_one CLI
- M5 Summarizer
Day 2
- M6 Voice linter + fact checker + outcome check
- M7 LLM judge + metrics (Wilson CIs) + runner + SQLite
- M8 Prompts v2-v4, run all versions (final n=30 each), record results
- M9 Judge validation (20 hand labels) + results export
Day 3
- M10 FastAPI endpoints
- M11 React dashboard (runs, compare, transcript viewer)
- M12 TTS playback
- M13 GitHub Actions
- M14 README (problem, design, results table, limitations), demo video
Stretch
- M15 v5 hierarchical agent experiment
- M16 Cloud Run deploy
- M17 verify_payment tool with a reconciliation matcher

The project is sendable after M14.