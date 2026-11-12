# bfs_tree raw construction indexed-builder candidate

Bead: `br-r37-c1-kzo1b`

Target: raw `franken_networkx.bfs_tree(Graph, 0)` construction on `barabasi_albert_graph(3000, 4, seed=42)`.

Baseline:

- FNX direct mean over 50 calls: `0.025621020282269456s`
- NetworkX direct mean over 50 calls: `0.005458620581193827s`
- Baseline hyperfine process envelope: `1.567242370322857s +/- 0.03574761168135869s`
- Baseline cProfile: `_fnx.bfs_tree` consumed `0.966s` over 50 calls.

Candidate lever:

- Add an index-returning BFS tree primitive for exact undirected `Graph`.
- Add a directed-tree bulk inserter for index-addressed source graph labels.
- Route exact undirected `Graph` `bfs_tree` through that builder to avoid the intermediate `Vec<(String, String)>` result stream.

Result:

- FNX direct mean: `0.025621020282269456s -> 0.024712777779204772s` (`1.036751939064857x`)
- Hyperfine: `1.567242370322857s -> 1.5726723092342858s` (`0.9965473170224047x`, regression/noise)
- After cProfile: `_fnx.bfs_tree` remained `0.990s` over 50 calls.
- Restored FNX mean after removing source: `0.025680061717284843s`

Decision:

- Impact: 0
- Confidence: 4
- Effort: 2
- Score: `0.0`
- Verdict: rejected; source changes were removed.

Next primitive:

- Do not repeat index-stream or bulk-insert micro-levers for this path.
- The next attack should change the representation boundary: either construct a tree object with arena-backed/lazy edge metadata while preserving `DiEdgeView` iteration and mutation semantics, or move to a different profiler-backed hotspot not dominated by PyO3 graph-object materialization.
