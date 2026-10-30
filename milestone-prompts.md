# Milestone prompts (Day 1)

How to use each one:
1. Type /clear in the Claude panel (fresh context for each milestone).
2. Switch to Plan mode (Shift+Tab).
3. Paste the prompt. Read the plan. Ask "why?" about anything unclear. Approve.
4. When Claude finishes: run the verify commands yourself, then
   "Explain this milestone as if I'm being interviewed about it."
5. Commit:
   git add .
   git commit -m "M1: ..."

---

## M1: Scenario generator + personas + policy document

Read CLAUDE.md and SPEC.md. We are doing Milestone 1 only.

Build:
- backend/scenarios/personas.py: the 7 personas from SPEC section 3, each with
  a name, a behavior description (used later as the debtor LLM's instructions),
  and the expected_outcome.
- backend/scenarios/generator.py: generates N seeded scenarios
  (invoice + persona + expected_outcome) using the fields in SPEC section 3,
  with SIM_DATE = 2026-11-02. Use Pydantic models. Synthetic Indian business
  names, INR amounts with 18% GST. Distribute personas evenly.
  CLI: python -m backend.scenarios.generator --n 14 --seed 42 prints JSON.
- data/policy/collections_policy.md: a short, realistic synthetic policy
  covering everything in SPEC section 4, with clear section headings.
- Tests: same seed gives identical output, all fields valid, personas evenly
  distributed, already_paid scenarios have a payment_claim.

Done when the CLI works and pytest -q passes.
Plan first. Don't write code yet.

---

## M2: Config + LLM client

Read CLAUDE.md and SPEC.md section 9. Milestone 2 only.

Build:
- backend/config.py: loads GEMINI_API_KEY, AGENT_MODEL, SIM_MODEL, JUDGE_MODEL,
  RPM_LIMIT from .env with python-dotenv. Clear error if something is missing.
  Never print the key.
- backend/llm/client.py: one interface for text generation and function
  calling via google-genai. Disk cache in data/cache/, retries with exponential
  backoff on rate-limit errors, simple requests-per-minute limiter, returns
  text, tool calls, latency_ms, and token counts.
- backend/llm/fake.py: a scripted fake client for tests.
- backend/llm/list_models.py: prints the model names my key can use.
- Tests using the fake client and mocks only (no real API calls).

Also update .env.example with the new variable names (blank values).
After it works, I'll run list_models and fill model names in .env.
Plan first.

---

## M3: Policy RAG + tools

Read CLAUDE.md and SPEC.md sections 4-5. Milestone 3 only.

Build:
- backend/rag/policy_index.py: chunk collections_policy.md by section, BM25
  search (rank-bm25; ask me before adding it), returns top-k chunks with
  section titles.
- backend/agent/tools.py: the 8 tools from SPEC section 5 as plain Python
  functions operating on a per-call CallState object (the scenario's invoice +
  logged actions), plus Gemini function declarations for them.
- Tests: retrieval finds the right section for 5 sample queries; each tool
  updates CallState correctly; get_invoice only returns that call's invoice.
Plan first.

---

## M4: Agent v1 + simulator

Read CLAUDE.md and SPEC.md sections 5-6. Milestone 4 only.

Build:
- backend/prompts/v1.yaml (naive prompt, as in SPEC).
- backend/agent/agent.py: given conversation history + CallState, runs the
  agent model with tools, executes tool calls, loops until it produces a spoken
  reply. Records tool calls, latency, tokens.
- backend/sim/simulator.py: debtor LLM plays the persona (behavior description
  + invoice as private context). Agent speaks first. Max 12 debtor turns. Ends
  on end_call, escalate_to_human, or limit.
- backend/sim/run_one.py: CLI that runs one scenario and prints the transcript
  readably and saves it as JSON.
- Tests with the fake client: loop terminates, tool calls are executed and
  recorded, turn limit enforced.
Then I'll run one real call with n=1 and we'll read the transcript together.
Plan first.

   Also: the google-genai SDK has its own internal retries stacked under ours
   (seen as tenacity in a traceback). Check the SDK docs for how to disable or
   limit them via HttpOptions so only our retry logic runs, and add a test.

---

## M5: Summarizer

Read CLAUDE.md and SPEC.md section 7. Milestone 5 only.

Build backend/agent/summarizer.py: turns a transcript + logged actions into the
JSON record from SPEC section 7, validated by Pydantic. Logged tool actions take
priority over the LLM's reading of the conversation; note any disagreement.
Tests with the fake client. Then run it on the transcript from M4.
Plan first.

---

# End of Day 1 check
- python -m backend.sim.run_one --scenario 0 --prompt v1 works
- pytest -q passes
- Everything committed and pushed
- LEARNINGS.md has notes: what broke, what you changed, what surprised you
