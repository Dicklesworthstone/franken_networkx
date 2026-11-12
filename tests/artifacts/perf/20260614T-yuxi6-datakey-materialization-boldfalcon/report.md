# br-r37-c1-yuxi6 - DiGraph data-key materialization

## Target

After `br-r37-c1-2a00r`, `DiGraph.edges(data=<key>)` still spent most of
its time in `_native_edges_data_key` and the Python fail-fast drain. This pass
keeps behavior fixed and attacks the native materialization side.

## Lever

One data-layout lever was kept:

- Cache live edge-attribute dict handles in edge iteration order when every edge
  has an attr dict. The cache is keyed by `(nodes_seq, edges_seq)` and stores
  dict handles, not attr values, so edge-attribute mutations remain visible.
- Add the empty-attribute-map path: when `edge_py_attrs` is empty, skip per-edge
  `(source, target)` key allocation and HashMap probing and return `default`
  directly for every edge.

The live shared tree already had the new `edges_attr_dicts_cache` field partially
introduced; this pass completed its `None` initializers so `fnx-python` builds.

## Golden Proof

Semantic SHA unchanged:
`5458482460dec697f761cfbdf7d960d269700ff45c0811e0f3dee9864703ac3a`.

Covered cases:
- Attribute modes: full, half, none.
- Edge data modes: `data="w"`, missing key with `default=-1`, `data=True`.
- Edge output order and values byte-match NetworkX for every case.
- Tie-breaking: N/A beyond insertion order.
- Floating point: N/A.
- RNG: N/A.

## Timing

Direct timing, deterministic 5k-node / 40k-edge DiGraph, `loops=60`,
`repeats=7`:

| Case | Baseline FNX | Final FNX | Speedup |
| --- | ---: | ---: | ---: |
| full attrs, `data="w"` | 15.724627 ms | 9.349769 ms | 1.682x |
| full attrs, missing key | 14.995482 ms | 9.237613 ms | 1.623x |
| half attrs, `data="w"` | 17.666788 ms | 9.117662 ms | 1.938x |
| half attrs, missing key | 16.571764 ms | 9.077022 ms | 1.826x |
| no attrs, `data="w"` | 9.242174 ms | 7.909372 ms | 1.169x |
| no attrs, missing key | 9.145640 ms | 8.103718 ms | 1.129x |

Hyperfine:

| Case | Baseline FNX mean | Final FNX mean | Speedup |
| --- | ---: | ---: | ---: |
| full attrs, `data="w"` | 1.501 s | 1.175 s | 1.278x |
| no attrs, missing key | 1.126 s | 0.939 s | 1.199x |

Profile shift:
- full attrs, `_native_edges_data_key`: 0.739 s -> 0.219 s over 60 loops.
- no attrs, `_native_edges_data_key`: 0.371 s -> 0.180 s over 60 loops.
- Python `_FailFastEdgeIterator._gen` remains the next residual.

## Validation

- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py -k 'edge_view_iteration' -q`
  - `2 passed, 431 deselected`
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_edges_nbunch_order_parity.py tests/python/test_dicsr_cache_parity.py::test_edges_walk_index_native_orientation -q`
  - `13 passed`
- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-python/src/digraph.rs crates/fnx-python/src/algorithms.rs crates/fnx-python/src/generators.rs crates/fnx-python/src/readwrite.rs tests/artifacts/perf/20260614T-yuxi6-datakey-materialization-boldfalcon/datakey_materialization_harness.py`
  - exit 0; no critical findings. UBS reported existing broad-file warning
    inventories.

## Score

Impact 3.5 x Confidence 4 / Effort 2 = 7.0. Keep.

Residual:
- The remaining cost is the Python fail-fast drain plus tuple/list creation.
  The next deeper primitive should replace the Python guarded drain with an
  exact fail-fast native iterator or another behavior-preserving C-level path.
