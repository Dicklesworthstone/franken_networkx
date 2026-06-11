# perf: min_cost_flow / network_simplex / capacity_scaling — network-simplex solver

Bead: br-r37-c1-mcfns (filed). fnx's min_cost_flow used a successive-shortest-paths
Bellman-Ford solver that relaxed over O(n^2) (u, succ) pairs calling G.successors /
G.get_edge_data INSIDE the hot loop. With REAL demands it was catastrophically slow:
50.8x slower than nx at n=300 (586ms vs 11ms), 96x at n=600 (3565ms vs 37ms). The
zero-demand default benchmark (2x) completely hid this — the solver only runs when
there is flow to route. network_simplex and capacity_scaling both route through it.

## Lever (ONE)
Replace the SSP solver with the network-simplex algorithm run IN-PROCESS on the fnx
graph (no fnx->nx conversion): it extracts the graph to flat arrays once then pivots
on arrays. The flow conformance contract is COST-ONLY (test_flow_conformance_matrix
asserts equal cost / balanced total flow, NOT an exact flow dict — fnx's SSP already
produced different valid optima than nx on some inputs), and the simplex is cost-exact
by construction. fnx's existing pre-validation (empty graph, negative capacity, inf /
non-zero total demand) is preserved for error-contract stability; SSP kept as fallback.

## Proof (cost-exact)
- Golden over a 5-graph demand corpus asserts, for each: min_cost_flow_cost == nx,
  total flow balance == nx, fnx flow is a VALID optimum (cost_of_flow == optimal), and
  network_simplex cost == nx. SHA e335234edfb42ea82f6168ea8817a990d31e09d25d79376a427ee1fb62abe051
- 1072 flow / min_cost / network_simplex / capacity_scaling / error_message tests pass.

## Benchmark (gnp directed, real source/sink demands, min-of-3)
| n   | nx (ms) | fnx before (ms) | fnx after (ms) | before vs nx | after vs nx |
|-----|---------|-----------------|----------------|--------------|-------------|
| 300 | 11.2    | 586             | 22.9           | 50.8x slower | 2.05x slower|
| 600 | 42.5    | 3565            | 67.4           | 96x slower   | 1.58x slower|

~25-60x self-speedup; 50-96x-slower -> 1.6-2x slower, cost-exact. Pure-Python.
NEXT (follow-up): native safe-Rust network-simplex kernel to beat nx (the residual
~2x is the array-extraction + fnx pre-validation graph reads).
