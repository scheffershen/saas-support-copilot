# Episode 14 — FastAPI application boundary

**On screen:** `curl -X POST /ask` against a real, running server - a real, cited
answer comes back, with a request ID in both the header and the body. Then the exact
same request against an unconfigured, unscripted client - a clean `502
malformed_output`, not a Python traceback.

## Learning objective

Everything built so far has been called in-process, directly, by tests and by each
other. This episode gives it an HTTP boundary - the same `ask()`/`run_agent()`
pipeline every earlier episode's tests already exercise, now reachable over the
network. That boundary brings its own concerns: a request body from a stranger needs
a validated shape, the expensive shared resources (the doc index, the call graph)
need to survive across many requests without rebuilding per request, synchronous work
can't block the event loop other requests share, and every one of this course's own
exception types needs to become a response a client can actually parse - not a
traceback.

## Talking points

1. **Request/response models, for the same reason as `Answer` (Episode 3).**
   `api/schemas.py`'s `AskRequest`/`AskResponse` are Pydantic - an HTTP request body is
   untrusted input the same way an LLM's output is, and FastAPI validates it before a
   route handler ever sees it.
2. **Dependency injection pays off an old debt.** `tools/__init__.py::build_default_registry`
   has carried a comment since Episode 10: rebuilding the doc index and call graph on
   *every* call is fine for a test that builds one registry and is done, wrong for a
   server handling many requests with different roles. Split into
   `build_shared_resources()` (expensive, built once) and `build_registry_for_role()`
   (cheap, rebinds only role) - `api/main.py`'s `lifespan` builds the shared part
   once at startup and stashes it on `app.state`; `api/dependencies.py`'s `Depends()`
   providers read it back per request. `build_default_registry()` is now a thin
   wrapper over both, kept so every earlier episode's tests keep calling it exactly
   as before - proven directly
   (`test_build_default_registry_matches_the_split_two_step_build`).
3. **Async endpoints, honestly.** `run_agent()`/`ask()` are synchronous, on purpose,
   since Episode 5's own correction note (a thread-pool timeout, not real async). The
   route handlers are `async def` anyway, and explicitly hop the actual agent work to
   a worker thread with `asyncio.to_thread()` - so a slow agent run doesn't block the
   event loop every other concurrent request shares. FastAPI would also run a plain
   `def` handler in a thread pool automatically (Loopline's own
   `routers/tickets.py` relies on exactly that, unmodified since Episode 0) - the
   explicit version here spells the same mechanism out instead of leaving it implicit.
4. **Request IDs, as middleware.** `add_request_id` wraps every request - the caller's
   own `X-Request-ID` if it sent one, otherwise a fresh one - set on `request.state`
   before the route runs and echoed as a response header on success *and* on an error
   response, since middleware wraps the whole call including exception handling.
5. **A health check that's cheap *and* real.** `/health` reports a real number
   (`docs_indexed`, read off `app.state`) without rebuilding anything - proof the
   service's actual dependency (the doc index) is alive, not just that the process
   is running, and fast enough to poll constantly.
6. **Error responses: one handler per exception type this course already defines,
   never a bare `except Exception`.** `UnknownRoleError` -> 400 (the client's
   mistake); `AgentError` and every subclass -> 422 (a well-formed request the
   agent's own safety constraints stopped it from answering); `LLMTimeoutError` -> 504
   ahead of the more general `LLMError` -> 502 (Starlette resolves handlers by
   walking the exception's MRO, so the more specific registration wins);
   `MalformedOutputError` -> 502 (the provider responded, but never produced valid
   output even after `complete_structured()`'s retries). Anything *not* named here
   still surfaces as FastAPI's ordinary 500 - swallowing unknown exceptions would
   hide real bugs, not handle them.
7. **Role travels as a header, never a request-body field.** `AskRequest` has no
   `role` field - `X-User-Role` is a dependency (`get_role`), out of band from the
   question, the same discipline as every allowlisted root and bound role since
   Episode 5/10. Proven all the way through the DI chain, not just asserted:
   `test_get_registry_binds_the_role_all_the_way_to_the_tools_own_filtering` calls
   `get_registry()` directly (a FastAPI dependency is just a plain function) and
   confirms the resulting registry's `search_docs` still can't surface the restricted
   admin runbook for `support_agent`.
8. **`/ingest` and `/evaluations`, honest about what they actually do today.**
   `/ingest` is real, not a stub: it re-reads Loopline's docs/source from disk and
   rebuilds the shared resources without restarting the process, swapping them onto
   `app.state` only after the rebuild finishes so an in-flight request isn't
   disrupted. `/evaluations` returns `{"suites": []}` - genuinely empty, because no
   evaluation suite is registered yet; that's Episode 15's job, and this is the shape
   it will fill in, not a placeholder pretending to run something that doesn't exist.

## Implement

- [`src/saas_copilot/tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — `SharedResources`, `build_shared_resources`, `build_registry_for_role`.
- [`src/saas_copilot/api/schemas.py`](../src/saas_copilot/api/schemas.py) — request/response models.
- [`src/saas_copilot/api/dependencies.py`](../src/saas_copilot/api/dependencies.py) — the `Depends()` providers.
- [`src/saas_copilot/api/routes.py`](../src/saas_copilot/api/routes.py) — `/health`, `/ask`, `/ingest`, `/evaluations`.
- [`src/saas_copilot/api/main.py`](../src/saas_copilot/api/main.py) — `lifespan`, the request-ID middleware, the exception handlers.

## Run

```bash
pytest tests/unit/test_api.py tests/unit/test_tools_default_registry.py -v
```

## Live demo (verified output)

```bash
curl http://localhost:8000/health
# {"status":"ok","docs_indexed":13}

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -d '{"session_id": "demo", "question": "how do I create a ticket?"}'
# {"request_id":"b65f7813-...","domain":"usage",
#  "answer":"To create a ticket in Loopline, follow these steps:\n\n1. Click New
#  ticket.\n2. Enter a title and description.\n3. Submit the ticket. The ticket will
#  start in the open status with no assignee.",
#  "citations":["docs/creating-a-ticket.md#chunk-0"],"confidence":1.0,
#  "refused":false,"refusal_reason":null,"steps_taken":2,"tools_called":["search_docs"]}
# (captured with a real OpenAI-compatible provider configured; the committed default,
# LLM_PROVIDER=fake, is covered in the failure case below instead - it was never
# meant to produce a coherent answer unscripted, only this course's tests script it)

curl -X POST http://localhost:8000/ask -H "Content-Type: application/json" \
  -H "X-User-Role: superadmin" -d '{"session_id": "demo", "question": "hi"}'
# 400 {"error":"unknown_role",
#      "detail":"unknown role: 'superadmin'. Known roles: billing_admin,
#      support_agent, support_lead","request_id":"c7eb6274-..."}

curl -D - -o /dev/null http://localhost:8000/health -H "X-Request-ID: my-own-trace-id"
# x-request-id: my-own-trace-id   <- echoed back exactly, not replaced
```

## Failure case (show this live — the actual committed default, zero config)

`LLM_PROVIDER=fake` (the repo's own `.env.example` default) gives you an *unscripted*
`FakeLLMClient` - its single fixed reply, `"This is a fake response."`, was never
meant to be valid JSON on its own; every real demo in this course scripts it first.
Hitting `/ask` with nothing configured beyond the README's own quickstart:

```pycon
>>> response = client.post("/ask", json={"session_id": "demo", "question": "how do I create a ticket?"})
>>> response.status_code
502
>>> response.json()
{'error': 'malformed_output',
 'detail': "no valid RouteDecision after 3 attempts: not valid JSON: Expecting value: line 1 column 1 (char 0)",
 'request_id': '859ae080-...'}
```

Exactly `complete_structured()`'s own retry-then-raise behavior from Episode 4,
now visible as a clean, structured 502 instead of an unhandled exception - the
boundary did its job even in the one case where nothing behind it works yet.

## Exercise

`AgentCancelledError` has had a full exception-to-status mapping (422) since this
episode, but nothing in the API ever actually triggers it - `memory/orchestration.py::ask()`
doesn't accept a `cancel_token` at all yet. Thread one through: add `cancel_token`
to `ask()`'s signature (passing it straight to `run_agent()`, which already accepts
one), create a fresh `threading.Event` per request in the `/ask` handler, and set it
if the client disconnects before the agent run finishes (FastAPI's `Request.is_disconnected()`,
checked from a small background task racing the `asyncio.to_thread()` call). Write a
test proving a run that would otherwise succeed is cut off mid-loop when the token
fires.

## Next

Episode 15 covers evaluation and observability: golden datasets, answer/citation/
refusal/access-control tests, an "evidence required before answering" check for
`bug`/`feature` questions specifically, traces, latency, token usage, retrieval
diagnostics, and privacy-safe logs. `/evaluations` finally gets something real to
report.
