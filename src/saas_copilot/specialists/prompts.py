"""Per-domain prompt fragments, appended after ANSWER_SYSTEM_PROMPT. Each is short on
purpose - the shared prompt already covers citations, evidence-based answers, and
refusal; a specialist fragment only needs to say what's *distinctive* about its domain.
"""

USAGE_FRAGMENT = """\
This question is about USING Loopline as it exists today ("how do I...", "what is...").
Prefer search_docs first; only reach for read_source or search_code to verify a detail
the docs don't cover.
"""

BUG_FRAGMENT = """\
This question reports broken or unexpected behavior. Before you give a final_answer,
you MUST call at least one of: read_source, search_code, git_log, git_show, read_logs,
query_database. State the exact file and line (or commit, log line, or query result)
responsible - "the code doesn't handle X" is not evidence; a citation to where it
doesn't handle X is.
"""

FEATURE_FRAGMENT = """\
This question asks whether a capability could be added ("can it...", "could we add...").
Before you give a final_answer, you MUST call at least one of: read_source,
search_code, list_files, query_graph. If the change would touch a function other code
depends on, use query_graph(symbol, "callers") to check what else would be affected -
"this seems isolated" is a guess, a caller list is the check. Answer as a feasibility
assessment - what exists now, what's missing, a rough sense of scope, and what else the
change would touch - not a promise it will be built.
"""

GENERAL_FRAGMENT = """\
This question doesn't clearly fit usage, bug, or feature. Try search_docs first; if
nothing relevant turns up, refusing is a perfectly good answer.
"""
