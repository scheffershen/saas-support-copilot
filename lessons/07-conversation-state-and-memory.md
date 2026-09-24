# Episode 7 — Conversation state and memory

**On screen:** two questions typed one after another — "what statuses can a ticket
have?" then "who can change them?" — the second one meaningless without the first.

## Learning objective

`run_agent()` from Episode 6 starts from nothing every call. Give it somewhere to
remember a conversation, without pretending "remembering this chat" and "remembering
this user" are the same problem.

## Talking points

1. **Context vs. session state vs. long-term memory — three different things.**
   *Context* is what's actually sent to the LLM in one call (`Session.as_context()` —
   a bounded slice). *Session state* is the full conversation so far for one chat
   (`Session.turns` — could be longer than what fits in context; nothing here trims
   mid-session yet, that's a fair exercise). *Long-term memory* is facts that outlive
   the conversation entirely (`UserMemory` — keyed by `user_id`, not `session_id`).
   Conflating these into one "memory" blob is how you end up unable to answer "does
   deleting my chat forget my role preference too?"
2. **Retention.** `Session.add_turn()` trims to the last `max_turns` on every append,
   not as a separate cleanup job that's easy to forget to schedule. Unbounded history
   is both a cost that grows forever and a growing amount of someone's conversation
   sitting in memory for no active reason.
3. **Deletion.** `SessionStore.delete()` and `UserMemoryStore.forget_all()` are two
   different user controls with two different meanings, proven independent by test,
   not just asserted in a docstring: deleting a conversation must not be able to erase
   who the user is, and forgetting long-term facts must not delete their chat history.
4. **In-memory now, an interface for later.** `SessionStore` is an ABC;
   `InMemorySessionStore` is the only implementation this course ships, and it's lost
   on restart — that's what "local-first prototype" means here. A real deployment
   swaps in a SQL- or Redis-backed store behind the exact same interface; `ask()`,
   `run_agent()`, and everything above them would not change.
5. **The router needs history too.** "who can change them?" is unroutable alone.
   `classify()` (Episode 4) now takes `history=`, same as the specialist step — both
   halves of the loop see the same conversation, not just the answering half.
6. **A thin wrapper, not a new path.** `ask()` doesn't re-implement or relax anything
   `run_agent()` already enforces — `test_ask_does_not_bypass_the_agent_loops_evidence_rule`
   proves a `bug` specialist still can't skip evidence just because `ask()`, not
   `run_agent()` directly, is the entry point.

## Implement

- [`src/saas_copilot/memory/session.py`](../src/saas_copilot/memory/session.py) — `Turn`, `Session`.
- [`src/saas_copilot/memory/store.py`](../src/saas_copilot/memory/store.py) — `SessionStore`, `InMemorySessionStore`.
- [`src/saas_copilot/memory/user_memory.py`](../src/saas_copilot/memory/user_memory.py) — `UserMemory`, `UserMemoryStore`, `InMemoryUserMemoryStore`.
- [`src/saas_copilot/memory/orchestration.py`](../src/saas_copilot/memory/orchestration.py) — `ask()`.
- [`src/saas_copilot/router/classify.py`](../src/saas_copilot/router/classify.py) / [`src/saas_copilot/agent.py`](../src/saas_copilot/agent.py) — both take `history=` now.

## Run

```bash
pytest tests/unit/test_memory_session.py tests/unit/test_memory_user_memory.py \
       tests/unit/test_memory_orchestration.py -v
```

## Live demo (verified output, not illustrative)

```pycon
>>> ask(client, registry, store, "demo-session", "what statuses can a ticket have?").answer.answer
'Statuses are open, in_progress, resolved, closed.'
>>> ask(client, registry, store, "demo-session", "who can change them?").answer.answer
'A support_agent or support_lead can change them.'
>>> len(store.get("demo-session").turns)
2
>>> store.delete("demo-session")
>>> store.get("demo-session")
None
```

The second answer only makes sense because the router and specialist both saw the
first question and answer as history — ask a fresh session the same follow-up and it
has nothing to resolve "them" against.

## Exercise

`Session.turns` has no bound on total *size* — only Episode 14's evals will notice if
a handful of very long turns blow past what fits in context, even under
`max_turns`. Add a `Session.as_context(max_turns=..., max_chars=...)` limit that drops
the oldest turns first until the rendered context fits, and a test with a few
deliberately long fake turns proving it actually trims.

## Next

Episode 8 makes `search_docs` and `read_source` actually good at retrieval — chunking,
embeddings, reranking — instead of Episode 5's plain term-count search.
