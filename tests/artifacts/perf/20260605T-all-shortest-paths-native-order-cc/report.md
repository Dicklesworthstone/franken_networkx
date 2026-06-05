# perf: all_shortest_paths (unweighted, undirected) native — nx-order kernel, drop fnx->nx delegation

Bead br-r37-c1-qiplw. Measured 17.4x slower than nx at n=2000 (single pair).

## Lever
The unweighted case (weight=None) delegated to networkx via a full fnx->nx graph
conversion per call (`_call_networkx_for_parity`) because the native
`all_shortest_paths` kernel ran `paths.sort()` for "canonical ordering", which
does NOT match nx's iteration order (nx yields paths via a DFS over the BFS
predecessor DAG — `_build_paths_from_predecessors`).

Fix the kernel instead of delegating: the kernel's BFS already builds predecessor
lists in nx's BFS-discovery order, so replace the `paths.sort()` tail with nx's
exact stack walk (a DFS from `target` back to `source` over `preds`, with a
`seen` set guarding the active path). Then drop the unweighted delegation in the
Python wrapper so it routes to the native kernel (`_raw_all_shortest_paths`,
method='unweighted'). The binding raises NetworkXNoPath with a different message
for an unreachable-but-present target, so the wrapper re-raises with nx's exact
wording.

Scope: UNDIRECTED unweighted only. The directed kernel
(`all_shortest_paths_directed`) has a separate predecessor-order divergence vs nx
(its pred[t] follows in-edge insertion order, not BFS-discovery order) — directed
unweighted keeps delegating, tracked in a follow-up bead.

## Correctness (differential vs nx, including exact iteration order)
`parity_proof.py`: 120 random graphs (directed + undirected gnp) + the karate
graph (the cited regression source), all node pairs in [0,6): 3651 path-cases +
705 no-path/error cases — 0 mismatches on full path-list order AND error
class+message. Undirected-only sweep (karate + 60 gnp): 0/2072. 515 shortest-path
pytest pass. golden_sha256
263581cb6c040af95ac009ae2c561fc0207b0d4cc627d8cd6038d7cee4b3885b.

In-crate fnx-algorithms kernel tests (diamond/single/no-path, directed variants)
pass — they assert set-membership/single-path so the order change is safe.

## Perf (warm min-of-12, single pair, connected_watts_strogatz)
- n=1000: OLD 12.11x -> NEW 0.07x  (self 8.725ms -> 0.051ms = 171x; 14x FASTER than nx)
- n=2000: OLD 13.46x -> NEW 0.25x  (self 19.345ms -> 0.356ms = 54x; 4x faster)
- n=5000: OLD 11.95x -> NEW 0.17x  (self 55.708ms -> 0.666ms = 84x; 5.9x faster)

The full fnx->nx per-call conversion is eliminated; the kernel BFS+enumeration is
pure Rust. Pattern: fix the diverging native kernel + drop delegation.
