# br-r37-c1-blgry Lazy Inner AttrMap Rejection

## Target

- Bead: `br-r37-c1-blgry`
- Surface: DiGraph attributed `add_edges_from` after the wrapper batch probe.
- Candidate: commit live Python edge-attribute dict mirrors immediately, insert
  inner directed adjacency with empty attrs, and mark `edges_dirty` so native
  weighted/attr kernels sync from the Python mirrors on demand.
- Primitive: representation-level deferred Rust `AttrMap` materialization.

## Baseline

- Baseline artifact: `tests/artifacts/perf/20260606T-digraph-add-edges-mirror-arena-cod/baseline_trusted_batch_timing.json`
- Direct FNX median: `0.0104194000s`
- Direct NetworkX median: `0.0038195670s`
- Ratio: `2.7279x`
- Baseline cProfile: `1.784s` total, `_try_add_edges_from_batch` `1.767s`.

## Candidate Result

- Golden SHA: `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- Focused add_edges parity: `16 passed`
- Direct timing repeat:
  - FNX median: `0.0123178030s`
  - NetworkX median: `0.0055421735s`
  - Ratio: `2.2226x`
- cProfile, 200 FNX builds:
  - total: `2.023s`
  - native `_try_add_edges_from_batch`: `1.993s`

## Verdict

- Rejected and source restored.
- Direct FNX median regressed `0.0104194000s -> 0.0123178030s`.
- cProfile regressed `1.784s -> 2.023s`.
- Source-restored timing sanity artifact:
  `tests/artifacts/perf/20260606T-digraph-add-edges-mirror-arena-cod/restored_after_lazy_reject_timing.json`.
- Score: Impact `0` x Confidence `5` / Effort `2` = `0`; do not keep.

## Isomorphism Proof

- Ordering preserved: candidate left node order, edge push order, and
  successor/predecessor row order unchanged.
- Tie-breaking unchanged: no graph algorithm tie policy touched.
- Floating-point unchanged: attr values stayed in Python dicts; weighted kernels
  sync through the existing dirty boundary.
- RNG unchanged: harness seed remained `20260606`.
- Golden outputs: SHA above unchanged; `sha256sum -c` passed from the artifact
  directory.

## Next Primitive

Do not retry lazy inner-attr deferral on this fixture. It adds dirty-sync
bookkeeping without removing the dominant native batch cost. The next attempt
should build a true slot descriptor: canonical endpoint strings and edge keys
should be allocated/probed once, then reused to commit both Python mirrors and
inner adjacency rows. Target direct ratio: `<=2.0x` vs NetworkX.
