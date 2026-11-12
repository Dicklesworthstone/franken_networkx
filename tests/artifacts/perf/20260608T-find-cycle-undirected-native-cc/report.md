# find_cycle (undirected): route through native _fnx_find_cycle, drop delegation (br-r37-c1-fcyclnative)

## Problem
find_cycle already ran nx's edge_dfs + find_cycle algorithm in-process for the
DIRECTED case (_fnx_find_cycle), but DELEGATED the undirected case to nx (full
fnx->nx conversion) — a stale note from when the RUST binding emitted
algorithm-canonical orientation instead of nx's DFS-traversal direction.

## Lever (ONE)
_fnx_find_cycle is a verbatim port of nx.find_cycle that already handles
undirected (tailhead = edge[:2]) via _fnx_edge_dfs, whose adjacency order matches
nx. So route BOTH directed and undirected through it; drop the undirected
delegation + its per-call conversion (find_cycle early-exits on the first cycle,
so the conversion was often the whole cost).

## Proof (correctness — no timing; host load avg ~13 this window)
- 2404 calls (directed/undirected x simple/multigraph x orientation
  None/original/reverse/ignore x source None/single/list): 0 mismatches on the
  full cycle edge list (orientation included).
- Edge cases (empty/tree/DAG no-cycle -> NetworkXNoCycle, bad source) match nx.
- `pytest -k cycle`: 921 passed.

Structural delegation-elimination (load-independent).
