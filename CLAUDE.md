# CollectionsLab

Evaluation harness for an AI collections voice agent. Full design in SPEC.md.
Read SPEC.md before starting any milestone.

## Stack
- Backend: Python 3.11+, FastAPI, SQLite, pytest
- LLM: Gemini API via the `google-genai` SDK, always through `backend/llm/client.py`
- Retrieval: BM25 (`rank-bm25`) over the policy document
- Frontend: React + Vite + TypeScript, Recharts
- CI: GitHub Actions

## How we work
- Plan first. Wait for my approval before writing code.
- ONE milestone at a time. Never start the next milestone unless I ask.
- Keep files under 200 lines. Prefer simple, readable code over clever code.
- Every backend module gets pytest tests. Unit tests must NOT call the real
  Gemini API: use a fake/mock LLM client.
- Run `pytest -q` before saying a milestone is done.
- Ask before adding any dependency. Add approved ones to requirements.txt.
- When done: summarize changes in 5 lines, list commands to verify, and suggest
  a commit message.

## Hard rules
- Never read, print, log, or hardcode `.env` or any API key. Load config with
  python-dotenv in `backend/config.py`.
- Never hardcode model names. They come from env vars (AGENT_MODEL, SIM_MODEL,
  JUDGE_MODEL).
- Synthetic data only. No real people, phone numbers, emails, or companies.
- Never report a metric that was not actually computed by the code.
- Live LLM runs default to small n (n=5 or less) unless I say otherwise.

## Environment (Windows, PowerShell)
- Activate env: `.venv\Scripts\activate`
- Do not chain commands with `&&`. Run them one per line.
- Do not create files with `>` redirects (PowerShell writes UTF-16). Use the
  file tools, or `Set-Content -Encoding utf8`.

## Commands
- Tests: `pytest -q`
- API: `uvicorn backend.main:app --reload`
- One simulated call: `python -m backend.sim.run_one --scenario 0 --prompt v1`
- Eval run: `python -m backend.eval.runner --prompt v1 --n 5 --seed 42`
- Frontend: `cd frontend`, then `npm run dev`

## Teaching mode
I'm new to React (I've used React Native). During frontend milestones, briefly
explain each new concept (components, props, state, hooks, fetching data) the
first time it appears. For backend milestones, explain any design decision I
might be asked about in an interview.