# Perf win — directed closeness_centrality(u) single-node (br-r37-c1-closedir)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`

The single-u closeness fast path was gated `not G.is_directed()`, so a DiGraph
single-u query delegated to nx — which builds the FULL reversed graph (O(V+E))
just to run one BFS: 0.46x. A directed graph's closeness of u uses INCOMING
distances; `single_target_shortest_path_length(G, u)` computes distances TO u
directly (no reversed-graph construction), in nx's finalisation order. Integer
hop sum -> byte-identical.

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20, n=1500/7000e)

| closeness_centrality(DiGraph, u=0) | before | after |
| --- | ---: | ---: |
| | 0.46x | **24.2x** (11.16ms -> 0.46ms) |

## Parity

700 random Graph+DiGraph, single u: 0 mismatches, byte-exact float (600/600
isolated single_target check too). pytest -k closeness: 371 passed.
