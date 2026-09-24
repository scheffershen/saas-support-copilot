# Prompting this build — how these 19 episodes actually got written

**On screen:** not code — this repository's own `git log --oneline` (75 real commits)
and the two-word instruction that produced most of them: `Continue to Episode N.`

## Why this document exists

Every lesson in this course teaches architecture, security, and verification
discipline through real, working code. None of them say who typed that code. This one
does: every line in `src/saas_copilot/`, every test, every one of the other 18 lesson
docs, was produced by one person directing an AI coding agent (Claude Code) through
natural language — never by hand-typing an implementation. That's not a caveat to
mention once and move past. It's worth its own lesson, because *how* to direct an
agent through a real, multi-session build is a distinct, learnable skill, and this
repository's construction is an honest, complete record of it — not a hypothetical.

## The claim worth being precise about

"Nobody hand-writes code anymore" overstates it — plenty still does, and always will
where it matters most. But the direction is real, and it's worth asking what that
actually changes here. Go back and reread any lesson in this course — Episode 5's
`resolve_within_root()`, Episode 10's `eligible_indices()`, Episode 13's uniform
`DATA_HEADER` wrapping. None of their talking points explain *how to type a Python
function*. Every one explains *why*: why a candidate-set restriction beats a post-hoc
filter, why stripping suspicious text corrupts legitimate content that happens to
discuss it, why an evidence gate has to reject a *failed* tool call as evidence, not
just require *some* tool call. That's the part that doesn't evaporate when an AI
agent writes the implementation — it's the part you need to understand well enough to
*ask for it correctly*, and the part you need to recognize when the agent's output
quietly gets it wrong instead. Architecture literacy and prompting well aren't
competing skills. The first is what makes the second possible.

## Talking points

1. **Standing rules, set once, hold for the whole build — that's what makes a
   two-word prompt work.** "Continue to Episode N" was, almost verbatim, the entire
   instruction for most of this course. That only works because a handful of rules
   were established once, early, and never had to be repeated: every episode ships
   code *and* tests *and* a lesson doc; every claim in a lesson doc gets verified
   against real output before it's written down, never invented; nothing proceeds to
   episode N+1 without that explicit instruction. A short prompt on top of an
   explicit, durable contract produces a disciplined result. A short prompt with no
   contract behind it produces whatever the agent guesses you meant.
2. **One prompt, one focused, tested change — not "build the whole thing."** Nobody
   ever asked for "the agent." The test count grew one verifiable step at a time:
   3 → 9 → 18 → 31 → 38 → 80 → 94 → 117 → 158 → 174 → 191 → 207 → 241 → 267 → 280 →
   297 → 305, across exactly as many real commits as capabilities. A prompt scoped to
   one reviewable capability produces a diff you can actually read end to end before
   trusting it. "Build a RAG pipeline with access control and an agent loop" does not.
3. **Demand verification, every time — "trust me" is not an acceptable answer from an
   agent any more than from a person.** Every lesson's "Live demo" and "Failure case"
   sections are real, captured output, not prose describing what probably would
   happen. Episode 9's call graph was checked interactively against Loopline's actual
   source *before* a single test was written. Episode 16's `localhost` vs `127.0.0.1`
   finding — a genuine 5-second connection delay — was measured, not assumed. If an
   agent's claim about its own output can't be re-run and re-checked, treat it as
   unverified, because it is.
4. **Catch overconfidence by checking the trace, not just the narration.** This
   applies recursively, and Episode 18 caught a real example of it: the live model's
   own answer text claimed *"a query_graph check... shows"* — and `tools_called`
   for that request was actually `["search_code"]`. The trace is what's checkable;
   the prose is a claim. The identical discipline applies one layer up, to an AI
   coding agent narrating what it did — read the diff, run the tests, don't take the
   summary as the verification.
5. **Correct drift in writing, don't silently rewrite history.** When Episode 8
   changed how `Document.citation` behaves, Episode 1's lesson got a dated addendum,
   not a quiet edit. When Episode 17 closed a gap Episode 10 had explicitly deferred,
   Episode 10's lesson got the same treatment. An agent that can silently edit its
   own prior claims to match new reality is an agent whose history you can no longer
   trust — the fix is a visible correction, every time, not a cleaner-looking rewrite.
6. **Investigate unfamiliar state before touching it — an agent should default to the
   same caution a careful engineer would.** A `.gitmodules` entry and a
   `video-production` directory turned up mid-course, unrelated to any of this work.
   The right response was to check what it was (the user's own separate tooling)
   before doing anything, then use pathspec-scoped commits for the rest of the course
   so nothing of it could get swept into an unrelated commit by accident.
7. **The prompt is not the security boundary — for a coding agent either.** This
   course spends Episodes 3, 12, and 13 proving that an LLM will follow a bad
   instruction as readily as a good one, and that real safety comes from validation,
   read-only contracts, and tests, not from asking nicely. The identical property
   holds one level up: an agent directed to "just make it work" will do exactly that,
   including cutting corners a careful prompt would have foreclosed. The actual
   safety net for *this* build was the standing rule (point 1), the human reviewing
   every diff before it was pushed, and a real test suite that had to stay green.
8. **None of this replaces points 1–7 of the other 18 lessons — it depends on them.**
   You cannot ask an agent to close a gap you can't describe. You cannot recognize a
   wrong answer you don't know is wrong. "Add role-based access control" and "restrict
   the candidate set before ranking, not after, so a paraphrase can't recover a
   restricted document" ask an agent for very different things, and only one of them
   is Episode 10. The architecture knowledge is not the part this course is teaching
   *around* — it's the part that makes the prompting work at all.

## Exercise

Pick any three episodes from this course and, without looking at how they were
actually built, write down what you believe the real instruction had to specify to
produce that exact diff, that exact test count, and that exact lesson doc — not "add
RBAC" but the actual property being enforced and how you'd know it was done correctly.
Then compare against what a bare "add access control" prompt would plausibly have
produced instead. The gap between those two is the actual skill this document is
about.

## Next

There is no next episode — this document sits alongside all 19, not inside their
sequence. Read it first if you're starting with [Episode 0](00-setup.md), or last if
you've just finished [the capstone](18-capstone-demonstration.md); it's about the
whole build, not one step of it.
