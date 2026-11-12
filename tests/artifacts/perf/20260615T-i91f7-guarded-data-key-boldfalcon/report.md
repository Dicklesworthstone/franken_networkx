# br-r37-c1-i91f7 - DiGraph guarded edge-list native iterator

## Target

`br-r37-c1-i91f7` follows the `br-r37-c1-yuxi6` ordered attr-dict cache.
The remaining profile-backed residual for materialized `DiGraph.edges(data="w")`
and `DiGraph.edges.data("w")` was the Python `_FailFastEdgeIterator._gen`
frame, which checked structural mutation tokens once per yielded edge.

## Lever

The kept lever adds a `PyDiGraph` native guarded iterator over already
materialized edge-list items. It captures `nodes_seq` and `edges_seq` once,
checks them in Rust on `__next__`, and returns the prebuilt tuple item directly.
The Python `_EdgeListWithSetAlgebra.__iter__` hook uses it only for guarded
native `DiGraph` lists without NetworkX private storage.

## Baseline And Candidate

Baseline and candidate both use the deterministic 5k-node / 40k-edge DiGraph
from `guard_token_edgeview_harness.py`, with `loops=80`, `repeats=7`, and a
release rebuilt `fnx-python` extension.

Golden bundle SHA stayed unchanged:

- Baseline: `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`
- Candidate: `7f1f79e081e71ab0e4030308a1df76f3419b7a14bc8ee8a3d58ef2aa693aeeea`
- Candidate golden file SHA: `6b4ccd83d4948aaa685270ba125eb6b0a250d676a4bf7f8dc5c64d96e4613684`

Direct medians:

| Case | Baseline FNX | Candidate FNX | Speedup | Candidate FNX/NX |
| --- | ---: | ---: | ---: | ---: |
| `edges_data_w` | 9.589882 ms | 7.160249 ms | 1.339x | 1.280x |
| `edges_data_view_w` | 9.331185 ms | 7.223221 ms | 1.292x | 1.258x |
| `edges_data_true` | 3.951527 ms | 2.062206 ms | 1.916x | 0.234x |
| `out_edges_data_true` | 0.523241 ms | 0.504088 ms | 1.038x | 0.053x |
| `edges` | 7.400866 ms | 7.728537 ms | 0.958x | 2.969x |

Process-level hyperfine medians:

| Case | Baseline | Candidate | Speedup |
| --- | ---: | ---: | ---: |
| `edges(data="w")` FNX | 1.193032 s | 0.952194 s | 1.253x |
| `edges.data("w")` FNX | 1.151438 s | 0.955318 s | 1.205x |

## Profile Shift

`edges(data="w")`, 80 loops:

- `_FailFastEdgeIterator._gen`: `0.376 s -> absent from profile`
- `_native_edges_data_key`: `0.322 s -> 0.322 s`
- Total profiled target: `0.983 s -> 0.557 s`

The next residual for this consumer is now `_native_edges_data_key`, not the
fail-fast generator frame.

## Isomorphism Proof

- Ordering: byte-identical edge-output hashes versus NetworkX for `edges`,
  `edges(data=True)`, `edges(data="w")`, `out_edges(data=True)`, and
  `edges.data("w")`.
- Tie-breaking: unchanged; this is insertion-order edge-view draining only.
- Floating point: not applicable; graph uses integer node ids and integer attr
  `w`.
- RNG: not applicable; graph construction is deterministic.
- Mutation: structural edge mutation after iterator creation still raises
  `RuntimeError("dictionary changed size during iteration")`; `data=True`
  live attr-dict iteration still reflects attr-only updates.

## Validation

- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_edge_attr_dirty_sync.py tests/python/test_dicsr_cache_parity.py tests/python/test_attribute_access_parity.py -q`
  - `195 passed`
- Inline guarded-iterator mutation proof passed.
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m py_compile python/franken_networkx/__init__.py`
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python` import/smoke proof passed.
- `timeout 120s ubs --only=rust crates/fnx-python/src/digraph.rs crates/fnx-python/src/lib.rs crates/fnx-python/src/generators.rs`
  - exit `0`; no critical issues, existing broad warning inventory only.
- `ubs --only=python python/franken_networkx/__init__.py`
  - timed out at 180s after the initial scanner banner; no Python finding was emitted before timeout.

## Score

Impact `3` x Confidence `4` / Effort `2` = `6.0`; keep.
