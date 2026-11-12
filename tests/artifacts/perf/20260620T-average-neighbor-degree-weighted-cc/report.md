# average_neighbor_degree (weighted) — vectorized sparse mat-vec

Bead: br-r37-c1-wqhqr (assortativity family)
Agent: cc (CopperCliff)
Date: 2026-06-20

## Problem

The unweighted undirected case has a native kernel, but the **weighted** path
fell through to a fallback walking `G.adj[n].items()` / `G.succ`/`G.pred`
AtlasViews per node and using the slow `source_degree(weight=...)` view as the
divisor. Measured (n=1500 gnp): undirected weighted 0.514x, directed weighted
in/out 0.470x, out/in 0.571x vs nx.

## Fix (vectorize the weighted neighbour sum)

`k_{nn,i}^w = (1/s_i) Σ_j w_ij k_j` is a sparse mat-vec. Build the weighted
adjacency once (`to_scipy_sparse_array`); numerator = `A @ k` (successor side)
and/or `Aᵀ @ k` (predecessor side); the weighted source degree `s_i` is the
matching row/col sum. `k` is the **unweighted** target degree (already
precomputed as `target_degrees`). Undirected self-loops sit once on the diagonal
but count twice in the weighted degree → add the diagonal back. Gated on
`weight is not None`, `nodes is None`, `type(G) in (Graph, DiGraph)`,
`number_of_edges() > 0` (empty graphs keep the fallback). Validation for
source/target already ran upstream.

## Proof

- `bench_and_parity.py`: **2000 value-parity checks, 0 fails** — all
  source×target×weight combos, self-loops, missing weights, empty/degenerate,
  directed + undirected. Golden sha256
  `3894077d8fddf691343580fc08461f188cf573e6b87f8749a15668a3658e72aa`.
- Conformance: 98 passed in the `neighbor_degree` family.

## Timing (interleaved min-of-9; run.log in this dir)

| case            | before | after  | nx     | after vs nx |
|-----------------|--------|--------|--------|-------------|
| undir weighted  | 0.514x | 5.6 ms | 6.3 ms | **1.12x**   |
| dir wt in+out   | ~0.96x | 10.5ms | 13.7ms | **1.31x**   |
| dir wt in/out   | 0.470x | 9.2 ms | 9.4 ms | **1.02x**   |
| dir wt out/in   | 0.571x | 9.1 ms | 7.0 ms | 0.77x       |

Strict improvement on every variant; undirected, in+out and in/out now at-or-
above nx. The residual `dir out/in` (0.77x, up from 0.57x) is **substrate-bound**:
fnx's weighted `to_scipy_sparse_array` construction ≈ nx's entire runtime for
this single-orientation case (same root as br-r37-c1-wvuf7). A native
weighted-degree-pair kernel would close it. Pure-Python change.
