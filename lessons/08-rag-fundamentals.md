# Episode 8 — RAG fundamentals

**On screen:** Episode 5's `search_docs` scoring a query by raw term count, next to
the same query about to go through BM25 + embeddings instead.

## Learning objective

Retrieval-augmented generation is four real steps, not a library import: split text
into pieces small enough to be useful, turn each piece into something comparable to a
query, rank by that comparison, and combine more than one ranking method when they
disagree. Build all four from scratch, once, so "RAG" stops being a black box.

## Talking points

1. **Ingestion and normalization.** `normalize_text()` fixes line endings and strips
   Markdown heading markers - layout, not content - before anything else touches the
   text. Small, but it's the first place bad input quietly becomes bad retrieval.
2. **Chunking.** Fixed-size chunks with overlap (`chunk_text()`). Too large and a
   real answer gets diluted by irrelevant surrounding text; too small and it loses
   context; overlap keeps a sentence that straddles a chunk boundary from being cut in
   half. `getting-started.md`, the longest Loopline doc, genuinely splits into 2
   chunks at this course's 300-character size - not a contrived example.
3. **BM25 full-text search.** `BM25Index` is a real, from-scratch Okapi BM25, not a
   library call: term-frequency saturation (a term's 10th occurrence matters far less
   than its 1st) and length normalization (a long document isn't more relevant just
   for containing more words) - the two things Episode 5's raw term-count scoring got
   wrong.
4. **Embeddings.** `EmbeddingClient` is Episode 2's `LLMClient` pattern again, applied
   to a new problem - depend on "something that embeds text," never a provider.
   `HashingEmbeddingClient` is the course default: deterministic, offline, same
   philosophy as `FakeLLMClient`. It gets vector-search *mechanics* right and has no
   real semantic understanding - a real gap, documented, not hidden.
5. **Reranking / hybrid search.** BM25 scores and cosine similarities live on
   incomparable scales, so `reciprocal_rank_fusion()` combines *ranks*, not raw
   scores - the same technique Elasticsearch's hybrid search uses.
6. **Citations.** `Document.citation` now means something: `docs/getting-started.md#chunk-0`
   and `#chunk-1` are genuinely different, retrievable pieces of the same file.

## Two real bugs, found while building this

Same discipline as Episode 5: neither was planted, both surfaced from running tests.

**A stopword false-positive.** Testing "no match" with the query
`"xyzzy-not-a-real-term"` produced a match - and not a low-confidence one. Its "not"
and "a" hash-collided with common words scattered across every doc, giving it *higher*
semantic similarity to an unrelated article than a genuine query scored against the
right one. Fixed with a short stopword list in `HashingEmbeddingClient`'s tokenizer.

**The deeper bug stopword filtering didn't fix.** Even with real gibberish
(`"zzqvxlpfmnbwortkugh"`, sharing no vocabulary with anything), `search_hybrid` still
returned results. `_semantic_ranking` had no relevance floor at all - it sorted
*every* chunk by cosine similarity, including chunks sitting at exactly `0.0`. Semantic
"search" could only ever reorder the whole corpus, never actually find nothing. Fixed
with a `min_similarity` floor (`DEFAULT_MIN_SIMILARITY = 0.05`) applied before ranking,
not after.

## Implement

- [`src/saas_copilot/retrieval/normalize.py`](../src/saas_copilot/retrieval/normalize.py) — `normalize_text`.
- [`src/saas_copilot/retrieval/chunking.py`](../src/saas_copilot/retrieval/chunking.py) — `chunk_text`.
- [`src/saas_copilot/retrieval/bm25.py`](../src/saas_copilot/retrieval/bm25.py) — `BM25Index`.
- [`src/saas_copilot/retrieval/embeddings.py`](../src/saas_copilot/retrieval/embeddings.py) — `EmbeddingClient`, `cosine_similarity`.
- [`src/saas_copilot/retrieval/hashing_embeddings.py`](../src/saas_copilot/retrieval/hashing_embeddings.py) — `HashingEmbeddingClient`.
- [`src/saas_copilot/retrieval/rrf.py`](../src/saas_copilot/retrieval/rrf.py) — `reciprocal_rank_fusion`.
- [`src/saas_copilot/retrieval/index.py`](../src/saas_copilot/retrieval/index.py) — `DocumentIndex`.
- [`src/saas_copilot/tools/docs.py`](../src/saas_copilot/tools/docs.py) / [`tools/__init__.py`](../src/saas_copilot/tools/__init__.py) — `search_docs` rewired onto the index.
- [`src/saas_copilot/models.py`](../src/saas_copilot/models.py) — `Document.citation` now always includes the chunk suffix (see the Episode 1 note).

## Run

```bash
pytest tests/unit/test_retrieval_normalize.py tests/unit/test_retrieval_chunking.py \
       tests/unit/test_retrieval_bm25.py tests/unit/test_retrieval_embeddings.py \
       tests/unit/test_retrieval_rrf.py tests/unit/test_retrieval_index.py \
       tests/unit/test_tools_docs.py -v
```

## Failure case (real, from this episode's own development)

```pycon
>>> len(index)   # 5 docs, 7 chunks - getting-started.md and roles-and-permissions.md each split in two
7
>>> index.search_semantic("zzqvxlpfmnbwortkugh", min_similarity=-1.0)   # the old, floor-less behavior
[<all 7 chunks, "ranked" at exactly 0.0 similarity>]
>>> index.search_semantic("zzqvxlpfmnbwortkugh")   # today's default floor
[]
```

A "ranking" with no floor isn't search. It's just an ordering opinion about things
that were never candidates in the first place.

## Exercise

`DEFAULT_MIN_SIMILARITY = 0.05` was picked by looking at this specific corpus's
numbers, not derived from anything principled - exactly the kind of magic number a
real system calibrates against data instead of eyeballing. Build a tiny "does it
match" eval set (5-10 query/expected-doc pairs covering Loopline's docs) and sweep a
few threshold values against it, picking the one that best separates real matches from
noise. (Full preview of Episode 15 - this is that idea at the smallest possible scale.)

## Next

Episode 9 adds a second retrieval paradigm alongside this one: a lightweight call
graph over Loopline's own source, for questions text search can't answer well
("what would changing this function break?").
