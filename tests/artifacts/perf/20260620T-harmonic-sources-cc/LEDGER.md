# Perf win — harmonic_centrality(sources=[few]) (br-r37-c1-harmsrc)

- Agent: `BlackThrush` · 2026-06-20 · File: `python/franken_networkx/__init__.py`

The nbunch fast paths require `sources is None`, so harmonic(G, sources=[few])
(default nbunch=all) delegated to nx: 0.14-0.15x (BOTH Graph and DiGraph). This is
the NON-transposed direction — centrality[u] = sum over v in sources of 1/d(v, u)
— so one FORWARD BFS per source accumulates 1/d into every reachable u (sources
are the BFS roots; works for directed and undirected). fnx's
single_source_shortest_path_length emits nx's accumulation order -> byte-identical.

## Win vs NetworkX 3.6.1 (clean worktree, warm min-of-20, n=1500/7000e, sources=3)

| harmonic_centrality(sources=[0,1,2]) | before | after |
| --- | ---: | ---: |
| Graph | 0.15x | **2.32x** |
| DiGraph | 0.14x | **1.75x** |

## Parity

800 random Graph+DiGraph, sources sizes 1..4: 0 mismatches, byte-exact float.
pytest -k harmonic: 277 passed.
