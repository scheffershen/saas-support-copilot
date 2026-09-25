# SaaS Support Copilot

A step-by-step Python build of a read-only chatbot that answers **usage**, **bug**, and
**feature-feasibility** questions about a SaaS application — by reading its end-user
help docs, source code, Git history, database, and logs. This is the companion project
for a YouTube course: every episode is one focused, tested change, and the commit
history *is* the course. The course is complete — 19 episodes, 0 through 18.

> Learning prototype, not a production-security guarantee. See [`lessons/`](lessons/)
> for the full arc and the [production-readiness checklist](docs/production-readiness-checklist.md)
> (Episode 17) for exactly what's still missing.

## What's fictional here

**Loopline** (`sample_app/loopline/`) — the ticketing SaaS the copilot answers
questions about — is invented for this course: fictional product, docs, database,
bugs, and commit history. Nothing in this repository is derived from, or represents,
any real company's product, code, or data.

## Quickstart

```bash
git clone <this-repo-url>
cd saas-support-copilot
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

# Seed the sample SaaS app's local database, then run it
python -m sample_app.loopline.app.seed
python -m uvicorn sample_app.loopline.app.main:app --reload --port 8001
```

In another terminal, run the copilot itself:

```bash
python -m uvicorn saas_copilot.api.main:app --reload --port 8000
curl http://localhost:8000/health

curl -X POST http://localhost:8000/ask \
  -H "Content-Type: application/json" \
  -d '{"session_id": "demo", "question": "how do I create a ticket?"}'
```

`/ask` needs a real LLM configured (`LLM_PROVIDER=openai` plus `LLM_API_KEY` in `.env`)
to do anything useful — with the default `LLM_PROVIDER=fake`, it answers every
question with the same fixed text, which is enough to exercise routing, tools, and
citations, just not to actually answer anything. Pass a caller's role via
`X-User-Role` (`support_agent`, `support_lead`, or `billing_admin`) to see
role-restricted content, like the admin runbook, come and go.

Run the tests (one is an intentional `xfail` — see [Episode 0](lessons/00-setup.md)):

```bash
pytest
```

### Optional: MySQL instead of SQLite (Episode 16)

`query_database` runs against SQLite by default — no Docker required. To switch it to
MySQL, matching Loopline's real target database:

```bash
# fill in MYSQL_ROOT_PASSWORD and MYSQL_READER_PASSWORD in .env first
docker compose up -d
```

Then set `LOOPLINE_READONLY_DATABASE_URL` in `.env` (see `.env.example` for the exact
form — use `127.0.0.1`, not `localhost`, to avoid a real ~5s IPv6-fallback delay on
some Windows + Docker Desktop setups). Set `USE_DATABASE_MCP=true` to route
`query_database` through a standalone MCP server (`mcp_server/server.py`, spawned
automatically per call) instead of connecting to MySQL in-process - needs the `mysql`
extra: `pip install -e ".[dev,mysql]"`.

```bash
docker compose down   # stop MySQL when you're done; add -v to also drop its data volume
```

## Repository layout

```text
saas-support-copilot/
├── pyproject.toml
├── docker-compose.yml     # optional MySQL, for query_database (Episode 16)
├── .env.example
├── README.md
├── docs/                  # production-readiness checklist + architecture diagrams
├── src/saas_copilot/      # the copilot — built episode by episode
│   └── mcp_server/        # standalone MCP server for query_database (Episode 16)
├── sample_app/loopline/   # the fictional target SaaS app (docs, source, schema, logs)
├── tests/
│   └── integration/       # cross-subsystem tests, one real conversation (Episode 18)
└── lessons/               # per-episode talking points, in order
```

## Course

Start with [`lessons/00-setup.md`](lessons/00-setup.md) and finish with
[the capstone](lessons/18-capstone-demonstration.md), which runs the whole system —
citations, refusal, RBAC, evaluation, local deployment — against a real model.

Every lesson is also available in full translation: [French](lessons/fr/00-setup.md)
([`lessons/fr/`](lessons/fr/)) and [Chinese](lessons/zh/00-setup.md)
([`lessons/zh/`](lessons/zh/)) — same code, commands, file paths, and citations as the
English original, only the prose is translated.

For a system-level map instead of an episode-by-episode one, see
[`docs/copilot-blueprint.html`](docs/copilot-blueprint.html) — four diagrams (system
boundary, request sequence, RAG pipeline, agent decision flowchart) read directly off
the current code. Open it in a browser; no build step.

Every line in this repository was written by prompting an AI coding agent, never
hand-typed — [`lessons/prompting-the-build.md`](lessons/prompting-the-build.md) is the
missing 19th-and-a-half lesson: not a new technical topic, but the discipline (one
focused, tested change per prompt; verify before writing anything down; correct drift
in writing) that made a two-word instruction like "Continue to Episode 12" reliably
produce a fully tested, fully documented capability, 75 real commits running.

## License

MIT — see [LICENSE](LICENSE).
