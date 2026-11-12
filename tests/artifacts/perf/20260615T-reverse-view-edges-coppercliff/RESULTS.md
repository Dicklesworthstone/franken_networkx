# br-r37-c1-04z53.9110 Reverse View Edges

Workload: `list(DG.reverse(copy=False).edges())` on
`DiGraph(watts_strogatz_graph(1200, 8, 0.2, seed=3))`, 300 loops per run.

## Baseline

- FNX mean: `1.7377445066s`
- FNX median: `1.6988494897s`
- NetworkX mean: `0.5276182837s`
- NetworkX median: `0.5218874097s`
- Gap: NetworkX `3.29x` faster by mean.

Profile: `5.126s / 300` in `_ReverseDirectedViewBase._edges`, dominated by
Python predecessor-row mapping traversal and tuple append.

## Lever

One lever only: exact `DiGraph` bare reverse-view no-data edge materialization
now dispatches to `DiGraph._native_reverse_edges_no_data()`. The helper walks
the native predecessor rows in NetworkX order and emits `(target, source)`
tuples in one PyO3 batch.

The following surfaces intentionally stay on the existing path: data/key/default
variants, `nbunch`, `MultiDiGraph`, filtered/conversion views, and attr-aware
edge views.

## Proof

- Golden payload SHA before and after:
  `2e13b616a395c926d715ab7843bd713b1626a5cba9957d1348916f059c5105f3`
- Covered cases: edge order, `edges(data=True)`,
  `edges(data="w", default=-999)`, live source mutation, frozen mutation errors.
- Focused pytest: `6 passed`.
- FP/RNG: N/A.

## After

- FNX mean: `0.61648264192s`
- FNX median: `0.61414930512s`
- NetworkX mean: `0.52758984622s`
- NetworkX median: `0.52364381812s`
- FNX speedup: `2.82x` by mean.
- Remaining gap: NetworkX `1.17x` faster by mean.

Profile: `_native_reverse_edges_no_data` is now the dominant frame at
`0.220s / 300`; the old Python `_edges` hotspot is gone.

## Validation

- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- `ubs crates/fnx-python/src/digraph.rs python/franken_networkx/__init__.py tests/python/test_view_pickle_parity.py` hung after the Rust scan/Python scanner and was terminated; no final UBS verdict.

