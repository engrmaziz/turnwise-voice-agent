# ADR-009: Token-overlap FAQ retrieval

- Status: Accepted
- Date: 2026-11-26

## Context

Phase 6 answers clinic FAQ from local markdown (`data/faq.md`). The reply must be grounded in a chunk id. An empty retrieval speaks a refusal template. Hallucination in this phase is a reply with zero chunk ids. The ungrounded counter must stay at 0 on a miss.

A local embedding model would score semantic similarity. That needs weights, a worker pool, and a measured latency row. None of those exist yet. T1.4.3 (local LLM) is blocked.

## Decision

FAQ score is **token overlap** until a later ADR replaces it:

\[
\text{score}(q, d) = |T(q) \cap T(d)| / |T(q)|
\]

when \(T(q)\) is non-empty, else 0. Tokens are `[a-z0-9]+` after casefold. Chunks split on markdown `# ` headings. A score below `faq_min_score` (STARTING POINT 0.2) is a miss. A hit's spoken template includes the chunk id.

Embeddings are a **rejected** option for this milestone. They come back only with a new ADR that names weights and a measured p50.

## Consequences

- Overlap is deterministic. CI does not download an embedding model.
- Short queries that share stopwords with a chunk can false-hit; the 0.2 threshold is a starting point, not a tuned value.
- The LLM may paraphrase a grounded reply later. It does not retrieve. It does not invent a chunk id.
- `turnwise_faq_ungrounded_total` stays 0 when retrieval misses (`tests/test_faq_empty.py`).
