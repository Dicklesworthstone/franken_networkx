# Graph Remove P2(c) Integer Endpoint-Mask Proof

Bead: `br-r37-c1-d58s8`

Source lever: `Graph::remove_node` and `Graph::remove_nodes_from` now filter incident edges through integer endpoint arrays instead of rebuilding or probing `EdgeKey(String, String)` sets. Batch removal computes a removed-index mask, an old-to-new remap, filters `edge_index_endpoints`, and rebuilds `adj_indices` from the old integer rows.

## Proof

- Golden SHA: `b17ec5c5f90bdd3b8f574fdc83929ee5a2f23268dcded21be68a80065107dcb2`
- Baseline proof: `baseline_proof.json`
- After proof: `after_proof.json`
- Cases: `half`, `thirds`, and `single_hot` removal on the same seeded weighted graph fixture.
- Observable surface: node order, edge order, edge attrs, degree order, node count, and edge count.
- Ordering/tie-break: survivor node and edge iteration order are included in the proof record.
- FP/RNG: no floating-point algorithm output is involved; graph construction is deterministic.
- Verdict: after proof SHA equals baseline proof SHA and every case matches NetworkX.

## Benchmarks

Direct Python timing, mean removal time:

| Scenario | Baseline | After | Speedup |
| --- | ---: | ---: | ---: |
| `remove_nodes_from(half)`, 3000 nodes / 36000 edges | 58.94 ms | 29.80 ms | 1.98x |
| `remove_node(single_hot)`, 3000 nodes / 36000 edges | 2.083 ms | 1.084 ms | 1.92x |

Process-envelope `hyperfine`:

| Scenario | Baseline Mean | After Mean | Speedup |
| --- | ---: | ---: | ---: |
| `loop --mode half --loops 5` | 1.782 s | 1.007 s | 1.77x |
| `loop --mode single_hot --loops 5` | 1.538 s | 1.059 s | 1.45x |

## Validation

- `after_proof.json`: pass, golden SHA unchanged.
- `cargo fmt -p fnx-algorithms -p fnx-classes -p fnx-python --check`: pass.
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: pass.
- `rch exec -- cargo clippy -p fnx-python --all-targets --features pyo3/abi3-py310 -- -D warnings`: pass.
- `cargo test -p fnx-classes remove_nodes_from_matches_repeated_removal_and_rebuilds_indices`: pass. `rch` fell open locally because no worker had admissible slots.
- Focused Python parity: `34 passed`.

## Score

Impact `3` x Confidence `4` / Effort `2` = `6.0`.

Verdict: keep. The lever clears the Score >= 2.0 gate. Next residual for `br-r37-c1-d58s8` remains DiGraph `add_edges_from` wiring, Multi twins, and union/compose recheck after this P2(c) slice.
