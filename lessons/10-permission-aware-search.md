# Episode 10 — Permission-aware search

**On screen:** the same question - "how do I force-deactivate a compromised
account?" - asked twice, once as `support_lead`, once as `support_agent`.

## Learning objective

A retrieval system that can find everything is a retrieval system that can leak
everything. Make role a first-class input to search, enforced at the layer that
decides what's even a *candidate*, not a suggestion the LLM is asked to respect.

## Talking points

1. **Document classification.** `security/classification.py`'s `RESTRICTED_DOCS` maps
   a path to the roles allowed to see it - `docs/admin-runbook.md` (seeded this
   episode: force-deactivating a compromised account) is `support_lead`-only, matching
   what `docs/roles-and-permissions.md` already says that role alone can do
   (deactivate users).
2. **Roles.** `security/roles.py`'s `ROLES` isn't an invented example set - it's
   exactly Loopline's own three roles, straight from `seed.py` and
   `roles-and-permissions.md`.
3. **Retrieval-time authorization, as a hard boundary.** `DocumentIndex.eligible_indices()`
   computes the allowed chunk-index subset *before* any ranking happens;
   `eligible` then restricts `BM25Index.search()` and the semantic ranking to only
   those indices. An ineligible chunk is never scored - not scored-then-hidden,
   never a candidate.
4. **Why "never a candidate" matters: paraphrase resistance.** A post-hoc filter (rank
   everything, then drop disallowed results) is only as safe as the filter step nobody
   forgets to call. `test_restricted_doc_stays_invisible_to_a_paraphrased_query_too`
   asks about the same restricted procedure in completely different words, sharing
   almost no vocabulary with the source doc - it still can't be found, because
   excluding the chunk from `eligible` makes the *question of how well it matches*
   never come up at all.
5. **Role is bound, never passed.** Same discipline as every allowlisted root since
   Episode 5: `role` is a `functools.partial` binding in `build_default_registry()`,
   never a field on `SearchDocsArgs`. If it were an LLM-suppliable argument, the model
   could simply claim to be searching as `support_lead` - the entire point of RBAC is
   that identity comes from the caller, not from what the caller's own request claims.
6. **A stated prototype gap, not a hidden one.** `is_visible_to(path, role=None)`
   defaults to visible-to-everyone - convenient with no auth layer yet, and explicitly
   documented as the wrong default for production, which must deny unknown identities,
   not allow them. Episode 17 revisits this.

   **Update (Episode 17):** closed - `role=None` is now the least-privileged caller,
   not the most. See [`lessons/17-prototype-vs-production-architecture.md`](17-prototype-vs-production-architecture.md)
   for the live before/after. What's described above was accurate through Episode 16;
   left as written rather than edited quietly, same as Episode 1's citation note.

## Implement

- [`src/saas_copilot/security/roles.py`](../src/saas_copilot/security/roles.py) — `ROLES`, `validate_role`.
- [`src/saas_copilot/security/classification.py`](../src/saas_copilot/security/classification.py) — `RESTRICTED_DOCS`, `is_visible_to`.
- [`sample_app/loopline/docs/admin-runbook.md`](../sample_app/loopline/docs/admin-runbook.md) — the seeded restricted doc.
- [`src/saas_copilot/retrieval/bm25.py`](../src/saas_copilot/retrieval/bm25.py) / [`retrieval/index.py`](../src/saas_copilot/retrieval/index.py) — `eligible` threaded through search.
- [`src/saas_copilot/tools/docs.py`](../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — `search_docs`/`build_default_registry` gain `role`.

## Run

```bash
pytest tests/unit/test_security_roles.py tests/unit/test_security_classification.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py tests/unit/test_tools_default_registry.py -v
```

## Live demo (verified output)

```pycon
>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_lead")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/admin-runbook.md', 'docs/roles-and-permissions.md', 'docs/notifications.md', ...}

>>> registry = build_default_registry(settings, repo_root=repo_root, role="support_agent")
>>> {d.path for d in registry.call("search_docs", {"query": "force-deactivate a compromised account"})}
{'docs/roles-and-permissions.md', 'docs/notifications.md', ...}   # admin-runbook.md: gone
```

(`admin-runbook.md` actually appears three times in the raw `support_lead` result
list before deduplication - it split into three chunks, Episode 8's chunking at work
on a doc just long enough to cross the 300-character boundary twice.)

## Failure case (the one that mattered while building this)

My first test for the unauthorized-role case asserted the query would find *nothing*.
It found five other docs. `roles-and-permissions.md` legitimately contains the phrase
"Deactivate users" in its own permissions table, and correctly still matches for every
role - it isn't restricted, it's just *about* a restricted action. The real property
isn't "an unauthorized search returns empty"; it's narrower and more precise: "the
restricted document specifically never appears." Asserting the stronger, wrong claim
would have made the test fail for a reason that had nothing to do with the security
property it was supposed to prove.

## Exercise

`eligible_indices()` takes a predicate, so it already generalizes past a single "which
roles" check. Add a second, independent classification dimension - restrict one doc by
*content sensitivity* (e.g., "financial") as well as role - and prove a query needs
both an allowed role AND an allowed sensitivity level to surface it
(`predicate = lambda doc: is_visible_to(doc.path, role) and is_sensitivity_allowed(doc.path, clearance)`).
This is the shape multi-tenant systems need for "role AND tenant," not just "role."

## Next

Episode 11 gives the `feature` specialist real planning structure: a bounded,
multi-step workflow instead of "call some tools, then answer."
