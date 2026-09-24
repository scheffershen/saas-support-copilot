# Episode 2 — The smallest useful LLM call

**On screen:** `src/saas_copilot/llm/`, empty, then built up file by file.

## Learning objective

Every provider — hosted or local — speaks roughly the same shape: a list of messages
in, one message and a token count out. Build that shape once, behind an interface,
before touching a real API key.

## Talking points

1. **Messages.** A chat call is a list of `{role, content}` turns (`system`, `user`,
   `assistant`) — `Message` in `llm/base.py`. The system message is instructions, user
   messages are the conversation; nothing about that list is inherently trustworthy,
   which matters a lot once Episode 12 puts retrieved documents into it.
2. **Prompts, tokens, context windows.** A prompt is just the message list rendered to
   text; tokens are the provider's unit of both cost and context-window budget.
   `FakeLLMClient` estimates tokens at ~4 chars/token — good enough to reason about
   budgets, wrong as an actual tokenizer (Episode 14 revisits this for real cost
   tracking).
3. **Temperature.** `complete(..., temperature=0.2)` — low temperature for a support
   copilot that's supposed to answer consistently from evidence, not brainstorm.
4. **Provider APIs.** `OpenAICompatibleClient` speaks raw HTTP
   (`POST /chat/completions`) instead of wrapping a vendor SDK, because that exact
   shape is also what Ollama, LM Studio, and vLLM expose in "OpenAI-compatible" mode —
   swapping providers later is a `base_url` and a `model`, not a rewrite.
5. **Timeouts and retries.** The real client retries once on a timeout and gives up
   with a clear `LLMTimeoutError`; an HTTP error status (bad key, bad model) is *not*
   retried, because retrying a 401 five times just wastes five timeouts finding out
   what attempt one already told you.
6. **Provider abstraction.** `LLMClient` is an ABC with one method. Nothing else in
   this codebase is allowed to import `httpx` or know what "OpenAI-compatible" means —
   that knowledge stays inside `llm/`.

## Implement

- [`src/saas_copilot/llm/base.py`](../src/saas_copilot/llm/base.py) — `Message`,
  `Usage`, `LLMResponse`, `LLMError`, `LLMTimeoutError`, `LLMClient`.
- [`src/saas_copilot/llm/fake.py`](../src/saas_copilot/llm/fake.py) — `FakeLLMClient`.
- [`src/saas_copilot/llm/openai_compatible.py`](../src/saas_copilot/llm/openai_compatible.py) — `OpenAICompatibleClient`.
- [`src/saas_copilot/llm/__init__.py`](../src/saas_copilot/llm/__init__.py) — `build_llm_client(settings)`.
- Config: `LLM_BASE_URL` / `LLM_MODEL` added to `.env.example` and `Settings`.

## Run

```bash
pytest tests/unit/test_llm.py -v
```

Point it at a real provider (optional, needs a key):

```bash
export LLM_PROVIDER=openai LLM_API_KEY=sk-...
python -c "
from saas_copilot.config import settings
from saas_copilot.llm import build_llm_client
from saas_copilot.llm.base import Message
client = build_llm_client(settings)
print(client.complete([Message(role='user', content='Say hi in five words.')]).content)
"
```

## Failure case (show this live)

`tests/unit/test_llm.py` proves both failure paths *without touching the network*,
using `httpx.MockTransport` to stand in for the provider:

- `test_openai_compatible_client_retries_on_timeout_then_succeeds` — first call times
  out, second succeeds, caller never sees the failure.
- `test_openai_compatible_client_raises_llm_timeout_error_after_exhausting_retries` —
  every call times out → a clean `LLMTimeoutError`, not a raw `httpx` exception leaking
  out of the abstraction.
- `test_openai_compatible_client_raises_llm_error_on_http_status_error` — a 401 raises
  immediately, no retry.

## Exercise

Add a `max_tokens: int | None = None` parameter to `LLMClient.complete()`. Thread it
into `OpenAICompatibleClient`'s payload (only when not `None`); have `FakeLLMClient`
accept and ignore it. Write one test per client proving the signature change didn't
break either implementation. This is the recurring shape of extending an interface:
every implementation has to agree, and a test has to prove it.

## Next

Episode 3 wraps `LLMClient` output in a validated, typed `Answer` — and shows exactly
why a system prompt asking nicely for JSON is not the same thing as a guarantee.
