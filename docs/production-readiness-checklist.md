# Production readiness checklist

What a real deployment of this pattern needs that `saas_copilot` — a local, single-
operator learning prototype — does not have. Written from this actual codebase, not
generic advice: every "today" line names the real file or behavior it's describing, and
every checkbox is something concretely true or false about this repository right now,
not a hypothetical.

One item on this list stopped being a gap during Episode 17 itself (see the first
section) — everything else here is still open, on purpose. Closing all of it would turn
a course project into an unbounded second project; naming it precisely is Episode 17's
actual deliverable.

## Identity and access

- [x] Role-based filtering is enforced at retrieval time, not suggested to the model
      (Episode 10 — `security/classification.py`, `retrieval/index.py::eligible_indices`).
- [x] An unknown caller defaults to the *least* privileged role, not the most
      (Episode 17 — `security/classification.py::is_visible_to`; before this episode,
      `role=None` returned `True` unconditionally, so any request that never sent
      `X-User-Role` could read `docs/admin-runbook.md`. See the lesson's live
      before/after transcript).
- [ ] **Authentication.** `get_role()` (`api/dependencies.py`) reads whatever the
      caller puts in `X-User-Role` — a real header, but a *self-asserted* one, checked
      only for being a known role name (`validate_role`), never for actually
      belonging to whoever sent it. RBAC restricts what a role can see; nothing here
      confirms the caller *is* that role. Minimum real step: a real identity
      provider (SSO/OIDC — whatever the org already runs) in front of this service,
      with role derived from a verified token claim, never a raw client header.
- [ ] **ABAC.** Access control here is a single dimension — role → document. A real
      system usually needs more: ticket ownership, team membership, time-of-day,
      data-sensitivity tags. `eligible_indices()` already takes an arbitrary
      predicate (see Episode 10's own exercise) — the gap is that no second dimension
      is wired in, not that the mechanism can't hold one.
- [ ] **Classify-by-default content.** `RESTRICTED_DOCS` is a denylist: a newly added
      doc is public the moment it's seeded unless someone remembers to list it here.
      A production system should default new content to restricted-until-classified.

## Tenant isolation

- [ ] **No concept of a tenant exists anywhere in this codebase.** One MySQL
      database, one `loopline` schema (`sample_app/loopline/schema.sql`), no
      `tenant_id` column on any table. Role restricts *what kind* of content a caller
      sees; it says nothing about *whose* data. This is the largest gap on this list
      for any real multi-customer SaaS.
- [ ] **`query_database` is a general-purpose SELECT tool** (`tools/database.py` /
      `database_mysql.py` / `database_mcp.py`) — exactly the shape of tool that's
      easiest to leak cross-tenant data through if a `tenant_id` filter is ever
      trusted from caller input instead of enforced underneath it. A real version
      needs the restriction enforced at the database layer itself (e.g., Postgres/
      MySQL row-level security, or a connection scoped to one tenant), not appended
      to the SQL string by application code.

## Network boundaries

- [ ] The copilot, Loopline, and MySQL all run on `localhost` with no network
      segmentation (`docker-compose.yml` publishes MySQL's port directly). The
      Episode 16 read-only `loopline_reader` user is real, but it's reachable from
      anywhere that can reach port 3306, not just from the copilot's own process.
- [ ] No TLS anywhere in this stack — copilot↔MySQL, client↔copilot, copilot↔LLM
      provider (`llm/openai_compatible.py` talks plain `LLM_BASE_URL`, whatever
      scheme it's configured with). Minimum real step: private subnets, security
      groups scoping database access to the copilot's own service, TLS on every hop.

## Scale of in-repo analysis

- [ ] `CallGraph` (Episode 9, `graph/call_graph.py`) and `DocumentIndex` (Episode 8)
      are both built in memory, on demand, from an `ast` walk and a full doc read —
      genuinely fine for Loopline's few hundred lines and dozen docs, not a claim it
      would scale to a real codebase of any size. A real deployment needs a real
      incremental index (persisted, updated on change, not rebuilt whole on every
      `/ingest`) and a call graph tool that doesn't re-parse the entire source tree
      in-process on every startup.

## Audit retention

- [x] Structured, privacy-safe operational logging exists (Episode 15 —
      `telemetry/trace.py::log_run`) — deliberately has no question/answer parameter
      at all, not "redacted," just never captured, so it can't leak what was asked.
- [ ] Nothing durable or queryable records *who* (once real identity exists) asked
      *what kind* of question, saw *which* citations, and when — which is what an
      actual compliance or incident investigation needs, and a different (less
      privacy-conservative, more access-controlled) artifact than the Episode 15 log.
      It also needs a retention policy; `log_run` currently just prints, wherever the
      process's stdout goes, forever or never depending on the deployment.

## Rate limits and cost

- [ ] **No rate limiting anywhere in `api/`.** A caller can call `POST /ask` — which
      makes a real, billed LLM call every time — in a tight loop with nothing to stop
      it. Minimum real step: per-caller throttling (even a basic token bucket) ahead
      of `get_llm_client`, keyed on real identity once Authentication above exists.
- [ ] **No cost tracking beyond a single request.** `TracingLLMClient` (Episode 15)
      reports `tokens_used` per call, but nothing aggregates it across callers, sets a
      budget, or alerts on a spend spike — the same missing throttle as rate limiting,
      looked at from the billing side instead of the abuse side.

## Queues

- [ ] `POST /ask` runs synchronously end-to-end, just hopped onto a worker thread so
      it doesn't block the event loop (`asyncio.to_thread` in `api/routes.py`) — the
      request stays open for the full agent turn, with no retry or replay if it fails
      partway and no way to handle a burst past the thread pool's own limits. A
      production version of a multi-step, multi-LLM-call agent turn belongs behind a
      real queue (Celery/RQ/SQS-backed) with a job-status endpoint the client polls.

## Backups

- [ ] MySQL's data lives in an unbacked-up local Docker volume
      (`docker-compose.yml`). Fine for seed data that regenerates from
      `seed_data.sql`; not fine for anything a real deployment would actually hold.
      Minimum real step: automated backups that are periodically *restored*, not just
      taken, with a stated RPO/RTO — an untested backup is a belief, not a plan.

## Incident response

- [ ] `/health` reports real status (`"ok"`/`"degraded"`, Episode 16 — it probes the
      database, not just whether the process is up) — but nothing currently watches
      it. No alerting, no on-call rotation, no written runbook for "the database is
      unreachable" or "`/ask` started 502ing." A one-page runbook beats none.

## Threat modeling

- [ ] Real, tested defenses exist — prompt injection (Episode 13), a destructive-
      intent gate (Episode 12), SELECT-only enforcement against SQL-injection-shaped
      abuse (Episode 12, re-verified at the MySQL layer in Episode 16) — but each was
      added when the course reached that topic, one at a time. No single pass has ever
      modeled this whole system's attack surface at once (a STRIDE pass or an attack
      tree, done once and revisited on every material change, not per-episode).

## Ownership

- [ ] No named owner. There's no on-call contact, no escalation path, and no
      documented decision-maker for questions like "can we point this at a new data
      source" or "who signs off on a schema change." A real deployment needs a named
      owner — person or team — written down, not implied by whoever last touched it.

## The data and IP boundary — pointing this at a real codebase

Not a gap in this prototype; a rule for what comes after it, stated here precisely
because this is the episode that names it in depth (it's referenced from this course's
very first commit and from `youtube_course_plan.md`'s own design-origin note):

- [ ] **Before wiring this pattern to any real employer's codebase, database, or
      logs — not after — get explicit, written sign-off on exactly what the agent may
      read and exactly where its output may go.** Treat that access the same way
      you'd treat any other credential: scoped, requested on purpose, and revocable.
- [ ] **Secrets stay outside source control**, in whatever the organization's real
      secret store is — not the `.env`-file convenience this course uses for local
      MySQL passwords (`.env.example`), which is explicitly a local-dev shortcut, not
      a production secrets story.
- [ ] **Real proprietary source, data, or product names never enter a public repo or
      public lesson content** — not summarized, not "genericized," not partially
      redacted. This repository only ever contains the fictional Loopline app for
      exactly this reason, from its first commit onward.

## What Episode 18 does with this list

The capstone doesn't close these gaps — closing all of them would be its own multi-
episode arc, not a wrap-up. It demonstrates the finished prototype end to end (real
citations, real refusals, real access control, real evaluation results) with this list
shown alongside it, honestly labeled as what's still missing — the same "state
production limitations plainly" rule this course has followed since Episode 0.
