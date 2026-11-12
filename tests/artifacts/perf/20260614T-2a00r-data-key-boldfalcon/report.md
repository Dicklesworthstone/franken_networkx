# br-r37-c1-2a00r Pass 4 - DiGraph data-key endpoint-key fast path

## Target

`_native_edges_data_key` was still the largest native frame for
`list(DiGraph.edges(data="w"))` after the guard-token candidate was rejected.
The one kept lever is narrow: when `succ_py_keys` is empty, reuse the cached
node-key vector and integer edge indices instead of re-hashing source and
successor string names for every output tuple.

## Baseline

Baseline worktree:
`/data/projects/.scratch/franken_networkx-2a00r-data-key-baseline-20260614T2350`
at `3e4b47980`.

The later `605870d2e` commit touched only readwrite parsing and its artifact
report, not `crates/fnx-python/src/digraph.rs` or the EdgeView harness, so the
baseline remains directly comparable to this isolated hunk.

## Golden Proof

Path-independent semantic SHA:
`12ee8486bd50a411dcacd6c7d11f6221c2660301e425c0895b6a7139ab546c21`.

This hash is computed from edge output cases, mutation cases, and explicit
isomorphism obligations, excluding the checkout-specific `franken_networkx_file`
metadata path.

Obligations:
- Ordering: byte-identical edge-output hashes versus NetworkX for `edges`,
  `edges(data=True)`, `edges(data="w")`, `out_edges(data=True)`, and
  `edges.data("w")`.
- Tie-breaking: unchanged; edge views are insertion-order drains only.
- Floating point: not applicable; workload uses integer node ids and integer
  edge attribute `w`.
- RNG: not applicable; graph construction is deterministic and seed-free.
- Mutation behavior: existing structural edge mutation parity and FNX current
  node/edge guard obligations still pass.

## Timing

Direct timing, 40k-edge deterministic DiGraph, `loops=80`, `repeats=9`:

| Case | Baseline FNX | Candidate FNX | Speedup | Baseline FNX/NX | Candidate FNX/NX |
| --- | ---: | ---: | ---: | ---: | ---: |
| `edges(data="w")` | 19.903964 ms | 17.202795 ms | 1.157x | 3.258x | 2.859x |

Hyperfine, same graph and loop count, `runs=7`:

| Case | Baseline FNX mean | Candidate FNX mean | Speedup |
| --- | ---: | ---: | ---: |
| `edges(data="w")` | 1.981225 s | 1.697662 s | 1.167x |

Profile shift:
- `_native_edges_data_key`: 0.577 s -> 0.467 s over 40 loops.
- `_FailFastEdgeIterator._gen`: 0.191 s -> 0.195 s, effectively unchanged.

## Validation

- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_review_mode_regression_lock.py -k 'edge_view_iteration' -q`
  - `2 passed, 444 deselected`
- `PYTHONPATH=/data/projects/franken_networkx/python .venv/bin/python -m pytest tests/python/test_edges_nbunch_order_parity.py tests/python/test_dicsr_cache_parity.py::test_edges_walk_index_native_orientation -q`
  - `13 passed`
- `cargo fmt --package fnx-python --check`
- `git diff --check`
- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `ubs crates/fnx-python/src/digraph.rs tests/artifacts/perf/20260614T-2a00r-guard-token-boldfalcon/guard_token_edgeview_harness.py`
  - exit 0; no critical findings. UBS reported existing broad-file warnings
    and one artifact-harness `json.loads` warning.

## Score

Impact 2.5 x Confidence 4 / Effort 2 = 5.0. Keep.

Residual follow-up filed as `br-r37-c1-yuxi6`: the next profile-backed primitive
should attack value lookup and tuple/list materialization for `edges(data="w")`.
