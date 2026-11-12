# perf: condensation native bulk construction (br-r37-c1-yaane)

## Target

Profile-backed construction gap in `fnx.condensation(G)` on sparse directed
graphs whose SCCs are mostly singletons. The old public path computed
NetworkX-ordered SCCs correctly, then rebuilt the result `DiGraph` through
Python `add_node` / `add_edge` loops. Baseline cProfile showed 59,950
`DiGraph.add_edge` calls dominating the condensation body.

## Lever

One native bulk-construction path for `scc is None`:

- compute SCCs with the existing `strongly_connected_components_nx_ordered`
  helper, preserving NetworkX SCC label order;
- build node labels, `members` sets, and `graph["mapping"]` while still in
  the binding;
- iterate original `DiGraph::edges_ordered()` once, dedupe cross-component
  edges in first-occurrence order, and insert them via
  `DiGraph::extend_edges_unrecorded`;
- route `franken_networkx.components.condensation` through the same public
  fnx implementation instead of NetworkX round-trip conversion.

## Proof

- Ordering preserved: SCC labels follow `strongly_connected_components_nx_ordered`;
  condensation edges follow original `G.edges()` / `edges_ordered()` order with
  first-occurrence dedupe, matching the old Python loop.
- Tie-breaking unchanged: SCC order helper is unchanged.
- Floating-point: N/A.
- RNG: N/A.
- Golden output: `e291a3fd2c9b9177608932917dab4d5d317ea3337f76700d266a1e658cc7f745`.
- Parity: 65 deterministic cases, 0 failures.
- Focused pytest: `tests/python/test_condensation_contract_parity.py` passed
  (`2 passed`).

## Benchmarks

Process-level rch hyperfine, `n=3000 degree=4 repeat=3`:

- before FNX: 633.4 ms mean; NetworkX: 482.0 ms mean.
- after FNX: 631.7 ms mean; NetworkX: 545.8 ms mean.

That process-level run is import/startup-noise dominated. The same-worker
repeat-heavy old-vs-new run isolates the condensation construction lever:

- old Python construction: 1.704 s mean, 1.712 s median.
- native bulk construction: 1.318 s mean, 1.314 s median.
- self-speedup: 1.29x.

Score: Impact 2 x Confidence 4 / Effort 3 = 2.67, keep.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `cargo fmt --check -p fnx-python`
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- `PYTHONDONTWRITEBYTECODE=1 pytest tests/python/test_condensation_contract_parity.py -q`
- `ubs crates/fnx-python/src/algorithms.rs tests/artifacts/perf/20260605T-condensation-bulk-yaane/bench_condensation.py`

The broader `ubs` run including the large `python/franken_networkx/__init__.py`
completed the Rust scan and then stalled in the Python scan; a narrow scan of
the touched Rust file and harness completed with zero critical issues and only
pre-existing broad warnings in `algorithms.rs`.
