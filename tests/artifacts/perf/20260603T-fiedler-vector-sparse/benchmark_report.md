# fiedler_vector: sparse shift-invert ARPACK instead of dense eigh

Lever: fiedler_vector formed the DENSE Laplacian and ran np.linalg.eigh
(O(n^3)) for just the 2nd-smallest eigenpair -- the same ~6.5x tax as
algebraic_connectivity (8a4ac4e5d). For a SPARSE graph with a SIMPLE
second-smallest eigenvalue, get the Fiedler eigenpair with shift-invert ARPACK
(scipy.sparse.linalg.eigsh, sigma=0, return_eigenvectors=True).

The Fiedler vector is sign-ambiguous -- nx and the old dense solver already
disagreed on sign (seeds 2,3 are sign-flipped), and on DEGENERATE lambda2
(complete/cycle/grid, gap l3-l2 ~ 1e-15) the current dense fnx ALSO differs from
nx (the eigenvector is not unique). So: canonicalize the sparse vector to a
largest-magnitude-component-positive sign (matches nx up to sign for
non-degenerate lambda2), and fall back to the EXACT dense eigh whenever lambda2
is not strictly separated from lambda3, on dense (avg degree >= 16) / tiny
(< 12 nodes) graphs, or on any failure -- byte-identical to the prior
implementation there.

## Benchmark (watts_strogatz(400,6,0.3), median of 3)

| impl        | time     |
|-------------|----------|
| nx          | 242 ms   |
| fnx BEFORE  | 1558 ms  |
| fnx AFTER   | 9 ms     |

Self-speedup ~170x; now 0.04x (27x FASTER than nx).

## Isomorphism proof

Returns a VALID Fiedler eigenvector (||L v - lambda2 v|| < 1e-5) on
watts/path/grid/complete/cycle/weighted/tiny x normalized; non-degenerate
lambda2 matches nx up to sign; directed -> NetworkXNotImplemented; disconnected
-> NetworkXError (test_fiedler_vector_sparse_parity, 6 cases). 315 existing
fiedler/spectral/algebraic tests pass.

## Note

spectral_ordering (bead br-r37-c1-193zq) delegates to nx for exact sign +
tie-break, so it does NOT share the dense-eigh tax and is left as-is. A native
safe-Rust Lanczos/LOBPCG remains the deeper lever.
