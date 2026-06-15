# br-r37-c1-yuxi6 - DiGraph data-key ordered attr-dict cache

## Target

`br-r37-c1-yuxi6` follows the `br-r37-c1-2a00r` endpoint-key fast path. The
remaining profile-backed residual for `DiGraph.edges(data="w")` was repeated
live edge-attr lookup and tuple materialization in `_native_edges_data_key`.

The kept lever adds a `PyDiGraph` cache of live edge-attr `PyDict` handles in
edge iteration order, keyed by `(nodes_seq, edges_seq)`. It caches only dict
handles, not attribute values, so `G[u][v]["w"] = new_value` remains visible.
The fast path activates only when every edge already has an attr dict.

## Baseline

Baseline was taken from current head after rebuilding the release extension:

- `rch exec -- maturin develop --release --features pyo3/abi3-py310`
- Golden bundle SHA: `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`
- Golden file SHA: `6b4ccd83d4948aaa685270ba125eb6b0a250d676a4bf7f8dc5c64d96e4613684`

Direct medians, 40k-edge deterministic DiGraph, `loops=80`, `repeats=9`:

| Case | Baseline FNX | Candidate FNX | Speedup |
| --- | ---: | ---: | ---: |
| `edges(data="w")` | 16.366747 ms | 9.735142 ms | 1.681x |
| `edges.data("w")` | 18.217452 ms | 9.870892 ms | 1.846x |

Process-level hyperfine medians, `runs=7`:

| Case | Baseline FNX | Candidate FNX | Speedup |
| --- | ---: | ---: | ---: |
| `edges(data="w")` | 1.632488 s | 1.226563 s | 1.331x |
| `edges.data("w")` | 1.757466 s | 1.233897 s | 1.424x |

Profile shift over 80 loops:

- `_native_edges_data_key`: `0.873 s -> 0.375 s`
- `_FailFastEdgeIterator._gen`: `0.404 s -> 0.370 s`
- Total profiled target: `1.582 s -> 1.046 s`

## Isomorphism Proof

- Ordering: byte-identical edge-output hashes versus NetworkX for `edges`,
  `edges(data=True)`, `edges(data="w")`, `out_edges(data=True)`, and
  `edges.data("w")`.
- Tie-breaking: unchanged; edge-view drains preserve insertion order.
- Floating point: not applicable; workload uses integer node ids and integer
  edge attribute `w`.
- RNG: not applicable; graph construction is deterministic.
- Mutation: structural edge mutation still raises
  `RuntimeError("dictionary changed size during iteration")`; attr-only updates
  remain visible through the cached live dict handles.

## Validation

- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_edge_attr_dirty_sync.py tests/python/test_dicsr_cache_parity.py tests/python/test_attribute_access_parity.py -q`
  - `195 passed`
- Inline live-attr proof: cached `edges(data="w")` reflects attribute updates and
  still raises on mid-iteration structural mutation.
- `timeout 120s ubs crates/fnx-python/src/digraph.rs`
  - exit `0`; no critical findings, existing broad-file warning inventory only.

## Score

Impact `3` x Confidence `4` / Effort `2` = `6.0`; keep.

Residual: the Python `_FailFastEdgeIterator._gen` frame is now the largest
remaining target for this consumer.
