# Perf win — directed harmonic_centrality(nbunch) reverse-BFS (br-r37-c1-harmdir)

- Agent: `BlackThrush` · 2026-06-20 · worktree at origin/main `08bc5aa52`
- File: `python/franken_networkx/__init__.py` (free)

The undirected harmonic(G, nbunch=[few]) fast path (br-r37-c1-19lrl) was gated
`not G.is_directed()`, so a DiGraph with a small nbunch delegated to nx — a full
fnx->nx O(V+E) conversion for a few reverse BFS, 0.15x nx (14.3ms vs 2.1ms).

For directed graphs harmonic(v) = sum 1/d(u, v) over u REACHING v (distances TO
v). nx computes this via its transpose optimisation (when len(nbunch) < |V| it
swaps nbunch/sources and reverses G), accumulating in reverse-BFS-from-v order.
fnx's `single_target_shortest_path_length` emits distance-to-v in that same order,
so the running float sum is BYTE-IDENTICAL. Added the directed branch, gated on
the transpose condition len(nbunch) < |V| (nbunch==|V| keeps the delegated path,
which nx does not transpose).

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20, n=1500/7000e)

| harmonic_centrality(DiGraph, nbunch=[0,1,2]) | before | after |
| --- | ---: | ---: |
| | 0.15x | **1.33x** (14.3ms -> 1.57ms) |

## Parity

600 random DiGraphs, nbunch sizes 1..|V| (incl nbunch==all -> delegated): 0
mismatches, BYTE-EXACT float values (492/492 isolated reverse-BFS check too).
pytest -k harmonic: 277 passed.
