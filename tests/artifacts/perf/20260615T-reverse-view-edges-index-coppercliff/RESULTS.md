# Reverse View Edge Batch Index-Row Lever

Bead: `br-r37-c1-04z53.9114`

Workload: `list(DG.reverse(copy=False).edges())` on
`DiGraph(watts_strogatz_graph(n=1200, k=8, p=0.2, seed=3))`, 300 loops.

## Lever

For exact reverse views with no predecessor display-key overrides, `_native_reverse_edges_no_data`
now walks predecessor index rows directly and builds a per-call node-object vector. The old
string-row path remains the fallback when `pred_py_keys` is non-empty, preserving mixed-key
display override behavior.

This is one lever: remove per-edge predecessor string row lookup and per-edge `py_node_key`
hash lookup from the dominant reverse-edge batch path.

## Benchmark

Hyperfine via `rch exec`:

| Engine | Baseline mean | After mean | Delta |
| --- | ---: | ---: | ---: |
| FrankenNetworkX | 772.4 ms | 529.0 ms | 1.46x faster |
| NetworkX | 537.9 ms | 497.9 ms | comparison drift only |

Gap to NetworkX: 1.44x slower before, 1.06x slower after.

Direct harness check:

| Engine | Baseline seconds/loop | After seconds/loop | Digest |
| --- | ---: | ---: | --- |
| FrankenNetworkX | 0.0010455483 | 0.0008561174 | `7a4d30e303c9e728d34e02b64022e1c445e60ce8d45ba3ea8639d00ea05e3b8c` |
| NetworkX | 0.0006999469 | 0.0006821543 | `7a4d30e303c9e728d34e02b64022e1c445e60ce8d45ba3ea8639d00ea05e3b8c` |

Profile:

| Frame | Baseline | After | Delta |
| --- | ---: | ---: | ---: |
| `_native_reverse_edges_no_data` | 0.185 s / 300 loops | 0.121 s / 300 loops | 1.53x faster |
| full target | 0.268 s / 300 loops | 0.223 s / 300 loops | 1.20x faster |

Score: Impact 3 x Confidence 5 / Effort 2 = 7.5.

## Isomorphism And Golden Proof

Golden bundle SHA stayed unchanged:

`2e13b616a395c926d715ab7843bd713b1626a5cba9957d1348916f059c5105f3`

The proof bundle verifies:

- reverse edge order
- `data=True`
- `data=<attr>, default=<value>`
- live reverse-view mutation visibility
- frozen reverse-view mutation errors
- node and edge counts after source graph mutation

There is no floating-point or RNG surface in this lever. Tie-breaking and ordering are determined
by the same node-major predecessor insertion rows as NetworkX-observable behavior.

A current-head rerun on `9c0ebd8fd` is recorded in `current_head_golden_reverse_edges.json`;
it preserves the same bundle SHA and all case-level hashes.

## Validation

- `rch exec -- cargo check -p fnx-python --lib --features pyo3/abi3-py310`
- `rch exec -- cargo clippy -p fnx-python --lib --features pyo3/abi3-py310 -- -D warnings`
- `cargo fmt --package fnx-python --check`
- `python -m pytest tests/python/test_view_pickle_parity.py -k 'reverse_view' -q`
  - `29 passed, 234 deselected`
- `ubs crates/fnx-python/src/digraph.rs`
  - exit 0; existing broad warning inventory remains outside this lever
