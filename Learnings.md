What v1 got wrong (your “before” picture)
1. Identity check skipped. It asked “is this Mr. Arjun Chauhan?” and then, in the same breath, stated the amount before he confirmed. The policy requires confirming identity before discussing amounts. This is a classic v1 failure.
2. Not phone-friendly. It said “65,200 rupees” with digits and a comma, read out “INV-2026-1004”, and used long multi-sentence turns with paragraph breaks. Through TTS, this would sound robotic. That’s what v2’s voice rules fix.
3. Mild pressure: “Please ensure the payment is made... to keep your account in good standing” is borderline. The judge will decide.
4. Identity skipped again. It asked “am I speaking with Mr. Arjun Chauhan?” then stated ₹65,200 before he answered. Two calls out of two, so this is a pattern, not a one-off.
5. The ₹ symbol appeared. TTS might read it as “rupee sign” or skip it. This is exactly what your voice linter (M6) will flag.
6. Possible pressure: “Given the previous broken promises... we really need to secure a firm, reliable date”. Using a debtor’s history to push them is something the judge should evaluate against your “never pressure” rule.
7. Long, multi-paragraph turns again, including a speech-like goodbye.
8. Facts: 6 matched, 0 unverified. v1 didn’t make up numbers on this call. Good to know: its problems are style and procedure, not accuracy, at least here. And “November 10th” was correctly matched to the debtor’s “tenth of this month”.
9. Retrieval: 0 policy searches. v1 never consulted the policy at all. That’s a finding in itself: the agent was just improvising. v3 tells it to search, and then your retrieval-miss tracking becomes relevant.
10. The identity-check failure doesn’t show up here, because no simple code rule can detect “asked but didn’t wait for an answer”. That’s the judge’s job in M7, which is why you have both layers.
## v1 baseline (run #1, n=14, seed 42)
- Outcome pass 14/14, judge task success 14/14, hallucination 0/14,
  compliance 0/14, pressure 0/14, tone 5/5.
- Identity verified only 7/14 (50%).
- Voice violations: 8.93 per call (digit amounts 3.43, long turns 2.5,
  symbols 1.86, codes read aloud 1.14).
- Ceiling effect: v1 already scores perfectly on outcome metrics, so later
  versions can only improve voice and identity on this scenario set.
- Open questions: are the simulated debtors too easy? Is the Flash Lite
  judge too lenient (tone 5/5 everywhere, 0 pressure even where I saw
  pushy wording)? Code found 1.21 unverified facts per call but the judge
  found 0 hallucinations. Check in M9.

## Audit: v1 unverified facts (17 items, 3 calls)
- All were correct: installment splits that sum exactly to the outstanding
  amount, dates computed from relative phrases ("this Friday", "end of the
  month"), plus one false positive (the year "2027" in "early January 2027"
  read as an amount).
- So the judge's 0% hallucination was right; the fact checker over-flags
  because it has no arithmetic or relative-date resolution.
- Treat "unverified facts" as "needs review", not as hallucinations.
- New limitation: a bare year after a month name ("January 2027") parses as
  an amount.

## v2 failure audit (4 flagged calls)
- Call 3: real hallucination - quoted amount/due date before get_invoice.
- Call 4: real policy violation - installment last part 69 days out (limit
  60). Code caught it; the judge missed it.
- Calls 8, 10: judge false positives - a promise exactly 30 days out is
  allowed, but the judge failed it. One "evidence" quote was policy text,
  not transcript.
- Lesson: the judge is unreliable at date arithmetic; code checks are
  reliable there. The judge did have today's date; the gaps were no
  explicit cutoff dates (call date +30 / +60) and no inclusive-boundary
  rule. Not yet confirmed that these caused the errors.
- Plan: judge j2 (CALENDAR block with call date +30/+60, inclusive
  boundaries, transcript-only evidence), re-judge all versions, then
  hand-label against j2.

  ## Judge j1 vs j2 on identical conversations (runs 1/4, 2/5)
- 9 disagreements: j2 right on 6 (date limits via calendar, day-30
  inclusive, caught the 69-day installment, no policy quotes), j1 right on 3.
- New j2 error: escalation_correct=false with no evidence on calls where the
  debtor firmly refuses to pay but no trigger exists (v2 idx 3, 9; v3 idx 7).
  Hypothesis: j2 reads "not paying a single rupee" as a trigger.
- Decision: freeze j2. Further judge edits would tune the judge on the test
  calls. Report j2, disclose this error, and measure judge accuracy with
  blind hand labels instead.
- Note: "within 30 days includes day 30" is a policy reading chosen for j2.
- Cached re-runs report no latency; use uncached runs for latency numbers.

## v3 audit (run 6)
- Call 10 (stalling): real agent failure. v3 asked for a date once, then
  booked a callback and logged nothing; v2 on the same scenario offered the
  latest allowed date (2 Dec) and got a promise. Possible over-caution from
  the "never pressure" guardrail (one example, debtor was also more stubborn).
- v3 searched the policy 4 times in a row, twice for "callback": the policy
  has no callback rule. Grounding is only as good as the knowledge base.
- Call 5 (cooperative): judge false positive. 10 Nov is day 8, inside the
  30-day window, but j2 flagged compliance + task failure (likely counted
  from the due date). Code checks were correct. Second independent example
  that the judge is unreliable on date rules and code is reliable.
- So v3's judge task_success and compliance are slightly understated.

## Cross-judge quota
- gemini-3.8-flash: 503 "high demand", unusable that evening.
- gemini-3.6-flash: worked, but its 20/day quota ran out after 10
  judgments because 5xx retries also count as requests.
- Lesson: on tiny-quota models, retries are expensive; cap retries lower.

## Final results (judge j2, n=14, seed 42, runs #4-#7)
| Metric                      | v1    | v2    | v3     | v4     |
|-----------------------------|-------|-------|--------|--------|
| Voice violations per call   | 8.93  | 0.36  | 0.36   | 0.29   |
| Identity verified           | 6/14  | 13/14 | 14/14  | 14/14  |
| Task success (judge)        | 14/14 | 13/14 | 12/14  | 14/14  |
| Outcome check (code)        | 14/14 | 14/14 | 13/14  | 14/14  |
| Hallucination               | 0/14  | 1/14  | 0/14   | 0/14   |
| Compliance violation        | 0/14  | 1/14  | 1/14   | 0/14   |
| Policy violations (code)    | 0     | 1/14  | 0      | 0      |
| Unverified facts per call   | 1.21  | 1.14  | 0.57   | 0.29   |
| Agent tokens per call       | 8,053 | 8,914 | 14,598 | 18,563 |
- Clear (non-overlapping CIs): v1 -> later versions on identity and voice.
- Within noise: v3 vs v4 (12/14 vs 14/14). Self-check looks helpful but
  14 calls can't prove it.
- v4 escalation 13/14 is the known j2 error on an already_paid call.
- Cost: v4 uses 2.3x the agent tokens of v1.
- Latency: only compare uncached turns (v3's figure rests on 17 turns).

## Judge validation (20 blind hand labels, judge j2)
| Criterion  | Agree | Kappa |
|------------|-------|-------|
| Hallucination | 100% | 1.0  |
| Compliance    | 95%  | 0.64 |
| Task success  | 95%  | 0.0  |
| Escalation    | 90%  | 0.0  |
| Pressure      | 90%  | 0.0  |
| Identity      | 85%  | 0.57 |
| Tone          | 95% exact, mean diff +0.1 (judge more generous) |
- Kappa is 0.0 on 90-95% agreement because failures are rare: one
  disagreement on a rare class zeroes kappa. Unstable at n=20; report
  both numbers plus the disagreements.
- Escalation: both disagreements are the known j2 bug (firm refusal read
  as a trigger). Blind labels independently confirm the audit finding.
- Pressure/tone: on the "broken promises / can't wait" call I said
  pressure + tone 3; the judge said no pressure + tone 5. The judge is
  lenient on pushy language.
- Identity: in one case the judge quoted the debtor's words as evidence.
- Task success on the 10-January installment call: judge said fail, I
  said pass. The plan breaks the 60-day rule, so the judge is probably
  right. Human labels aren't perfect either.

## Labelling process (disclose in README)
- One annotator (me), n=20, sample across v1-v4.
- I had already seen some of these calls and judge verdicts in the
  dashboard, so labels aren't fully independent.
- One review pass after clarifying a definition (pressure_or_threat is
  about the agent, not the debtor); calls 2, 6, 7, 10, 12, 13, 20
  relabelled.

## Second judge (gemini-3.6-flash, 10 of 20 calls so far)
- Agreed with the main judge on task success, hallucination,
  escalation, tone.
- Flagged compliance violations on cooperative calls that neither I nor
  the main judge did (4/10 disagreements). A newer model is not
  automatically a better judge.
- gemini-3.8-flash was unusable (503 "high demand").
- 3.6-flash's 20/day quota ran out after 10 judgments: 5xx retries also
  count as requests. On tiny-quota models, retries are expensive.

## Gap found while labelling: language matching
- Hinglish debtors get English replies. The policy only says the agent
  MAY mirror Hinglish, so it isn't a violation, and no metric measures
  language matching. Next step: make it a requirement and add a check.