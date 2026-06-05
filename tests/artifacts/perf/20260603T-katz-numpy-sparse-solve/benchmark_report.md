# katz_centrality_numpy: sparse LU solve instead of dense O(n^3)

Lever: katz_centrality_numpy built the DENSE adjacency (to_numpy_array) and ran
`np.linalg.solve(I - alpha*A.T, b)` -- a dense O(n^3) solve, identical to nx.
On a large SPARSE graph this is catastrophic. The Katz linear system
(I - alpha*A.T) x = b is itself sparse for a sparse graph, so solve it with a
sparse LU (scipy.sparse.linalg.spsolve) over the fast sparse adjacency
(to_scipy_sparse_array). Same solution to machine precision; any failure
(singular system at the spectral-radius limit) falls back to the exact dense
solve.

## Benchmark (watts_strogatz(n,6,0.3), median of 3)

| graph    | nx       | fnx BEFORE | fnx AFTER |
|----------|----------|------------|-----------|
| n=200    | 163 ms   | ~227 ms    | 2 ms      |
| n=1200   | 5176 ms  | ~3066 ms   | 46 ms     |

Self-speedup ~67-110x; now ~0.01x (≈110x FASTER than nx).

## Isomorphism proof

Katz values match networkx within 1e-8 across normalized {True,False},
unweighted/weighted, beta scalar/dict, alpha, and n up to 400; incomplete-beta
NetworkXError; empty graph -> {}; multigraph -> NetworkXNotImplemented
(test_katz_numpy_sparse_parity, 6 cases). 6 existing katz tests pass.

## Note

Same "sparse beats nx's dense numeric kernel" pattern as the spectral eigsh
wins (algebraic_connectivity 8a4ac4e5d / fiedler_vector a90c3c887). Other
dense-linear-algebra centralities on sparse graphs are candidates for the same
treatment (e.g. current-flow / information centrality if they form dense
Laplacian pseudo-inverses).
