# greedy_tsp tie-path fix — CopperCliff 2026-06-28

## Problem
`approximation.greedy_tsp` native kernel returns None on ANY weight TIE (common
for integer-weighted complete graphs). The bail fell back to
`_networkx_graph_for_parity(G)` (O(n^2) build) + nx's O(n^2) loop => 0.05-0.9x vs nx,
regression growing with n (n=250 -> 0.31x).

## Fix
1. Python in-process fallback: run nx's EXACT greedy walk over one
   `dict(G.adjacency())` snapshot; tie-break via real CPython set order => byte-exact.
2. Native kernel rewritten to a LAZY walk that bails O(n) at the first tie
   (was O(n^2) matrix-build + completeness-scan before the walk).

## Measured (complete graph, min-of-25, gc off)
INT weights (tie path -> in-process):
  n=100 1.42x  n=200 1.42x  n=250 1.37x  n=300 1.35x  n=400 1.32x   (was 0.05-0.9x)
FLOAT weights (no-tie -> native fast path):
  n=100 3.90x  n=200 3.56x  n=250 1.72x  n=300 2.49x  n=400 1.84x   (maintained/improved)

## Correctness
- 0/3360 adversarial mismatches vs nx (n=1..40, dir+und, int+float, heavy-tie ranges, varied source)
- error contracts match: incomplete->NetworkXError, empty->StopIteration, bad-source->KeyError, weight=None, dir-incomplete
- conformance: 118 tsp/approx-parity pass; 4593 passed/0 failed across approximation/connectivity/clique/dominating
