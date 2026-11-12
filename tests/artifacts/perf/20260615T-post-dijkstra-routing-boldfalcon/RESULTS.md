# br-r37-c1-04z53.9104 - Graph attributed exact-int edge batch

## Target

Fresh post-Dijkstra routing found `Graph.add_edges_from([(u, v, {"weight": 1.0}), ...])` slower than NetworkX on a deterministic 2,000-node / 8,000-edge construction workload. Baseline cProfile put the residual inside `PyGraph._try_add_edges_from_batch`.

## Lever

One lever: add a fresh exact-int attributed edge batch for simple `Graph` that collects node labels once, commits the inner graph in index space, and preserves the existing generic attributed batch fallback for non-fresh graphs, global attrs, bool nodes, non-int nodes, invalid edge tuples, and unsupported attr values.

## Isomorphism Proof

- Ordering/tie-breaking: `graph_attr_batch_harness.py golden` compares full `nodes()`, `edges(data=True)`, adjacency prefixes, degree prefixes, and a duplicate-edge attr probe against NetworkX.
- Duplicate semantics: repeated undirected edges merge attrs in insertion order; the final duplicate wins per key while preserving earlier keys.
- Attribute identity: source input dicts are copied, not aliased; focused pytest mutates input dicts after construction.
- Floating point: only stored `1.0` payloads are copied; no arithmetic or rounding path changed.
- RNG: fixed harness seed `20260615`; the edge list is deterministic.
- Golden payload SHA: `2cc03e86353aa0bca84b567de31856b808c7b2c6fb8fc60b9462ecfebc752cfd` for both baseline and after payload files.
- Snapshot digest: `ee4bd77d10084e29dc3fe789a7daac5edf898b5745ef5475691b643f32c534c7` before and after.

## Timing

| Metric | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| FNX direct median | 11.674832 ms | 7.757990 ms | 1.50x faster |
| NetworkX direct median | 4.602571 ms | 4.673486 ms | comparator stable |
| FNX / NX direct median | 2.5366x | 1.6600x | residual narrowed |
| FNX hyperfine mean | 288.596 ms | 278.621 ms | 1.04x faster |

Hyperfine is startup/import dominated for this small construction workload; the direct harness and cProfile isolate the target path.

## Profile

`_try_add_edges_from_batch` over 120 FNX builds:

- Baseline: `1.182 s`
- After: `0.569 s`
- Speedup: `2.08x` in the profiled native batch frame

## Validation

- `cargo fmt --check`
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`
- `rch exec -- cargo test -p fnx-classes`
- `rch exec -- maturin develop --profile release-perf --features pyo3/abi3-py310`
- `python -m pytest tests/python/test_add_edges_attr_batch_parity.py tests/python/test_dicsr_cache_parity.py -q` (`40 passed`)
- `ubs crates/fnx-python/src/lib.rs crates/fnx-classes/src/lib.rs tests/python/test_add_edges_attr_batch_parity.py` exited 0; no critical issues, existing broad warning inventory remains.

## Score

Impact 3 x Confidence 4 / Effort 2 = 6.0. Keep.
