# global_reaching_centrality — unweighted distance fast path (br-r37-c1-04z53)

## Problem
`global_reaching_centrality(G)` (weight=None) was the top residual vs-nx perf gap:
1.90x SLOWER than NetworkX (182ms vs 95ms @ N=400, m=3 Barabasi-Albert).

Root cause: the wrapper computed `dict(shortest_path(G))` — all-pairs full
shortest-path NODE LISTS — then per node summed `1/(len(path)-1)`. For the
unweighted case `_average_path_weight` only consumes `len(path)-1` = the BFS
distance, so the O(N^2 * path_len) path reconstruction (Rust kernel clones a
`Vec<String>` per discovered node) was pure waste. The native Rust
`global_reaching_centrality` kernel exists but computes the wrong (reachability)
formula for undirected graphs (returns 0.0) and is 1 ULP off for directed — not
bit-exact — so it could not be used.

## Lever (one change, python/franken_networkx/__init__.py)
For `weight is None`, replace path reconstruction with all-pairs BFS *distances*
via `single_source_shortest_path_length` (BFS-discovery order, no node lists):
- undirected: lrc[v] = sum(1/d for reachable d>0) / (n-1)
- directed:   lrc[v] = (reachable_count) / (n-1)
Then GRC = sum(max_lrc - lrc[v]) / (n-1).

## Bit-exactness
`single_source_shortest_path_length` yields distances in the *identical*
BFS-discovery order as `shortest_path`, and the builtin `sum` (Neumaier-
compensated for floats in CPython 3.12+) is reused exactly as the reference does.
A naive accumulator loop drifts 1 ULP vs `sum()` — that subtlety is why the
generator+`sum()` form is mandatory. Verified bit-identical (==) to NetworkX on
464 cases: 280 undirected BA + 120 directed GNP + 15 weighted (unchanged path) +
disconnected/multigraph/path/complete/cycle/tree/karate + error-parity corners.

GOLDEN_SHA256 (over all fnx outputs): see grc_proof.py output
78fbb2e383858cf51eade650c1f1efa976eec5ff53ccacdac4fe20eec71a386c

## Benchmark (p50, Barabasi-Albert, seed=7)
| N    | m | before fnx | after fnx | nx       | after vs nx |
|------|---|-----------|-----------|----------|-------------|
| 200  | 3 |     ~25ms |    6.25ms |  20.90ms |  3.34x faster |
| 400  | 3 |    182ms  |   26.21ms |  99.24ms |  3.79x faster |
| 800  | 4 |       —   |  104.73ms | 410.0ms  |  3.91x faster |
| 1500 | 4 |       —   |  373.15ms | 1497ms   |  4.01x faster |

Self speedup @ N=400: 182ms -> 26ms = 6.95x (Score >= 2.0).
Gap closed: was 1.90x slower than nx, now 3.3-4.0x faster.
