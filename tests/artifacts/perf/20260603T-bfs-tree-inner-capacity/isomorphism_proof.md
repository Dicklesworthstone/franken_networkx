# bfs_tree inner DiGraph capacity rejection proof

Bead: `br-r37-c1-04z53.35`

## Profile-backed target

- Source profile: `tests/artifacts/perf/20260603T-post-sparse-edge-once-traversal-sweep/profile_bfs_tree_fnx.txt`.
- Target: `bfs_tree(Graph, 0)` on BA(3000, 4, seed=42).
- Profile line: 20 timed calls spent `0.139s` inside native `_fnx.bfs_tree`.
- Sweep gap: fnx `0.006744459495530463s` vs NetworkX `0.004209162501501851s`.

## Candidate lever

Add a `DiGraph::with_runtime_policy_and_capacity` constructor, expose it through
the `PyDiGraph` empty-result constructor, and use `edges.len() + 1` node capacity
plus `edges.len()` edge capacity when building the `bfs_tree` result graph.

No traversal algorithm, neighbor iteration, node key conversion, edge insertion
order, or Python wrapper fallback was changed.

## Isomorphism

- Ordering: preserved. The BFS edge vector was still produced by the existing
  `fnx_algorithms::bfs_edges*` implementations, and the result tree still
  inserted source first followed by BFS edges in the same order.
- Tie-breaking: preserved. Neighbor iteration order and directed/reverse
  dispatch were unchanged.
- Floating point: N/A. `bfs_tree` uses no floating-point arithmetic.
- RNG: N/A in the library path. The benchmark graph seed remained fixed at 42.
- Golden output: baseline fnx, NetworkX, and candidate fnx all produced
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.

## Verdict

Rejected. The direct rch sample improved slightly, but hyperfine did not prove a
real process-level win and the opportunity score was below the `Score >= 2.0`
gate. The source changes were manually removed and the release extension was
rebuilt from restored source.
