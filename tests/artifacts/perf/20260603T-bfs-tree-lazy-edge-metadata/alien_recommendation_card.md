# Alien Recommendation Card: bfs_tree lazy edge metadata

Bead: `br-r37-c1-bdd87`

Profile-backed target:
- `bfs_tree` on `barabasi_albert_graph(8000, 4, seed=42)`.
- Baseline FNX mean: `0.07658544930018252s`.
- Baseline NetworkX mean: `0.018295269904774612s`.
- Baseline cProfile: native `_fnx.bfs_tree` consumed `1.185s` across 20 calls.
- Matching golden SHA: `40dd5c5bbd4df6a848c51d3980210cf060943460e9809e5a6d9a6bd9231916f2`.

Primitive harvested:
- Alien graveyard §7 data-structure locality and §8.2 selection/materialization discipline.
- Replace eager Python edge-attribute dictionary materialization with native edge-set storage plus deferred dictionary creation at observation/mutation boundaries.

One lever attempted:
- `bfs_tree` returned a `DiGraph` whose native edge set was populated immediately, while Python `edge_py_attrs` was populated lazily by directed edge-data accessors.

Decision:
- Rejected. Behavior proof passed, but the perf gate failed.
- The next BFS-tree attack should not tune edge metadata. It needs a different graph-object representation or a different profiler-backed hotspot. The currently live profile-backed quotient-node metrics bead is a better next target if its reservations are clear.
