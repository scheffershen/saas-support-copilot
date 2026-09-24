# Episode 12 — Human approval and refusal

**On screen:** "Deactivate bob@loopline.example's account" - refused, zero LLM calls
made. "How do I deactivate a compromised account?" - answered normally, citing the
admin runbook.

## Learning objective

Every specialist so far has answered questions. None has ever been asked to *perform*
one - because nothing this agent can call writes anything; every tool has been
read-only since Episode 5. But a question can still be *phrased* as a command, and
routing it through the usual pipeline anyway would be dishonest about what happened:
nothing would actually get deactivated, but a fluent LLM answer could easily read as
if it had been. Give the agent a way to recognize that shape of request and say, in so
many words, "I can't do this, here's who can, and here's what I *can* tell you" -
before the question ever reaches a specialist.

## Talking points

1. **A deterministic gate, not an LLM judgment.** `security/intent.py`'s
   `detect_destructive_intent()` is plain regex over the raw question text - no model
   call. Episode 3 already established that a system prompt is a request, not a
   guarantee; a model-judged gate would be exactly as talkable-past as the thing it's
   supposed to guard. This runs in code the model never touches, before the model is
   even invoked for the turn.
2. **"You" vs "we" is the actual signal.** An imperative ("Deactivate...",
   "Delete...") or a "you"-directed command phrase leading straight into a destructive
   verb ("can you delete...", "please disable...") is a command. "could we" / "can we"
   is this course's own established feature-question idiom since Episode 4 ("could we
   add dark mode?") and is never mistaken for one -
   `test_a_feasibility_question_using_we_is_not_a_command` proves it directly. The
   command phrase also has to be *directly attached* to the verb, not just present
   somewhere earlier in the sentence - "can you check if we should delete stale
   tickets" is not a command to delete anything.
3. **Exact-verb matching solves past tense for free.** "deactivate" is not
   "deactivated" - a bug report about something that already happened
   (`"the account got deactivated, why?"`) keeps routing to the bug specialist
   normally, with no tense-detection logic required. Just don't stem the verb list.
4. **Two independent layers, not one.** This gate catches natural-language commands,
   in code the model never runs. It does *not* catch SQL-shaped phrasing dressed up as
   an innocuous request (`"run this: DROP TABLE tickets"`) - proven directly, not just
   claimed (`test_sql_shaped_input_is_not_this_layers_job`). That's `query_database`'s
   own job (point 7) - a second, independent layer, because a single layer that's
   supposed to catch everything eventually has something get past it.
5. **The refusal *is* the escalation path.** `build_refusal_answer()` doesn't just say
   no - it names who actually can do this (a human, with the right role, following
   Loopline's own process) and how to get an explanation instead of a refusal. "No"
   alone would be honest but useless.
6. **Confirmation reuses memory instead of inventing new state.** A bare "yes" after a
   refusal means nothing on its own. `agent.py::_confirmed_original_question()`
   recognizes the shape - an affirmative reply immediately after *this gate's own*
   refusal, detected via a fixed marker string in the previous assistant turn - and
   re-asks the *original* question reframed as an explanation request, using Episode
   7's existing `history`, not a new session-state field.
7. **New tools, same discipline as every tool since Episode 5.** `query_database`:
   read-only enforced twice - a SELECT-only prefix check for a fast, clear error, and
   the SQLite connection itself opened in read-only URI mode, so a statement that
   somehow got past the regex still can't write. Proven directly against the real
   driver (`test_the_database_file_is_opened_read_only_not_just_regex_checked`), not
   assumed. `read_logs`: no path argument at all - it always reads the one log file
   its root is bound to at registry-build time, the same `functools.partial` pattern
   as every allowlisted root since Episode 5.
8. **The bug specialist gets two new ways to gather evidence.** `required_evidence_tools`
   grows to include `read_logs` and `query_database` - checking real data or log state
   counts as evidence, same as reading source. `query_database` in particular can
   directly confirm the seeded notification bug's root cause: `notification_settings`
   really does have zero rows for user 5.

## Implement

- [`src/saas_copilot/security/intent.py`](../src/saas_copilot/security/intent.py) — `detect_destructive_intent`, `build_refusal_answer`, `CONFIRMATION_MARKER`.
- [`src/saas_copilot/agent.py`](../src/saas_copilot/agent.py) — the gate and `_confirmed_original_question()`, checked before `classify()`.
- [`src/saas_copilot/tools/database.py`](../src/saas_copilot/tools/database.py) — `query_database`, `resolve_sqlite_path`.
- [`src/saas_copilot/tools/logs.py`](../src/saas_copilot/tools/logs.py) — `read_logs`.
- [`src/saas_copilot/tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — both tools registered; `loopline.db` seeded idempotently at build time.
- [`src/saas_copilot/specialists/specialist.py`](../src/saas_copilot/specialists/specialist.py) / [`prompts.py`](../src/saas_copilot/specialists/prompts.py) — bug's evidence set grows.

## Run

```bash
pytest tests/unit/test_security_intent.py tests/unit/test_tools_database.py \
       tests/unit/test_tools_logs.py tests/unit/test_agent.py \
       tests/unit/test_specialists.py tests/unit/test_tools_default_registry.py -v
```

## Live demo (verified output)

```pycon
>>> detect_destructive_intent("Deactivate the account for bob@loopline.example")
DestructiveIntentMatch(verb='deactivate', question='Deactivate the account for bob@loopline.example')
>>> detect_destructive_intent("how do I deactivate a compromised account?")
None

>>> client = FakeLLMClient(responses=["SHOULD NEVER BE READ"])
>>> result = run_agent(client, registry, "Deactivate the account for bob@loopline.example")
>>> result.answer.refused, client.call_count
(True, 0)
>>> result.answer.answer
"I can't perform this action myself - every tool I can call is read-only, so there is
no way for me to actually deactivate anything. If this needs to happen right now, it
needs a human with the right role, following Loopline's own process (see the admin
runbook for account actions). If you want an explanation of the process instead - what
it involves, who can do it - just ask, for example \"how do I deactivate an
account?\", or reply \"yes\" and I'll explain this one."

>>> # user replies "yes please" - history carries the refusal from above
>>> result2 = run_agent(client2, registry, "yes please", history=history)
>>> result2.answer.refused
False
>>> [m.content for m in client2.received_messages[0] if m.role == "user"][-1]
'Explain how to do this, without performing it: Deactivate the account for bob@loopline.example'
```

```pycon
>>> registry.call("query_database", {"sql": "SELECT * FROM notification_settings WHERE user_id = 5"})
[]   # confirmed: user 5 really has no row - the seeded bug's exact root cause
>>> registry.call("read_logs", {"tail": 2, "grep": "notifications"})
['2026-09-23 09:12:30 INFO  loopline.notifications: notified user_id=2 re ticket_id=2',
 '2026-09-23 15:47:02 ERROR loopline.notifications: failed to notify assignee for ticket_id=4']
```

## Failure case (show this live)

```pycon
>>> registry.call("query_database", {"sql": "DELETE FROM users"})
ToolError: query_database only allows SELECT statements
```

That's the fast, clear error from the prefix check. The deeper guarantee is proven
separately, straight against the driver, bypassing this code's own regex entirely: the
same read-only URI `query_database` connects with raises
`sqlite3.OperationalError: attempt to write a readonly database` the instant anything
tries to write through it - regardless of what the SQL text looked like.

## Exercise

Right now, a refusal followed by anything other than one of a fixed set of "yes"-shaped
phrases (`_AFFIRMATIVE_RESPONSES`) just falls through to ordinary routing - including an
explicit "no." Add decline handling: recognize a small set of "no"-shaped replies
(`"no"`, `"never mind"`, `"cancel"`) immediately following this gate's own refusal, and
return a short, clean closing acknowledgment instead of letting an unroutable "no" reach
the router. Write a test proving a *bare* "no" with no preceding refusal is still just
an ordinary (unroutable) question, the same property
`test_a_bare_affirmative_with_no_preceding_refusal_is_not_treated_as_a_confirmation`
already proves for "yes."

## Next

Episode 13 defends against a harder version of the same problem: this episode's gate
trusts that a command typed by the user, in the chat turn itself, is what it looks
like. It says nothing about a command hiding *inside* a document, a log line, or a
tool result the agent reads along the way - text the agent was never supposed to treat
as instructions at all. Direct and indirect prompt injection, instruction/data
separation, and secret redaction are next.
