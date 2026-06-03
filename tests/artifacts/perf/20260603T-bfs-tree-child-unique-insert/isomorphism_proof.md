# bfs_tree child-unique insertion isomorphism proof

Status: kept candidate.

Invariant:
- `fnx_algorithms::bfs_edges*` emits BFS tree edges. A node is discovered once,
  and the first-discovery parent is emitted once. Therefore each child `v` in
  the returned edge stream is unique.

Observable behavior:
- BFS traversal is unchanged. Neighbor iteration, visited marking, reverse
  directed traversal, and `depth_limit` behavior stay in the existing
  `fnx_algorithms::bfs_edges*` calls.
- Source handling is unchanged. The source node is inserted before edge
  materialization; source-only/empty-tree behavior is unchanged.
- Node order is unchanged. The source is inserted first, then children are
  inserted in BFS tree edge order, as before.
- Edge order is unchanged. The same `edges` vector is passed to
  `extend_edges_unrecorded`.
- Edge orientation is unchanged. Each `(u, v)` pair is untouched.
- Node and edge attr behavior is unchanged. Returned tree nodes and edges still
  receive fresh empty Python attr dicts.
- Tie-breaking is unchanged. The first-discovery parent selection remains in
  the traversal layer.
- Floating-point behavior is N/A. `bfs_tree` performs no floating-point
  arithmetic.
- RNG behavior is unchanged. The library path is RNG-free; benchmark seed is
  fixed at `42`.

Golden-output proof:
- Baseline FNX repeat-50 SHA:
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Baseline NetworkX repeat-50 SHA:
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.
- Candidate FNX repeat-50 SHA:
  `5a16c0c6b529b4abf6a1e8e95a7b383d81f8b9f586357b010ec92697613cdc64`.

Focused parity:
- `tests/python/test_traversal.py`
- `tests/python/test_sort_neighbors_parity.py`
- `tests/python/test_traversal_coding_minors_conformance.py`
- `tests/python/test_attribute_access_parity.py`
- Selector: `-k 'bfs_tree or bfs_edges'`
- Result: `22 passed, 256 deselected`.
