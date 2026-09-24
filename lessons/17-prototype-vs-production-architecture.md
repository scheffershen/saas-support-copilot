# Episode 17 — Prototype versus production architecture

**On screen:** the exact same call — an anonymous caller, no `X-User-Role` header,
asking to search for "force-deactivate a compromised account" — run twice: once
against this episode's starting code, once after its one-line fix. `docs/admin-
runbook.md` is in the results the first time. It's gone the second.

## Learning objective

Every episode until now added a capability. This one draws the line around all of
them: what does this prototype actually have, what does a real production deployment
still need, and — the one place those two questions meet concretely enough to fix
today — where has this course's own code been quietly relying on a gap it already
named out loud? Close that one for real, then write down the rest precisely enough
to act on, not just gesture at.

## Talking points

1. **A gap two earlier episodes had already named and deliberately deferred.**
   `security/classification.py::is_visible_to`'s `role=None` branch returned `True`
   unconditionally since Episode 10 — "no known identity" was treated as *more*
   trusted than any actual role, not less. Episode 10's own docstring called this "a
   prototype convenience... not a production-safe default." Episode 14's
   `api/dependencies.py::get_role` repeated the same note: "flipping that default is
   explicitly Episode 17's job." A documented gap is still a real gap until the
   episode that promised to close it actually does.
2. **The fix is narrower than "unknown caller sees nothing."** `RESTRICTED_DOCS` is a
   denylist — most docs have no entry at all and are visible to everyone. The
   correct flip isn't "no identity, no access" (that would break every usage-domain
   answer, since no client in this course ever sends `X-User-Role` unless it's
   specifically testing role restriction) — it's "no identity is never treated as
   implicitly authorized for content that names specific allowed roles," which is
   exactly what any other unauthorized role already gets. `is_visible_to` now checks
   `path not in RESTRICTED_DOCS` first, same short-circuit `roles_allowed()` already
   used, before ever comparing `role`.
3. **What this fix does *not* close.** `get_role()` still trusts whatever
   `X-User-Role` the caller sends — validated for being a real role name
   (`validate_role`), never for actually belonging to whoever sent it. RBAC
   (restricting what a role can see) and authentication (confirming a caller really
   is that role) are different concerns; this episode closed the first gap in the
   first one, not the second one. The checklist below keeps them as separate,
   unchecked items on purpose.
4. **The production-readiness checklist.** `docs/production-readiness-checklist.md`
   — identity/access, tenant isolation, network boundaries, audit retention, rate
   limits and cost, queues, backups, incident response, threat modeling, ownership.
   Every line names the actual file or behavior it's about, not generic advice — the
   same discipline this course has applied to every lesson's talking points, turned
   on the whole system at once instead of one episode's feature.
5. **Tenant isolation is the largest single gap on it.** Nothing in this codebase has
   ever had a concept of "tenant" — one MySQL schema, no `tenant_id` anywhere,
   `query_database` a general-purpose SELECT tool built in Episodes 12 and 16 that
   would be exactly the wrong shape to trust with a caller-supplied tenant filter. No
   episode before this one needed to name that, because Loopline itself only ever
   modeled a single organization.
6. **The IP and sign-off boundary, in full.** Referenced since this repo's very first
   commit and `youtube_course_plan.md`'s own design-origin note, given its complete
   treatment here: before pointing this pattern at any real employer's codebase,
   database, or logs, get explicit written sign-off on exactly what the agent may
   read and where its output may go — treated as a credential, not a convenience —
   and never let real proprietary source, data, or product names reach a public repo
   or public lesson content. This repository has held that line from commit one.
7. **The capstone doesn't close this list — it shows it.** Episode 18 demonstrates
   the finished prototype end to end and presents this checklist alongside it,
   honestly labeled as what's still missing. That's the same "state production
   limitations plainly" rule from Episode 0's very first talking point, applied to
   the whole system on the way out instead of one feature on the way in.

## Implement

- [`src/saas_copilot/security/classification.py`](../src/saas_copilot/security/classification.py) — `is_visible_to`'s deny-by-default flip.
- [`src/saas_copilot/api/dependencies.py`](../src/saas_copilot/api/dependencies.py) — `get_role`'s docstring, corrected now that the flip is real.
- [`docs/production-readiness-checklist.md`](../docs/production-readiness-checklist.md) — this episode's second deliverable.
- [`tests/unit/test_security_classification.py`](../tests/unit/test_security_classification.py), [`tests/unit/test_tools_docs.py`](../tests/unit/test_tools_docs.py), [`tests/unit/test_api.py`](../tests/unit/test_api.py) — flipped and one new test, proving the property at the classification layer, the tool layer, and the real FastAPI dependency chain.

## Run

```bash
pytest tests/unit/test_security_classification.py tests/unit/test_tools_docs.py tests/unit/test_api.py -v
```

## Failure case (real, this episode's starting point)

Against the code exactly as Episode 16 left it — `get_role(x_user_role=None)`, the
real function FastAPI calls for a request with no `X-User-Role` header at all, fed
straight into `get_registry()`, the real dependency chain, no mocks:

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/assigning-tickets.md', 'docs/creating-a-ticket.md',
 'docs/getting-started.md', 'docs/integration-notes.md', 'docs/notifications.md',
 'docs/roles-and-permissions.md'}
```

A caller who authenticated as nobody got back the one document in this entire corpus
that's restricted to `support_lead`.

## Live demo (verified output)

The identical call, after this episode's one change to `is_visible_to`:

```pycon
>>> role = get_role(x_user_role=None)
>>> role
None
>>> registry = build_registry_for_role(resources, role=role)
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/assigning-tickets.md', 'docs/creating-a-ticket.md', 'docs/getting-started.md',
 'docs/integration-notes.md', 'docs/notifications.md', 'docs/roles-and-permissions.md'}
```

`docs/admin-runbook.md` — gone. Everything else — identical, six of six. The fix
removed exactly the one document it was supposed to, and nothing else: an anonymous
caller can still find every ordinary doc, same as before.

## Exercise

Pick one open item from `production-readiness-checklist.md` and close the smallest
real slice of it. Rate limiting is the most self-contained: add a basic per-caller
token bucket in front of `POST /ask` (key it on `X-User-Role`, or the connecting IP
if that's absent — real identity is still Authentication's job, not this one's),
returning `429` once a caller exceeds it within a window. Write a test proving the
Nth request in a tight loop gets throttled and the (N-1)th doesn't — then update the
checklist's rate-limiting checkbox to reflect exactly what you built and what's still
missing (a single-process token bucket won't survive multiple server instances;
name that honestly rather than silently claim more than you built).

## Next

Episode 18 is the capstone: ingestion, permission-aware Q&A, a bug diagnosis with
cited evidence, a feature-feasibility triage using the call graph, citations,
refusal, tool traces, evaluation results, local deployment, and this episode's
checklist — shown together, end to end. It challenges learners to add a new Loopline
module with its own docs, its own role restrictions, and ten tests of their own.
