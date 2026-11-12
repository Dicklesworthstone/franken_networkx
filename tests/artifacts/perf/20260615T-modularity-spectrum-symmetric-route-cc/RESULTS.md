# modularity_spectrum — native symmetric route (sibling of 04z53.9112)

## Lever (one)
Route undirected `Graph` `modularity_spectrum` through the already-shipped
safe-Rust `symmetric_eigvals_rust` kernel (no Rust rebuild), presented as
complex128. The undirected modularity matrix B = A − k kᵀ / 2m is symmetric,
so its eigenvalues are real — but nx/`scipy.linalg.eigvals` runs the GENERAL
(non-Hermitian) dgeev path and ignores that. Directed keeps the SciPy
`directed_modularity_matrix` fallback.

## Proof
- Tolerance-coded golden sha256 (sorted real+imag, round 8, signed-zero
  normalized) over {karate, path7, cycle9, complete8, ba120, grid6x5,
  directed6}: FNX == NX ==
  `c9eaf8a1101c23abaed753eaa6a5916ad674a828fa3955b4cb41d89c02a170c1`
- dtype complex128 on every case; max abs delta 3.8e-14.
- Empty-graph raise parity: both `NetworkXError`.
- `test_community_extras.py::test_modularity_spectrum_matches_networkx`
  updated to compare sorted values (LAPACK/QR solver order is unstable),
  consistent with the existing `adjacency_spectrum` contract; passes.

## Timing (warm, min-of-7, BA(n,*,seed))
| n   | nx (scipy) | native | vs nx  |
|-----|------------|--------|--------|
| 96  | 2.2 ms     | 1.1 ms | 1.9x   |
| 200 | 126.5 ms   | 5.8 ms | 21.9x  |
| 400 | 454.5 ms   | 38.7 ms| 11.8x  |

## Score
Impact 5 (12-22x vs nx + drops C LAPACK per no-gaps) × Confidence 5
(golden sha match, test green) / Effort 1 (pure-Python routing) ≫ 2.0.

## Contract note
Solver order (LAPACK Schur/Francis deflation) is unstable and not portable
across BLAS builds; `modularity_spectrum` returns eigenVALUES only (no
eigenvector pairing), so sorted-value + dtype parity is the correct contract.
