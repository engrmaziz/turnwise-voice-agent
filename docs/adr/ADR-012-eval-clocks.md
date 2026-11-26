# ADR-012: Eval clocks

- Status: Accepted
- Date: 2026-11-26

## Context

Phase 9 runs functional volume on a virtual clock so 900 calls are not 900 minutes of wall time. A 30-call real-time subset is the source for barge-in and TTFA that the SLO table may quote. Mixing the two clocks in one process would let a virtual silence threshold look like a measured P50.

## Decision

`TURNWISE_EVAL_TIME_SCALE` is **0** (virtual) or **1** (realtime). The driver is a separate process per mode. Matrix JSON always records `n`, `elapsed_s`, and `time_scale`. If the operator lowers `eval_matrix_n`, the file reports the actual n and must not claim 900.

Numbers that may be quoted in the README (T10.5.1):

- Task success from the DB judge.
- TTFA P50/P95 from the **realtime** subset only.

Virtual-clock early cutoff is labeled `virtual` and is not an SLO quote. Realtime n=30 that was not run is recorded as `skipped`, not as a guessed P50.

## Consequences

- CI smoke uses the scripted caller and the virtual clock. It does not fail on TTFA when the realtime artifact is missing or `skipped`.
- `eval_text_inject` is true only in the eval process. Production WebSocket does not implement text injection.
- The 900-call product is 50 × 3 × 3 × 2. This checkout reports the n that actually ran.
