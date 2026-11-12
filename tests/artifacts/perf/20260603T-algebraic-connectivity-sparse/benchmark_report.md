# algebraic_connectivity: sparse shift-invert ARPACK instead of dense eigvalsh

Lever: algebraic_connectivity (the Fiedler value = 2nd-smallest Laplacian
eigenvalue) formed the DENSE Laplacian and ran np.linalg.eigvalsh (O(n^3)),
ignoring the `method` kwarg — ~7x slower than networkx (1.85s vs 0.26s on a
400-node sparse graph), which uses a sparse iterative solver. Match nx's
algorithm CLASS: build the sparse Laplacian and pull the few smallest
eigenvalues with shift-invert ARPACK (scipy.sparse.linalg.eigsh, sigma=0
targets eigenvalues nearest 0). For a connected graph the smallest is 0 and the
second is the algebraic connectivity.

Robustness: k=4 (not 2) + a "smallest ~= 0, all finite" sanity check guard a
missed/degenerate eigenvalue; a sparsity gate (avg degree < 16) + maxiter=200
keep it off dense Laplacians where shift-invert converges slowly; tiny graphs
(<12 nodes) and ANY failure fall back to the exact dense eigvalsh, so
correctness is never at risk.

## Benchmark (watts_strogatz(400,6,0.3), median of 3)

| impl        | time     |
|-------------|----------|
| nx          | 240 ms   |
| fnx BEFORE  | 1850 ms  |
| fnx AFTER   | 7 ms     |

Self-speedup ~260x; now 0.03x (34x FASTER than nx).

## Isomorphism proof

Fiedler value matches nx within 1e-6 across watts/path/cycle/complete/grid/
weighted graphs x normalized {False, True}; disconnected -> 0.0; directed ->
NetworkXNotImplemented; <2 nodes -> NetworkXError; method/tol/seed kwargs
accepted (value unchanged); dense graphs take the dense path and return < 5s
(test_algebraic_connectivity_sparse_parity, 7 cases). 8 existing
spectral/algebraic tests pass.

## Deeper future lever

A native safe-Rust Lanczos / LOBPCG with nullspace deflation (matching nx's
tracemin) would remove the scipy/ARPACK dependency entirely; the scipy-sparse
solver here matches nx's solver class for an immediate 260x win. fiedler_vector
+ spectral_ordering share the dense eigh and are the obvious follow-ups (the
eigenvector has a sign/degeneracy ambiguity, so deferred).
