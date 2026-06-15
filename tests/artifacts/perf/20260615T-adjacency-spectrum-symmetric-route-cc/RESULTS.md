# br-r37-c1-04z53.9112 — Native symmetric route for adjacency_spectrum

## Lever (one)
Route undirected `Graph` `adjacency_spectrum` through the already-shipped
safe-Rust `symmetric_eigvals_rust` kernel (Householder tridiagonalization +
implicit-shift QL, from br-r37-c1-04z53.9109), presented as `complex128`.
Directed / multigraph / subclass / weight=callable keep the SciPy fallback.
No Rust rebuild — pure Python routing to an existing binding.

## Why it was "blocked" and why that was wrong
The bead note claimed raw LAPACK eigenvalue ORDER had to be reproduced.
But the project's own contract test
`test_adjacency_spectrum_returns_complex_match_nx` **sorts both sides**
("solver order is unstable"). The contract is `dtype==complex128` +
**sorted-value** parity — NOT raw Schur-deflation order (which is not even
portable across BLAS builds). Raw-order reproduction was self-imposed and
infeasible; it was never required.

## Root cause of the gap
`networkx.adjacency_spectrum` calls `scipy.linalg.eigvals` — the GENERAL
(non-Hermitian) dgeev path — on a SYMMETRIC matrix. It ignores symmetry and
is ~10-16x slower than a symmetric tridiagonal QL.

## Proof
- Contract tests: `test_review_mode_regression_lock.py -k adjacency_spectrum` 2 passed;
  `-k "spectrum or spectral or estrada or eigval"` 7 passed.
- Tolerance-coded golden sha256 (sorted real+imag, round 8, signed-zero
  normalized) over corpus {path5, cycle7, complete6, star10, ba96, grid5x4,
  directed5, weighted5}:
  FNX == NX == `1d4334bc9e295bc2b0c4d0b5d32d3efe5591eb915770b8ff4aeab02cb6bea276`
- dtype parity complex128 on every case; max abs delta (raw) 3.2e-14.
- Empty-graph raise parity: both `NetworkXError`.

## Timing (warm, min-of-9, BA(n,3,seed=1))
| n   | before (scipy) | after (native) | nx       | self   | vs nx  |
|-----|----------------|----------------|----------|--------|--------|
| 96  | 1.65 ms        | 1.15 ms        | 1.77 ms  | 1.44x  | 1.54x  |
| 200 | 108.75 ms      | 6.53 ms        | 88.62 ms | 16.65x | 13.57x |
| 400 | 402.12 ms      | 38.59 ms       | 372.4 ms | 10.42x | 9.65x  |
| 800 | 3492 ms        | 270.8 ms       | 3370 ms  | 12.90x | 12.45x |

## Score
Impact 5 (10-16x vs nx at scale + drops C LAPACK per no-gaps directive) ×
Confidence 5 (golden sha match, contract + spectrum tests green) / Effort 1
(pure-Python routing, no Rust) ≫ 2.0.

## Fallback
weight=callable, directed, multigraph, subclass, empty, or missing binding →
unchanged SciPy `eigvals` path.
