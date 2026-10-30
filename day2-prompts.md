# Day 2 milestone prompts (M6-M9)

Same routine for each: /clear -> Plan mode -> paste -> review plan -> approve
-> pytest -q -> live check (if any) -> interview notes -> commit.

---

## M6: Deterministic checks (no LLM calls)

Read CLAUDE.md and SPEC.md section 8. Milestone 6 only. No LLM calls at all.

Build in backend/eval/:

1. voice_linter.py: check every AGENT turn's spoken text. Return a list of
   violations: {turn, category, snippet}. Categories:
   - symbols_markdown: currency symbols (e.g. the rupee sign), *, #, bullets,
     %, slashes, emojis, markdown
   - long_turn: more than 2 sentences, or multiple paragraphs
   - digit_amount: amounts written as digits (e.g. "65,200")
   - numeric_date: dates in digits (2026-11-10, 10/11/2026, 10/11)
   - code_token: codes like INV-2026-1004 read out as-is
   - unspelled_contact: emails or phone numbers not spelled out
   Each category must be a separate, tested function.

2. fact_checker.py: extract every amount and date the agent SAYS (digits,
   "65,200", "Rs 65,200", number words including thousand/lakh such as
   "sixty-five thousand two hundred", dates like "November 10th, 2026",
   "10 November", "the tenth") and classify each as:
   - matched: equals an invoice fact (amount, outstanding, paid, GST, due date,
     days overdue, broken promise dates), a policy constant (threshold,
     promise window, max parts, 60 days), SIM_DATE, or a value the DEBTOR said
     earlier in the call
   - unverified: not matched (possible hallucination; the judge decides)
   - unparsed: looked like a number/date but could not be parsed
   Return counts and the list with turn and snippet.

3. policy_check.py: deterministic policy checks from logged actions:
   - installment plan only when outstanding > threshold, at most 3 parts,
     parts sum exactly to outstanding, last part within 60 days of SIM_DATE
   - promise date within PROMISE_WINDOW_DAYS of SIM_DATE, amount == outstanding
   - no promise_to_pay logged on a dispute or payment-claim call
   Return a list of violations with the rule name.

4. outcome_check.py: pass if the summary's outcome is in the scenario's
   expected_outcomes AND logged_outcomes has no forbidden combination.

5. retrieval_stats.py: count search_policy calls, empty results, and the
   queries used, per call.

6. checks.py: run_all_checks(transcript, summary) -> one Pydantic CheckResult.

7. CLI: python -m backend.eval.checks --transcript <path> prints the results
   (uses the saved summary, or runs the summarizer only if I pass --summarize).

Tests for every category and rule with small handmade transcripts, including
false-positive tests (e.g. "sixty-five thousand two hundred rupees" must NOT
be a digit_amount; a date the debtor proposed must be "matched").
Then run the CLI on data/transcripts/v1_s0_seed42.json and report exactly what
it prints. Plan first.

---

## M7: LLM judge + metrics + runner + SQLite

Read CLAUDE.md and SPEC.md sections 8 and 10. Milestone 7 only.

1. backend/eval/judge.py: one JUDGE_MODEL call per transcript with
   response_schema. The judge sees: the policy text, the agent-visible invoice,
   the full transcript including tool calls. It does NOT see the deterministic
   check results (independent reading). Fields, each with a short quoted
   evidence string from the transcript:
   task_success, hallucination, compliance_violation, escalation_correct,
   identity_verified_before_amounts, pressure_or_threat, tone (1-5).
   Judge prompt lives in backend/eval/judge_prompt.yaml (versioned).

2. backend/eval/metrics.py: per run and per persona: rates with 95% Wilson
   confidence intervals (outcome_check pass, judge task_success,
   hallucination, compliance violation, escalation accuracy, identity
   verified, pressure), avg lint violations per call by category, unverified
   facts per call, policy_check violations, avg turns, avg agent latency
   EXCLUDING cached turns, tokens per call, retrieval empty-result rate.

3. backend/db.py: SQLite (data/collectionslab.db). Tables runs and calls as in
   SPEC section 10. Each run stores the exact scenario list it used (JSON) and
   its hash, the models, prompt version, prompt file hash and seed.

4. backend/eval/runner.py:
   python -m backend.eval.runner --prompt v1 --n 5 --seed 42
   - Before starting: print an estimated request count and ask for
     confirmation if it exceeds 100 (flag --yes to skip).
   - RESUMABLE: if a run is interrupted (quota, crash, Ctrl+C), rerunning the
     same command continues from the first unfinished call. Completed calls
     are never re-run.
   - On QuotaExhaustedError: save progress, print how many calls are done and
     when to resume, exit cleanly.
   - At the end print the metrics table.

Tests with the fake client only, including resume after an interruption and
quota-exhausted handling. Then one live run with --n 2. Plan first.

---

## M8: Prompt versions v2-v4

Read CLAUDE.md, SPEC.md section 5, and my LEARNINGS.md (v1 failures).
Milestone 8. Write prompts only; DO NOT run any evaluations.

- v2.yaml = v1 + voice rules: 1-2 short sentences per turn, no symbols or
  markdown, amounts and dates in words, spell out codes/emails/phones.
- v3.yaml = v2 + grounding and guardrails: verify identity and WAIT for
  confirmation before any amount; facts only from get_invoice; consult
  search_policy for installment/promise/dispute rules. The safety-critical
  rules go directly in the prompt (they must not depend on retrieval):
  escalate only for legal threats or continued abuse, no discounts or
  waivers, no threats or pressure, ask for the UTR on payment claims and do
  not ask for payment again.
- v4 = v3 + self-reflection: before each spoken reply, a check step reviews
  the draft against the invoice facts, policy and voice rules and revises it
  if needed. Implement it in the agent as an optional step enabled by the
  prompt file (e.g. self_check: true), recording both draft and final text
  and the extra latency/tokens. Add fake-client tests.

Show me all three prompts before anything else. Each version changes ONE
category of thing compared with the previous one, so improvements can be
attributed.

---

## M9: Judge validation + results export

Milestone 9.

1. backend/eval/label.py: a CLI that shows me one transcript at a time
   (readable), asks me y/n for each judge criterion, and saves my labels to
   data/labels/labels.json. It does NOT show me the judge's answers first.
   Sample 20 calls across personas and prompt versions (seeded).
2. backend/eval/agreement.py: per criterion: % agreement and Cohen's kappa
   between my labels and the judge; list the disagreements.
3. backend/eval/export.py: export each final run's metrics and a few example
   transcripts to data/results/*.json (committed to Git) for the README and
   dashboard.
Tests with small fixtures. Plan first.
4. Cross-judge check: re-judge 20 stored calls (same sample as the hand
   labels) with a second judge model passed as --judge-model (I'll use
   gemini-3.8-flash, 20 requests/day). Report per-criterion agreement and
   Cohen's kappa between the two judges, and between each judge and my
   labels. Don't store second-judge results as the main verdict.