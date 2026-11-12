# br-r37-c1-04z53.57 Endpoint Canonical Cache Rejection

## Target

- Surface: attributed `DiGraph.add_edges_from` batch construction.
- Profile-backed residual: pass 6 left `_try_add_edges_from_batch` as the
  dominant cProfile frame.
- Candidate lever: batch-local canonical string cache for repeated plain
  int/float/string endpoints, preserving the existing display-conflict fallback.

## Baseline

- Direct timing, `n=1500`, `edges=5217`, `loops=80`:
  - FNX median: `0.01127832499332726s`
  - NetworkX median: `0.003926566976588219s`
  - Ratio: `2.872311884802474x`
- Hyperfine mean: `0.50028626336s`
- Hyperfine median: `0.49617633756s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `1.735s`

## Candidate Result

- Direct timing:
  - FNX median: `0.012523301498731598s`
  - NetworkX median: `0.004276822990505025s`
  - Ratio: `2.928178586426088x`
- Hyperfine mean: `0.5726019359800001s`
- Hyperfine median: `0.5404474299800001s`
- cProfile, 200 FNX builds:
  - native `_try_add_edges_from_batch`: `1.834s`

## Proof

- Golden proof command: `.venv/bin/python tests/artifacts/perf/20260606T-digraph-add-edges-batch-cod/digraph_add_edges_batch_harness.py proof --cases 8`
- Golden SHA unchanged:
  `c6f6227073dc924849e81ae552df913fcfaf278a522aae3abccdca2605eb6f48`
- `sha256sum -c golden_add_edges_batch.sha256`: passed.

## Isomorphism Notes

- Ordering: candidate did not reorder edge stream, node insertion, successor
  rows, predecessor rows, or duplicate merge order.
- Tie-breaking: no graph algorithm tie policy changed.
- Floating-point: no arithmetic was introduced; finite integral floats would
  still canonicalize through the existing integer canonical form.
- RNG: unchanged; harness seed remains `20260606`.
- Error semantics: fallback paths for non-plain endpoints and incompatible
  attrs were preserved.

## Verdict

- Rejected.
- Direct FNX median regressed `0.01127832499332726s -> 0.012523301498731598s`.
- Hyperfine mean regressed `0.50028626336s -> 0.5726019359800001s`.
- cProfile native time regressed `1.735s -> 1.834s`.
- Score: Impact `0` x Confidence `5` / Effort `2` = `0.0`.
- Source change was removed; only this rejection artifact remains.

## Next Primitive

Do not repeat endpoint canonical cache micro-tuning. The next pass should attack
the structural batch representation: carry edge Python-attribute mirrors and
Rust `AttrMap` payloads through a compact descriptor that reduces per-edge
`PyDict` entry/update and attr conversion work while preserving NetworkX
duplicate merge order and source-dict non-aliasing. Target ratio remains
`<=2.0x` vs NetworkX on the same fixture.
