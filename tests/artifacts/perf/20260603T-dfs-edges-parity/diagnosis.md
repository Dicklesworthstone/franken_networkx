# dfs_edges digest mismatch diagnosis

Bead: `br-r37-c1-v389d`

## Summary

The `dfs_edges` digest mismatch was caused by the traversal benchmark's oracle graph construction, not by FNX DFS semantics.

The old benchmark generated a NetworkX Barabasi-Albert graph and compared:

- FNX graph built by replaying `base.nodes()` and `base.edges()`.
- The original NetworkX generator graph.

For undirected graphs, `base.edges()` cannot preserve both endpoints' adjacency insertion order. NetworkX DFS observes adjacency order, so the original generator graph can have a different neighbor order than any graph reconstructed from its edge list.

## Concrete first difference

`repro_current.txt` shows:

- FNX raw DFS SHA: `25251999456aa12430e8a229f57f204d5426d13543b16d4c0c0193af6f235473`
- FNX Python fallback DFS SHA: `25251999456aa12430e8a229f57f204d5426d13543b16d4c0c0193af6f235473`
- Original NetworkX DFS SHA: `b248892fc0f3af47792cbaa179c8900ad061859dac411f8631d9756249fface7`
- First edge difference at index `8`: FNX `(63, 38)`, original NetworkX `(63, 57)`.

Node `63` exposes the construction-order problem:

- Original NetworkX neighbors: `[57, 4, 38, 9, 231, ...]`
- FNX neighbors after edge-list replay: `[4, 9, 38, 57, 231, ...]`

FNX raw DFS and the FNX Python DFS fallback are identical, so the Rust DFS stack semantics are not the cause.

## Replay oracle proof

`replay_oracle_probe.txt` builds a fresh NetworkX graph from the same node and edge insertion stream used to build FNX.

Results:

- FNX SHA: `25251999456aa12430e8a229f57f204d5426d13543b16d4c0c0193af6f235473`
- Replayed NetworkX SHA: `25251999456aa12430e8a229f57f204d5426d13543b16d4c0c0193af6f235473`
- FNX equals replayed NetworkX: `True`
- First FNX/replayed difference: `None`

## Benchmark fix

`tests/artifacts/perf/20260602T-traversal-residual-sweep/bench_traversal.py` now creates the NetworkX oracle by replaying the generated graph's nodes and edges before building the FNX graph. This makes the two benchmark inputs observe the same adjacency insertion order.

Patched `dfs_edges` repeat-50 results:

- FNX SHA: `60cfd824e2ecc2670fc5847aa328b05199a27e3541a7a15b01ce97e0d1e9c5ac`
- NetworkX SHA: `60cfd824e2ecc2670fc5847aa328b05199a27e3541a7a15b01ce97e0d1e9c5ac`
- FNX mean: `0.0007394904823740944s`
- NetworkX mean: `0.0018356602179119364s`

Patched sweep repeat-5 also reports matching `dfs_edges` SHA for FNX and NetworkX: `0a875a840418aba6b8cb5c69e202d22e00773a6b1977035a4dc86b1869198397`.

## Correctness conclusion

The blocker is resolved by fixing the benchmark oracle. Further `dfs_edges` performance work is no longer blocked by this digest mismatch. Behavior parity remains tied to same-construction insertion order, and the existing focused traversal parity tests continue to cover DFS API semantics.

