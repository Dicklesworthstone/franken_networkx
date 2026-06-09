# perf(find_cycle): native edge_dfs+find_cycle DFS (common case)

br-r37-c1-7yn51

## Problem
`find_cycle(G)` was a verbatim Python port of nx's edge_dfs+find_cycle running on
fnx views — each node's incident edges came through a per-node `G.edges(node)`
fnx EdgeView crossing. ~3-4x slower than nx on cycle-dominated graphs (must
traverse much of the graph before the back-edge closes a cycle).

## Lever (one)
Port the fused edge_dfs + find_cycle state machine to native Rust
(`find_cycle_simple_dfs`) for the common case (orientation=None, source=None,
simple graph), querying integer adjacency ON DEMAND via neighbors_indices /
successors_indices — so an early-exit cycle costs only the rows visited, NOT an
O(V+E) whole-graph build. Faithful line-by-line translation: same traversal
order, edge-id dedup (frozenset undirected / ordered pair directed), active-path
trim, and final rotation to begin at final_node. Multigraph / explicit source /
non-None orientation keep the Python port.

Touched: crates/fnx-python/src/algorithms.rs (kernel + binding + register),
python/franken_networkx/__init__.py (wrapper fast path + import).

## Proof (nx-exact)
209 cases: cycle/path/complete/directed-cycle/DAG/empty/self-loop(both
dir)/multi-component/isolated + random directed&undirected gnp n=1..30.
0 mismatches vs nx (cycle edges + orientation + NetworkXNoCycle). pytest -k
"find_cycle or cycle or edge_dfs": 935 passed.

## Timing (warm min-of-9)
| scenario              | before ratio | after ratio |
|-----------------------|-------------:|------------:|
| cycle_graph n=1000    |    3.95x     |  0.12x (8x faster) |
| cycle_graph n=4000    |    3.00x     |  0.10x (10x faster)|
| dense gnp n=1000 (early-exit) | ~1x  |  0.12x (faster, no regression) |
| dense gnp n=4000 (early-exit) | ~1x  |  0.22x (faster) |

First lazy-adjacency draft regressed early-exit 200x (O(V+E) prebuild); on-demand
neighbors_indices fixed it — now faster than nx in BOTH regimes.

## Score
Impact: high (3-4x slower -> 8-10x faster on cycle-dominated, faster everywhere).
Confidence: high (0/209 vs nx, 935 tests). Effort: moderate (faithful port).
Score >> 2.0.
