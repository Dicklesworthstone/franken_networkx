# br-r37-c1-04z53.9121 rejection: DiGraph weight-float converter probe

Target: DiGraph attributed `add_edges_from` fresh exact-int construction.
Routing profile: `tests/artifacts/perf/20260616T-post-go994-routing-coppercliff/survey.json`.

One lever tested: reuse the existing single-`weight: float` attr conversion helper
inside `PyDiGraph::collect_fresh_exact_int_attr_edge_batch` before the generic
`py_dict_to_attr_map_with_mirror` fallback.

## Baseline

- Direct FNX median: `0.0073874639929272234s`
- Direct NX median: `0.006051262025721371s`
- cProfile FNX total: `0.805s / 160`
- cProfile `_try_add_edges_from_batch`: `0.790s / 160`
- Hyperfine FNX mean: `1.2608158253333335s`
- Hyperfine FNX median: `1.2622147542s`
- Hyperfine NX mean: `1.729450228s`

## Candidate

- Direct FNX median: `0.009289957000873983s`
- Direct FNX median speedup: `0.7952097078847861x`
- Direct FNX mean speedup: `0.7864623337418262x`
- cProfile FNX total: `0.986s / 160`
- cProfile `_try_add_edges_from_batch`: `0.972s / 160`
- Hyperfine FNX mean: `1.2916852427199998s`
- Hyperfine FNX median: `1.28549865712s`
- Hyperfine FNX mean speedup: `0.9761014399129758x`
- Hyperfine FNX median speedup: `0.9818872600208197x`

## Behavior Proof

- Golden digest before and after: `e603205862fdf5e9ed648d992331f9f236208d0d0bb5743ab01a1103a678c144`
- Semantics digest before and after: `334a1d40c776f5539620631bb1564c19a8cb7f5b5187bc120784808a2a264bd3`
- Focused parity while candidate installed: `26 passed in 0.45s`
- Ordering/tie-breaking: unchanged by identical golden digest over nodes and edge order.
- Floating point: stored `weight` values are copied unchanged; no arithmetic or RNG path changed.
- RNG: no runtime RNG path changed; benchmark edge fixture is deterministic.

## Decision

Rejected. Score: Impact `0` x Confidence `5` / Effort `1` = `0.0`.

This is the second small converter/mirror-family rejection in the construction
lane. The next DiGraph construction attack should avoid single-dict conversion
micro-levers and instead target a different primitive, such as an indexed fresh
row builder that preserves Python-visible attr mirrors while reducing hash-table
traffic and duplicate per-edge map work.
