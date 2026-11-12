# yxmdc: native order-invariant aggregation kernels

## Target

`br-r37-c1-yxmdc` after the partial `s_metric` wrapper route. The live
`s_metric` residual did not reproduce, so this pass targeted the remaining
order-invariant aggregation path: undirected `transitivity`.

## Baseline

- `s_metric` reprofile, BA(1500, 4, seed=19): `_fnx.s_metric` median
  `0.400 ms`, public `fnx.s_metric` median `0.498 ms`, NetworkX median
  `3.760 ms`; proof SHA
  `0069324bb819151aac12db2b28b990f668605dbe0e869e8a229bcfa850530466`.
- `transitivity`, BA(1500, 4, seed=19): raw `_fnx.transitivity` median
  `82.455 ms`, public `fnx.transitivity` median `83.336 ms`, NetworkX median
  `22.887 ms`; proof SHA
  `4b5c53e2a2fc0616eb35010090a1457bfda7d87d6a6e842144bda379f01ad2ce`.

## Lever

`clustering_coefficient` now counts undirected triangle participation over
integer adjacency rows. It marks the current node's neighbor set in a reusable
boolean side table and counts neighbor-neighbor hits by index, avoiding
per-node `Vec<&str>` allocation and string-keyed `has_edge` hashing.

This is a GraphBLAS-style sparse-structure lever: operate over the graph's CSR
rows directly and keep the scalar aggregation order-independent.

## Proof

- Ordering/tie-breaking: public result is a scalar; per-node clustering score
  output order remains `nodes_ordered()`.
- Floating point: triangle and triad totals are unchanged integers; final
  division formula is unchanged.
- RNG: none.
- Golden output: transitivity proof SHA stayed
  `4b5c53e2a2fc0616eb35010090a1457bfda7d87d6a6e842144bda379f01ad2ce`.

## After

- Raw `_fnx.transitivity`: `82.455 ms -> 0.350 ms` median (`235.67x`).
- Public `fnx.transitivity`: `83.336 ms -> 0.352 ms` median (`236.95x`).
- NetworkX reference remained `~23 ms`.
- Hyperfine after: `419.8 ms +/- 13.2 ms` for 200 public calls.

Score: `Impact 5 * Confidence 5 / Effort 2 = 12.5`.

## Validation

- `rch exec -- cargo check -p fnx-algorithms --all-targets`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-algorithms --all-targets -- -D warnings`
- `rch exec -- cargo test -p fnx-algorithms clustering_coefficient -- --nocapture`
- `python3 -m pytest tests/python/test_graph_metrics.py tests/python/test_graph_metrics_conformance.py tests/python/test_network_summary_measures_conformance.py -k 'transitivity or clustering or s_metric' -q`
- `cargo fmt -p fnx-algorithms --check`
- `python3 -m py_compile tests/artifacts/perf/20260609T-yxmdc-s-metric-kernel-tealspring/harness_yxmdc.py python/franken_networkx/__init__.py`

`fnx-python` clippy currently fails on pre-existing peer node-key cache lints in
`crates/fnx-python/src/lib.rs` and `crates/fnx-python/src/digraph.rs`; this
pass did not edit those files.
