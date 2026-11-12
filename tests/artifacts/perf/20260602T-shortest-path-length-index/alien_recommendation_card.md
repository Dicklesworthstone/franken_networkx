# Alien Recommendation Card: br-r37-c1-hbv0y

## Target

`shortest_path_length(G, 0, n-1)` on BA(3000, 4, seed=42), unweighted public Python API.

Baseline:
- fnx mean: `0.0003396593499928713` s
- NetworkX mean: `0.000023062153777573256` s
- fnx/nx ratio: `14.727997795382509`
- cProfile repeat-200: native `_fnx.shortest_path_length` consumes `0.071` s of `0.072` s in the call path.

## Primitive

Alien graveyard §7.1 Succinct Data Structures and §7.2 Cache-Oblivious Data Structures.

Applied subset: dense node-index distance state and adjacency-index traversal. A shortest-path-length query does not need string-keyed `HashMap<&str, usize>` state because it returns only a scalar distance.

## EV Score

Impact 5 x Confidence 5 / Effort 1 = `25.0`.

## One Lever

Replace `HashMap<&str, usize>` BFS distance tracking with:
- `Graph::get_node_index` for source/target;
- `Vec<usize>` distance state with `usize::MAX` as the unvisited sentinel;
- `VecDeque<usize>` frontier;
- `Graph::neighbors_indices` adjacency scans.

## Fallback

Fallback is `git revert` of the code commit. The PyO3 wrapper still validates source and target before the kernel and maps `None` length to the same `NetworkXNoPath` exception.

## Result

After:
- fnx mean: `0.00001346970646409318` s
- Speedup: `25.216536893236462x`
- fnx/nx ratio: `0.5840610809382325`
- Repeat-1000 hyperfine: `0.70563424858` s -> `0.34953590724` s (`2.0187747065868513x`)
- Golden sha256 unchanged: `3d95e61519c778f79f1a76ab3f900fb9c8e7a3fb2991e89213fba2475aec3547`
