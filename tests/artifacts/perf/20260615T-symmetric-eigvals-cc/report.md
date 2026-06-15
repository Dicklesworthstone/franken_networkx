# Own safe-Rust symmetric dense eigensolver — no C BLAS/LAPACK (br-r37-c1-04z53.9109)

Agent: cc (CopperCliff) · 2026-06-15

## No-gaps directive
`laplacian_spectrum` / `adjacency_spectrum` call `np.linalg.eigvalsh` /
`scipy.linalg.eigvals` — i.e. they link **C LAPACK** (OpenBLAS/MKL) for the
eigensolve. The standing no-gaps directive requires our OWN 100% safe-Rust
LAPACK-class kernels, never linking C BLAS/MKL/XLA.

## What landed (step 1 of the eigensolver)
A complete, machine-precision **100% safe-Rust symmetric dense eigenvalue
solver** in `fnx-algorithms`, exposed as `_fnx.symmetric_eigvals_rust`:
- `householder_tridiagonalize` — Householder reduction to tridiagonal form,
  eigenvalues-only (no Q accumulation). Safe-Rust analogue of LAPACK `dsytrd`.
- `tridiagonal_ql_eigvals` — implicit-shift QL with Wilkinson shift
  (NR `tqli`, eigenvalues only). Analogue of LAPACK `dsterf`.
- `symmetric_eigvals` — Householder→QL pipeline, ascending eigenvalues,
  `None` fallback on dimension mismatch / non-convergence.

`laplacian_spectrum` is wired to the native kernel for small dense Laplacians
(`n ≤ 10`, where it beats numpy's LAPACK dispatch overhead) with the numpy
path retained for larger matrices — **never regresses larger graphs**.

## Correctness (machine precision vs LAPACK)
`symmetric_eigvals_rust` vs `np.linalg.eigvalsh` on random symmetric matrices:
```
n=  5 maxrel=1.08e-15     n= 50 maxrel=4.11e-15
n= 20 maxrel=2.50e-15     n=100 maxrel=8.70e-15
```
Rust unit tests cross-validate against the production Jacobi eigensolver to
1e-9 across n=1..50, plus diagonal / 2×2 closed-form / P4-Laplacian checks
(`cargo test -p fnx-algorithms lu_pade_tests` — 12 passed).
`laplacian_spectrum` tolerance parity vs nx across n=2..120: max abs err
2.49e-14 (np.allclose rtol=1e-9). 265 spectral pytest passed.

## Why byte-identical golden-sha is N/A
Two distinct backward-stable eigensolvers (QL vs LAPACK D&C) produce eigenvalues
that agree to ~1e-14 but differ in the last bits — a byte-identical sha is not
achievable and not the contract. Parity is tolerance-based (`np.allclose`),
matching how nx itself is tested.

## Bench (native vs LAPACK, the wired small-n regime)
```
n=  6  native 1.80x faster      n= 10  break-even (~0.99x)
n=  8  native 1.26x faster      n≥ 20  LAPACK faster (3-4x) -> stays on numpy
```

## Next step (named, per no-ceiling addendum)
The naive scalar Householder is 3-4x slower than LAPACK's blocked+SIMD `dsytrd`
at n≥50. To drop C LAPACK at parity for real sizes: blocked (BLAS-3) Householder
reduction + portable-SIMD rank-2 update, then a divide-and-conquer tridiagonal
solver (LAPACK `dstedc` analogue). Target ratio ≤1.2x at n=200. Tracked on
bead br-r37-c1-04z53.9109.
