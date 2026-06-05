# br-r37-c1-04z53.52 all_pairs_dijkstra weighted Dijkstra snapshot cache

## Target

Profile-backed residual: `all_pairs_dijkstra_weighted` in
`tests/artifacts/perf/20260604T-delegation-goldmine-sweep/bench_delegation_goldmines.py`.

Baseline hyperfine via rch:

- FNX: 2.32521515554 s mean, 2.26540204494 s median, 0.16017582040716635 s stddev.
- NX: 2.18965166284 s mean, 2.19983781894 s median, 0.062381123862794464 s stddev.
- Baseline relation: NX 1.06x faster than FNX.

Baseline cProfile via rch:

- `case_all_pairs_dijkstra`: 3.195 s cumulative over 120 repeats.
- `_call_networkx_for_parity`: 0.167 s cumulative.
- `_networkx_graph_for_parity`: 0.163 s cumulative.
- `_fnx_to_nx`: 0.159 s cumulative.

## One Lever

Add a Dijkstra-only NetworkX snapshot cache for simple `Graph`/`DiGraph`
weighted delegation. The cache is keyed by `(type(G), nodes_seq, edges_seq)` and
is used only when `dijkstra_weight_cache_token(G)` reports `edge_attrs_dirty ==
False`.

The lever also adds a native read-only `edge_py_attrs` scan for
`_graph_has_explicit_nonunit_weight`. The old Python scan used
`G.edges(data=True)`, which conservatively marked edge attrs dirty during an
internal read and would make the cache unusable.

## Behavior Proof

Ordering and tie-breaking:

- Weighted delegated `all_pairs_dijkstra` still calls NetworkX's
  `all_pairs_dijkstra`; no native result ordering is introduced.
- The cached object is the same `_fnx_to_nx` conversion shape used by the old
  path, preserving node insertion order and adjacency insertion order.
- Callable weights keep fresh conversion because user callables can mutate the
  copied edge-attribute dicts across calls.

Floating point:

- Edge weights are copied unchanged into the NetworkX graph.
- The new native explicit-weight probe mirrors Python `attrs[weight] != 1`
  with Python rich comparison and treats comparison errors as explicit non-unit,
  matching the fallback Python scan.

Mutation and invalidation:

- Node/edge structural mutation changes `nodes_seq` or `edges_seq`, invalidating
  the cache key.
- Visible edge-attribute mutation marks `edge_attrs_dirty`, bypassing the cache.
- Regression test proves a cached call followed by `G["a"]["c"]["weight"] = 1.0`
  matches NetworkX after mutation.

RNG:

- No random state is read or written.

Golden SHA:

- FNX old-disabled digest: `b799b17c9a68d0dc3e2f969a4a08636207d9d6fbb00eb30026e643fccbe913a7`.
- FNX new-cached digest: `b799b17c9a68d0dc3e2f969a4a08636207d9d6fbb00eb30026e643fccbe913a7`.
- NetworkX digest: `b799b17c9a68d0dc3e2f969a4a08636207d9d6fbb00eb30026e643fccbe913a7`.

## After Benchmark

After hyperfine via rch:

- FNX: 2.27978967564 s mean, 2.08109397404 s median, 0.46817906914311713 s stddev.
- NX: 2.59643821334 s mean, 2.26243281954 s median, 0.5503073822712337 s stddev.
- After relation: FNX 1.14x faster than NX.

Same-process lever control via rch:

- Old-disabled path: 0.011724446615699 s mean, 0.010583599971142 s median.
- New-cached path: 0.010702470322576 s mean, 0.009849708003458 s median.
- Lever speedup: 1.0955x mean, 1.0745x median.

Score: Impact 2 x Confidence 3 / Effort 1 = 6.0. Keep.

## Reprofile

After cProfile via rch:

- `_networkx_graph_for_parity` / `_fnx_to_nx` no longer appear in the hot list.
- Remaining residual is NetworkX execution:
  - `weighted.py:784(_dijkstra_multisource)`: 2.988 s cumulative over 120 repeats.
  - benchmark digest: 17.816 s cumulative over 120 repeats.

Next primitive: replace delegated weighted `all_pairs_dijkstra` with a native
generator-compatible weighted Dijkstra output path that preserves NetworkX
source order, per-source finalize order, distance numeric types, exception
contracts, and path list shape. Target ratio: at least 1.25x over NetworkX on
the weighted path case.

## Validation

- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed.
- `rustfmt --edition 2024 --check crates/fnx-python/src/algorithms.rs`: passed.
- `rch exec -- maturin develop --release --features pyo3/abi3-py310`: passed.
- `pytest tests/python/test_shortest_path.py -q`: 74 passed.
- `ubs --only=rust crates/fnx-python/src/algorithms.rs`: 0 critical; warnings are broad pre-existing inventory in the large file.

Validation gaps:

- `cargo fmt --check -p fnx-python` is blocked by unrelated formatting drift in
  `crates/fnx-python/src/digraph.rs` and `crates/fnx-python/src/lib.rs`.
- `cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
  is blocked by unrelated existing warnings in `crates/fnx-python/src/digraph.rs`
  and `crates/fnx-python/src/lib.rs`.
- `ubs --only=python python/franken_networkx/__init__.py tests/python/test_shortest_path.py`
  timed out after 60 s during the Python scan.
