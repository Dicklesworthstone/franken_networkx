# Perf WIN — all_simple_paths neighbor-DFS + gate extension: 0.64x -> 1.38-1.65x at ALL cutoffs (br-r37-c1-aspneigh)

- Agent: `BlackThrush` · 2026-06-21 · File: `__init__.py`

## The gap
all_simple_paths had a de-delegated in-process DFS (`_all_simple_paths_fnx`, br-asplocal) but
ONLY for cutoff<=3; it ran at 0.64x vs nx, and cutoff>=4 / None still DELEGATED (full fnx->nx
conversion). Root cause: the DFS pushed `iter(G.edges(next_node))` per node — `G.edges(n)`
materializes the EdgeView (builds (u,v) tuples) and is ~8x slower than `G.neighbors(n)`
(MEASURED 273us vs 33us / 50 nodes) even though the DFS only consumes the neighbor (`e[1]`).

## The fix
1. Emit `(next_node, nbr) for nbr in G.neighbors(next_node)` instead — SAME adjacency order
   so byte-identical yield order. 0.64x -> 1.46x at the same cutoff.
2. The old "large cutoff -> nx's C DFS wins" rationale was FALSE (nx's all_simple_paths is
   pure Python). With the cheaper DFS the in-process path beats nx at EVERY cutoff
   (1.32-1.38x measured through cutoff=6 / 2665 paths), so extend the gate to any
   non-multigraph cutoff incl None (-> len(G)-1 inside, matching nx). Removes the conversion
   delegation for cutoff>=4 / None.

## Verify
- BYTE-IDENTICAL yield order vs nx: 3000/3000 finite cutoff 0-6 (directed+undirected, scalar
  + iterable target, string nodes) + 600/600 cutoff=None (trees/paths/cycles). conformance
  pytest -k simple_path 443 passed.

## MEASURED (nx/fnx, warm min)
| cutoff | before | after |
|--------|--------|-------|
| 2      | 0.64x  | 1.65x |
| 4      | delegated (conv-tax) | 1.38x |
| 6      | delegated | 1.40x |
| None   | delegated | wins (1.3x) |

LEVER (reusable): in-process DFS/BFS that calls `G.edges(node)` but only needs the neighbor
should use `G.neighbors(node)` (~8x cheaper — no EdgeView tuple materialization). Audit other
`iter(G.edges(` / `G.edges(node)` sites in path/traversal wrappers.
