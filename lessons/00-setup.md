# Episode 0 — What we're building

**On screen:** an empty terminal, then this repo after `git clone`.

## Talking points

1. **Model vs application vs agent.** A model predicts text. An application wraps a
   model in fixed logic. An agent decides, using tools, what to do next. This course
   stays firmly on the "reads things, answers, cites sources" end of that spectrum —
   not the "takes autonomous actions" end.
2. **Workflow vs agent.** Most of what we build is a deterministic workflow
   (classify → retrieve → answer) with one bounded planning step for
   feature-feasibility questions. We're explicit about which parts are which, because
   "agent" is not automatically better than "workflow."
3. **Prototype vs production.** Everything here runs locally, with no auth, on sample
   data. Episode 17 is a full list of what's still missing for a real deployment —
   including the rule that none of this touches a real company's code or data without
   explicit sign-off.
4. **Local-first development.** No paid API key required to follow along — Episode 2
   introduces a fake `LLMClient` alongside a real provider adapter.
5. **Who's actually typing.** Every line in this repository was produced by prompting
   an AI coding agent, never by hand-writing the implementation — and every lesson
   from here on teaches exactly the knowledge that makes that work: not syntax, but
   why a design is correct, and how to verify that it is. See
   [`lessons/prompting-the-build.md`](prompting-the-build.md) once you've got a feel
   for a few episodes — it's about the whole course, not a step in it.

## Tour

- `sample_app/loopline/` — the fictional ticketing SaaS the copilot will answer
  questions about. Walk through `docs/`, `app/models.py`, `schema.sql`, and
  `logs/app.log`.
- `src/saas_copilot/` — the copilot itself. Today it's just `config.py` and a
  `/health` endpoint; everything else is built episode by episode.
- The commit history so far *is* the first lesson: scaffold → Loopline's app →
  logs → docs → a bug fix (`git log --oneline`) → this lesson.

## Do this

```bash
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
cp .env.example .env

python -m sample_app.loopline.app.seed
python -m uvicorn sample_app.loopline.app.main:app --reload --port 8001 &
curl http://localhost:8001/health

python -m uvicorn saas_copilot.api.main:app --reload --port 8000 &
curl http://localhost:8000/health

pytest
```

You should see 3 tests pass and 1 `xfail` — that's the seeded notification bug, not a
broken checkout.

## Exercise

Reproduce the seeded bug by hand: `POST /tickets/4/comments` with a body like
`{"author_id": 2, "body": "test"}`. Then, without any tooling, find the exact source
line that raises the `KeyError` and the exact seed row that's missing. That's the shape
of every answer the copilot will need to produce later: a claim plus a citation.
Episode 6 builds the tool that does this automatically.

## Next

Episode 1 adds typed models and a real test suite around the copilot's own code.
