# SaaS Support Copilot

A step-by-step Python build of a read-only chatbot that answers **usage**, **bug**, and
**feature-feasibility** questions about a SaaS application — by reading its end-user
help docs, source code, Git history, database, and logs. This is the companion project
for a YouTube course: every episode is one focused, tested change, and the commit
history *is* the course.

> Learning prototype, not a production-security guarantee. See [`lessons/`](lessons/)
> for the full arc and Episode 16 for the prototype-vs-production gap list.

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

In another terminal, run the copilot itself (grows a real `/ask` endpoint from
Episode 13 onward — today it's just a health check):

```bash
python -m uvicorn saas_copilot.api.main:app --reload --port 8000
curl http://localhost:8000/health
```

Run the tests (one is an intentional `xfail` — see [Episode 0](lessons/00-setup.md)):

```bash
pytest
```

## Repository layout

```text
saas-support-copilot/
├── pyproject.toml
├── .env.example
├── README.md
├── src/saas_copilot/      # the copilot — built episode by episode
├── sample_app/loopline/   # the fictional target SaaS app (docs, source, schema, logs)
├── tests/
└── lessons/               # per-episode talking points, in order
```

## Course

Start with [`lessons/00-setup.md`](lessons/00-setup.md).

## License

MIT — see [LICENSE](LICENSE).
