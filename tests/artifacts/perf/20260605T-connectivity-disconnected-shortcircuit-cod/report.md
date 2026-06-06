# perf keep: disconnected connectivity short-circuit (br-r37-c1-c1gz0)

## Target

Ready bead `br-r37-c1-c1gz0` reported `node_connectivity` as 562x slower than
NetworkX on disconnected graphs because fnx delegated disconnected global
connectivity calls through `_fnx_to_nx` before returning `0`.

The profile-backed residual was specific to disconnected global calls that hit
delegation surfaces, especially self-loops, `flow_func`, multigraphs, and
`edge_connectivity(..., cutoff=...)`.

## Lever

Mirror NetworkX's global disconnected short-circuit in the Python wrappers after
the existing null-graph and `s`/`t` validation, but before delegation:

- directed graphs: `not is_weakly_connected(G) -> 0`
- undirected graphs: `not is_connected(G) -> 0`

This preserves local `s, t` behavior and keeps the existing delegated paths for
connected/self-loop/multigraph/cutoff cases.

## Proof

Harness: `connectivity_shortcircuit.py`.

The proof corpus checks forced-old, after, and NetworkX outputs for:

- `node_connectivity` on a disconnected self-loop graph
- `node_connectivity(..., flow_func=edmonds_karp)` on a disconnected graph
- `edge_connectivity(..., cutoff=2)` on a disconnected directed graph

Result:

- failures: `0`
- golden SHA256: `88eb452e5c8dc837120478b4af3a028caa71e2e983c46c9ce349c2b91c4c9a5c`
- ordering/tie/floating-point surface: none; scalar integer outputs only
- RNG: fixed seeds in the harness

## Timing

Primary same-worker internal timing, disconnected self-loop graph,
`n=1500`, `edges=1200`, `loops=30`, `repeat=11`:

- forced-old best: `0.0061155965s/call`
- forced-old median: `0.0071456057s/call`
- after best: `0.0000106592s/call`
- after median: `0.0000108532s/call`
- best speedup: `573.7x`
- median speedup: `658.4x`

Hyperfine via `rch exec`, `loops=300`, `runs=7`:

- forced-old mean: `3.128551s`
- forced-old median: `3.042985s`
- after mean: `0.323228s`
- after median: `0.316125s`
- mean command speedup: `9.68x`
- median command speedup: `9.63x`

Decision: keep. Conservative score `Impact 5 x Confidence 5 / Effort 1 = 25`.

## Validation

- `pytest tests/python/test_connectivity_wrappers.py -q`: `27 passed`
- `pytest tests/python/test_connectivity.py tests/python/test_connectivity_empty_graph_parity.py tests/python/test_self_loop_connectivity_eulerian_parity.py tests/python/test_edge_connectivity_value_only_flow_parity.py tests/python/test_lnc_msg_wording_parity.py -q`: `67 passed`
- `cargo fmt --check`: passed
- `rch exec -- cargo check -p fnx-python --all-targets --features pyo3/abi3-py310`: passed
