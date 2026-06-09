# perf(bethe_hessian_matrix): native weighted COO adjacency

br-r37-c1-bethecoo

## Problem
`bethe_hessian_matrix` built A via `to_scipy_sparse_array(G, nodelist=<explicit
list>, format="csr")` with the default str weight and dtype=None. That arg combo
misses fnx's native weighted-COO fast path (which needs a pinned dtype) AND the
default-node-order fast path (explicit nodelist forces the slower reorder path),
so A was built by per-edge `G[u][v]` AtlasView Python reads (~595k __getitem__
on n=1000). 3.4-3.7x slower than nx.

## Lever (one)
Build A with `dtype=float` and, for the default node order, `nodelist=None` —
triggering the native default-order weighted COO builder. The matrix is
byte-identical: default order == G.nodes() order, and the H = (r^2-1)I - rA + D
formula's `r*A` is float regardless of A's dtype. (Degree/regularizer still use
the explicit nodelist.)

Touched: python/franken_networkx/__init__.py (bethe_hessian_matrix, A build).

## Proof (nx-exact)
60 cases (gnp n=15..250, weighted+unweighted, default AND shuffled explicit
nodelist): bethe matrix byte-identical to nx (0 mismatches via np.array_equal /
allclose atol=0). Directed/multigraph raise NetworkXNotImplemented. pytest -k
"bethe or hessian or spectr": 94 passed.
BETHE_SHA 40e4623575d871d6b1f4943070aec82d3ed8f6f96fe8f41ebc594a9fd138c54c

## Timing (warm min-of-6, gnp weighted)
| N    | nx     | fnx before | fnx after |
|------|-------:|-----------:|----------:|
| 500  | 4.23ms |  13.08ms   |  2.26ms   |
| 1000 | 9.40ms |  35.33ms   |  5.29ms   |
=> 3.4-3.7x SLOWER -> ~1.8x FASTER than nx; ~5.8x self-speedup.

## Score
Impact: high (3.5x slower -> 1.8x faster, ~5.8x self). Confidence: high
(byte-identical vs nx 0/60, 94 tests). Effort: trivial (to_scipy call args).
Score >> 2.0.
