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