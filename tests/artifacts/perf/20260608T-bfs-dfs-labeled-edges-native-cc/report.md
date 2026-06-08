# bfs_labeled_edges / dfs_labeled_edges: native in-process, drop fnx->nx delegation (br-r37-c1-bfslabnative)

## Problem
Both labeled-traversal generators delegated to nx (full fnx->nx conversion per
call) then ran nx's BFS/DFS.

## Lever (ONE)
Port nx's exact generators in-process over fnx's native adjacency. BFS iterates
`G[u]` (== nx's `G._adj[u]` order); DFS uses `G.neighbors(n)` as a STATEFUL
iterator resumed via the stack (fnx returns a dict_keyiterator, matching nx).
fnx's adjacency order already matches nx, so the yielded (u, v, label) triple
SEQUENCE is byte-identical. dfs_labeled_edges with a user `sort_neighbors`
callable keeps delegating.

## Proof (correctness — no timing; host load avg ~14 this window)
- 1600 calls (Graph/DiGraph/MultiGraph/MultiDiGraph x single-source/list-sources/
  source=None x depth_limit None/3/1/2): 0 mismatches on the full triple list.
- Edge cases (empty/single-node/self-loop/empty-source-None) match nx incl error
  type+message.
- Golden fnx == nx.
- `pytest -k "labeled_edges or bfs or dfs"`: 710 passed.

Structural delegation-elimination (load-independent); removes the per-call
fnx->nx conversion for both traversal generators.
