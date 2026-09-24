# Episode 1 — Python project foundations

> **Note (added in Episode 8):** `Document.citation` originally omitted the
> `#chunk-N` suffix when `chunk_id` was 0, treating 0 as "this document wasn't
> chunked." Once Episode 8 adds real chunking, chunk 0 is a genuine first chunk, not
> a sentinel - the citation now always includes it. The `Document`/`SourceFile`
> concepts below are unchanged; only that one property's exact output is.

**On screen:** `src/saas_copilot/models.py`, empty, in an editor; the Episode 0 repo
running in a split terminal.

## Learning objective

Every later episode hands data between functions, tools, and the LLM. Get the shape of
that data right now, with types and tests, so nothing downstream is guessing.

## Talking points

1. **Packages.** `src/saas_copilot/` is a real installable package — `pyproject.toml`
   declares it (`packages = ["src/saas_copilot"]`), and `pip install -e ".[dev]"` from
   Episode 0 is what makes `from saas_copilot.models import Document` work from
   anywhere, including `tests/`.
2. **Type hints.** Every field below is annotated. This isn't decoration — it's what
   lets your editor catch a typo today, and what lets structured LLM output (Episode 3)
   validate against a schema instead of hoping the model got the shape right.
3. **Dataclasses.** `@dataclass(frozen=True)` gives us equality, `repr`, and immutability
   for free. Immutability matters here specifically: once the copilot retrieves a
   `Document` to answer a question, nothing later in the pipeline should be able to
   quietly edit its content out from under the citation you're about to print.
4. **Exceptions.** `SourceFile.line()` raises `IndexError` with a specific, readable
   message instead of letting a bare index error escape. Episode 5's tools catch
   exactly this pattern and turn it into a clean tool-call error instead of a stack
   trace reaching the user.
5. **Async basics.** Loopline's endpoints and the copilot's `/health` are still plain
   `def` — there's no I/O yet, so `async def` would buy nothing. Episode 5 makes the
   tool-calling functions `async def`, because they'll do real file, database, and log
   reads and we don't want one slow tool call blocking every other request.
6. **venv / pyproject.toml / dependency pinning.** Recap from Episode 0: the `>=`
   ranges in `pyproject.toml` are fine for a course you re-run today, but a real
   deployment (Episode 16) wants an exact, locked set of versions so "works on my
   machine" doesn't bite you in production.
7. **pytest.** `tests/unit/test_models.py` sets the pattern for the rest of the course:
   one happy path and one failure path per behavior, not just one test per function.

## Implement

- [`src/saas_copilot/models.py`](../src/saas_copilot/models.py) — `Document`, `SourceFile`.
- [`tests/unit/test_models.py`](../tests/unit/test_models.py) — 6 tests.

## Run

```bash
pytest tests/unit/test_models.py -v
```

## Failure case (show this live)

```pycon
>>> from saas_copilot.models import SourceFile
>>> f = SourceFile(path="app/notifications.py", language="python", content="a\nb\nc")
>>> f.line(10)
IndexError: app/notifications.py has no line 10 (file has 3 lines)
```

## Exercise

Add a third model, `LogEntry` (`path`, `line_number`, `level`, `message`), with the
same discipline: a clear, specific exception on bad input rather than a bare crash or a
silent `None`. Write it, then write its tests before moving on. You'll wire it up for
real in Episode 5's log-reading tool.

## Next

Episode 2 makes the smallest possible real LLM call, behind a fake/real provider switch
so the course still runs with no API key.
