# ego_graph batch empty node copy rejection proof

Bead: `br-r37-c1-04z53.36`

## Profile-backed target

- Source profile: `tests/artifacts/perf/20260603T-post-bfs-capacity-reject-sweep/profile_ego_graph_r2_fnx.txt`.
- Target: `ego_graph(Graph, 0, radius=2)` on BA(3000, 4, seed=42).
- Fresh sweep: fnx `0.026285672295489348s` vs NetworkX `0.02217907609883696s`.
- cProfile: 20 `ego_graph` calls took `0.790s`; result construction still showed
  `Graph.add_edges_from`, `EdgeDataView._materialize`, and node-copy costs.

## Candidate lever

If all nodes copied into the ego graph had empty attrs, batch node insertion
through `graph.add_nodes_from(ordered_nodes)`. If any copied node had non-empty
attrs, leave the old `for node in ordered_nodes: graph.add_node(node,
**dict(G.nodes[node]))` loop unchanged.

## Isomorphism

- Node order: preserved in the candidate because `ordered_nodes` was passed to
  `add_nodes_from` in the same order as the old loop.
- Edge order: unchanged; edge discovery, filtering, materialization, and
  `add_edges_from` were untouched.
- Tie-breaking: unchanged. BFS node discovery and final filtering over
  `G.nodes()` were untouched.
- Floating point: N/A for this unweighted radius-2 case.
- RNG: N/A in the library path; the benchmark graph seed remained fixed at 42.
- Golden output: baseline fnx, NetworkX, and candidate fnx all produced
  `8195242bb15c80fa50c2ad2d1daf43699828f5dadf578d8ac6c22754dddc7849`.

## Verdict

Rejected. The operation sample improved, but two rch hyperfine runs regressed
and did not confirm a real process-level win. The source hunk was manually
removed, and restored ego-graph parity passed.
