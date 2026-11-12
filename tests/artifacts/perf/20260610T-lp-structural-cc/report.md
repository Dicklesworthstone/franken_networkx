# perf(label_propagation_communities): structural conversion

br-r37-c1-6sbtx

## Problem
`fnx.community.label_propagation_communities` delegated to nx by running its
algorithm on `_networkx_graph_for_parity(G)` — a FAITHFUL conversion that copies
every node/edge/graph attribute dict. Profiled at n=800: conversion **17 ms**
(55%) + nx algorithm 13.5 ms = 31 ms. **2.1–2.8× slower than nx.**

## Lever (one)
nx's semi-synchronous label propagation is **unweighted and structure-only** — it
reads node iteration order, `greedy_color(G)`, and a `Counter` of neighbour
labels (the neighbour SET). So a structural `nx.Graph` built from `G`'s nodes (in
G's order) + `G.edges()` (in G's edge order) reproduces the SAME node and
adjacency iteration order — hence identical greedy_color and labeling — at ~half
the conversion cost (no attr copying). Gated to a plain simple `Graph`;
MultiGraph / views keep the faithful path.

Touched: `python/franken_networkx/community.py`. Python-only.

## Proof (nx-exact)
`harness_proof.py`: 42 cases — gnp n∈{40,100,200} × p∈{0.03,0.06,0.12} × 4 seeds,
plus edge cases (self-loop+string+isolated, single edge, empty, path, complete,
**multigraph fallthrough**). Compared against the faithful-conversion baseline
(= nx contract) as an ORDERED list of community sets. **0 mismatches.**
Golden sha256 (== faithful/nx baseline):
`a844bb45c6f849e2fed7d80bd5b8e8e3000634eaa20b5b560d30288839f8ff4c`
pytest -k "label_propagation/community": **114 passed**.

## Timing (warm interleaved min-of-6, backend disabled, gnp)
| n    | baseline fnx | nx       | baseline ratio | new fnx  | new ratio | self-speedup |
|------|-------------:|---------:|---------------:|---------:|----------:|-------------:|
| 800  |   31.04 ms   | 14.03 ms |     2.21×      | 20.93 ms |   1.48×   |    1.48×     |
| 1200 |   44.31 ms   | 21.03 ms |     2.11×      | 31.15 ms |   1.49×   |    1.42×     |
| 1500 |   63.17 ms   | 22.68 ms |     2.79×      | 39.09 ms |   1.72×   |    1.62×     |

1.42–1.62× self-speedup. HONEST RESIDUAL: stays 1.5–1.7× slower — the conversion
(~8 ms) is the cost of running nx's algorithm on a converted graph; reaching
parity needs a true in-process de-delegation that reproduces nx's `greedy_color`
exactly (parity-fragile, deferred).

## Score
Impact: moderate (1.42–1.62× self-speedup on a community-detection primitive).
Confidence: very high (byte-identical golden sha vs nx-contract baseline, 0/42
incl. multigraph/edge cases, 114 tests). Effort: very low (swap conversion,
Python-only). Score >= 2.0 by low-effort/high-confidence; explicitly NOT the full
gap.
