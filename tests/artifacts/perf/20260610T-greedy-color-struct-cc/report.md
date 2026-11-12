# perf(greedy_color non-largest_first): structural conversion

br-r37-c1-pwdwy

## Problem
`greedy_color` with any strategy other than the (native) `largest_first` —
`smallest_last`, `connected_sequential_bfs/dfs`, `saturation_largest_first`,
`DSATUR`, `independent_set` — delegated via `_call_networkx_for_parity`, which
round-trips the graph through the FAITHFUL `_networkx_graph_for_parity`
conversion (copies every node/edge attr dict). Split at n=400: conversion 5.29 ms
+ nx algo 5.48 ms = ~11 ms. **~1.92–1.98× slower than nx** (flat across sizes).

## Lever (one)
Coloring is **structure-only** (no node/edge attrs or weights affect it), so run
nx's strategy on a cheap **structural** `nx.Graph` (G's nodes in order + edges)
instead of the faithful conversion. These strategies pop nodes from degree
buckets in CPython `set` order, so byte-identity requires preserving the node +
adjacency iteration order — which the structural graph does (verified
`struct==faithful` for every str strategy). Multigraph / directed / callable
strategy / `interchange=True` keep the faithful path. Python-only.

Touched: `python/franken_networkx/__init__.py` (`greedy_color`).

## Proof (nx-exact)
`harness_proof.py`: 114 cases — 7 strategies × 8 seeds × 2 sizes, plus
string-labelled and an `interchange=True` (faithful-path) case. Full
`{node: color}` dict **== nx, 0 mismatches**.
Golden sha256 (== nx):
`c78ec3839070dfbd0d7c0b48cf4ff781e7f69ecfee6078acb4fd4af3dff9caa2`
pytest -k "greedy/coloring/color": **1056 passed**.

## Timing (warm interleaved min-of-6, backend disabled, gnp, smallest_last)
| n    | baseline fnx | nx | base ratio | new fnx | new ratio | self-speedup |
|------|-------------:|---:|-----------:|--------:|----------:|-------------:|
| 400  | 11.31 ms | 5.63 ms | 1.98× | 7.62 ms | 1.35× | 1.48× |
| 800  | 28.30 ms | 14.78 ms | 1.92× | 19.57 ms | 1.32× | 1.45× |
| 1500 | 50.82 ms | 26.66 ms | 1.94× | 35.89 ms | 1.35× | 1.42× |

1.92–1.98× slower → 1.32–1.35× (1.42–1.48× self-speedup), cascading to all six
delegated strategies. Residual is nx's strategy running on the converted graph
(O(V+E) algo, same cost as nx) + the cheap structural build.

## Score
Impact: moderate (1.42–1.48× self-speedup across 6 coloring strategies).
Confidence: high (byte-identical golden sha, 0/114 incl. all strategies +
string + interchange, 1056 tests). Effort: very low (swap conversion,
Python-only). Score >= 2.0 by low-effort/high-confidence; explicitly NOT full
parity (the O(V+E) coloring on a converted graph remains).
